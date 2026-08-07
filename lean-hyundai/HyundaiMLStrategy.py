"""현대차 예측 신호 전략 — LEAN 알고리즘.

make_signals.py 가 만든 signals.csv 를 Custom Data 로 읽어 **주문을 집행**합니다.
예측 자체는 여기서 하지 않습니다. 예측은 백테스트 시작 전에 끝나 있고,
이 알고리즘은 그 신호대로 사고파는 체결·비용만 책임집니다.

체결 규약
  signals.csv 의 한 행은 "그날 종가에 확정된 신호"입니다. 엔진이 t일 봉을 받는
  순간 주문을 내면 close[t] 에 체결되고, 그 포지션이 t+1일 봉에서 평가됩니다.
  예측이 겨냥한 구간(close[t] → close[t+1])과 정확히 맞습니다.

통화에 관한 주의
  계좌 통화는 LEAN 기본값(USD)을 그대로 둡니다. 환율 데이터를 붙이지 않았기 때문에
  숫자에 붙은 통화 기호만 USD 일 뿐, **모든 금액은 원(KRW)으로 읽으시면 됩니다.**
  원화를 달러로 환산한 게 아닙니다.
"""

import os
from datetime import date, datetime, timedelta

from QuantConnect import Globals, Resolution, SubscriptionTransportMedium
from QuantConnect.Algorithm import QCAlgorithm
from QuantConnect.Data import SubscriptionDataSource
from QuantConnect.Orders.Fees import FeeModel, OrderFee
from QuantConnect.Orders.Slippage import ConstantSlippageModel
from QuantConnect.Python import PythonData
from QuantConnect.Securities import CashAmount

SIGNAL_FILE = os.getenv("HD_SIGNAL_FILE", "hyundai_signals.csv")

# 비용 가정 — hd_core.py 의 기본값과 같은 숫자를 씁니다. 한쪽만 고치면 두 결과가 갈립니다.
COMMISSION_RATE = float(os.getenv("HD_COMMISSION_RATE", "0.00015"))
SELL_TAX_RATE = float(os.getenv("HD_SELL_TAX_RATE", "0.0015"))
SLIPPAGE_RATE = float(os.getenv("HD_SLIPPAGE_RATE", "0.0005"))


class HyundaiSignalData(PythonData):
    """일자 · 종가 · 예측수익률 · 매매신호를 담은 CSV."""

    def get_source(self, config, date, is_live):
        source = os.path.join(Globals.data_folder, SIGNAL_FILE)
        return SubscriptionDataSource(source, SubscriptionTransportMedium.LOCAL_FILE)

    def reader(self, config, line, date, is_live):
        if not line.strip() or line.startswith("Date"):
            return None

        fields = line.split(",")
        if len(fields) < 4:
            return None

        try:
            bar = HyundaiSignalData()
            bar.symbol = config.symbol
            bar.time = datetime.strptime(fields[0].strip(), "%Y-%m-%d")
            bar.end_time = bar.time + timedelta(days=1)
            bar.value = float(fields[1])
            bar["PredReturn"] = float(fields[2])
            bar["Signal"] = float(fields[3])
            return bar
        except (ValueError, IndexError):
            # 형식이 깨진 행은 조용히 버립니다. 전체 실행을 죽일 이유가 없습니다.
            return None


class KoreanEquityFeeModel(FeeModel):
    """위탁수수료(양방향) + 증권거래세·농어촌특별세(매도 시)."""

    def get_order_fee(self, parameters):
        order = parameters.order
        security = parameters.security
        trade_value = abs(order.get_value(security))

        rate = COMMISSION_RATE
        if order.quantity < 0:  # 매도에만 세금이 붙습니다.
            rate += SELL_TAX_RATE

        return OrderFee(CashAmount(trade_value * rate, security.quote_currency.symbol))


class HyundaiMLStrategy(QCAlgorithm):
    def initialize(self):
        start = date.fromisoformat(os.getenv("HD_TEST_START", "2026-01-01"))
        end = date.fromisoformat(os.getenv("HD_TEST_END", "2026-06-30"))
        self.set_start_date(start.year, start.month, start.day)
        # 마지막 봉까지 처리되도록 하루 여유를 둡니다.
        finish = end + timedelta(days=1)
        self.set_end_date(finish.year, finish.month, finish.day)
        self.set_cash(float(os.getenv("HD_INITIAL_CASH", "100000000")))

        ticker = os.getenv("HD_LEAN_SYMBOL", "005380")
        self.hd = self.add_data(HyundaiSignalData, ticker, Resolution.DAILY)
        self.symbol = self.hd.symbol

        self.hd.set_fee_model(KoreanEquityFeeModel())
        self.hd.set_slippage_model(ConstantSlippageModel(SLIPPAGE_RATE))

        # 매수·보유 벤치마크. 같은 시세를 쓰므로 전략과 직접 비교됩니다.
        self.set_benchmark(self.symbol)

        self.trade_count = 0
        self.last_signal = 0

    def on_data(self, data):
        if self.symbol not in data:
            return

        bar = data[self.symbol]
        price = float(bar.value)
        if price <= 0:
            return

        signal = int(bar["Signal"])
        predicted = float(bar["PredReturn"])

        self.plot("현대차", "종가", price)
        self.plot("신호", "매수보유", signal)
        self.plot("예측", "예측수익률(%)", predicted * 100)

        holding = self.portfolio[self.symbol]
        invested = holding.quantity > 0

        if signal == 1 and not invested:
            # 수수료·슬리피지 여유를 두고 가용 현금 전부를 씁니다.
            quantity = int(self.portfolio.cash * 0.995 / price)
            if quantity > 0:
                self.market_order(self.symbol, quantity)
                self.trade_count += 1
                self.debug(f"{self.time.date()} 매수 {quantity}주 @ {price:,.0f} (예측 {predicted:+.4%})")
        elif signal == 0 and invested:
            self.liquidate(self.symbol)
            self.debug(f"{self.time.date()} 청산 @ {price:,.0f} (예측 {predicted:+.4%})")

        self.last_signal = signal

    def on_end_of_algorithm(self):
        self.log(f"진입 횟수: {self.trade_count}")
        self.log(f"최종 자산: {self.portfolio.total_portfolio_value:,.0f}")
