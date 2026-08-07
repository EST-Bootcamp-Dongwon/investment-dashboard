"""여러 라우터가 함께 쓰는 기술적 지표 계산 함수.

## 이 모듈이 생긴 이유

`charting.py` 와 같은 사정이다. 강사님 원본에서 `routers/quant.py` 의
`/api/quant/pipeline` 은 `_calc_rsi(...)` 를 호출하지만 이 함수는 `main.py` 에만
정의되어 있고 `quant.py` 는 import 하지 않는다. 그래서 해당 엔드포인트가
`NameError` 로 500 을 냈다.

`main.py` 는 `routers/quant.py` 를 import 하므로 `quant.py` 가 `main.py` 를
거꾸로 import 하면 순환 참조가 된다. 그래서 정의를 의존성 없는 이 모듈로 옮기고
양쪽이 여기에서 가져다 쓰도록 했다.

## v2.0 에서 할 일

`main.py` 에도 `_calc_rsi` 사본이 남아 있다. 동작에는 문제가 없어 v1.0 에서는
건드리지 않았지만, 설계 정리 단계에서 이 모듈로 합쳐야 한다.
"""
from __future__ import annotations

# pandas 는 무거워서 모듈을 import 하는 시점이 아니라 함수 호출 시점에 불러온다.
# (원본 코드가 라우터 함수 안에서 import 하던 방식과 같은 이유다.)


def calc_rsi(series, period: int = 14):
    """RSI(Relative Strength Index, 상대강도지수)를 계산한다.

    최근 `period` 거래일 동안의 평균 상승폭과 평균 하락폭의 비율을 0~100 으로
    환산한 값이다. 통상 70 이상이면 과매수, 30 이하면 과매도로 읽지만
    **미래 가격을 알려 주는 지표가 아니다.**

    인자와 반환값 모두 `pandas.Series` 이며, 앞의 `period` 개 값은 계산에 필요한
    표본이 모자라 `NaN` 이 된다. 호출하는 쪽에서 `dropna()` 로 걸러야 한다.
    """
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    # 하락이 전혀 없던 구간에서 0 으로 나누는 것을 막는다. 이때 RSI 는 100 에 수렴한다.
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))
