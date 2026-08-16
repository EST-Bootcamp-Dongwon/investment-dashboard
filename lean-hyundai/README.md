# lean-hyundai — 예측 검증 백테스트 모듈

**"2025년으로 학습한 모델이 2026년 상반기를 얼마나 맞혔고, 그대로 매매하면 돈이 됐는가"** 를
한 번의 명령으로 검증하고 HTML 리포트까지 만듭니다.

`lean-samsung/` 이 "엔진이 도는지" 확인용이었다면, 이쪽은 **워크포워드 검증**이 목적입니다.

---

## 빠른 실행

```bash
cd /mnt/c/Users/kik32/workspace/EST-Camp-AI-Quant/projects/investment-dashboard
docker compose -f docker-compose.hd.yaml run --rm hd-backtest
```

끝나면 `lean-hyundai-results/report.html` 을 브라우저로 엽니다.

```bash
wslview lean-hyundai-results/report.html   # 또는 explorer.exe lean-hyundai-results
```

> **코드를 고쳤다면 `--build` 를 붙이세요.** 코드가 `COPY` 로 이미지에 구워지기 때문에
> 안 붙이면 예전 코드가 그대로 돕니다.
>
> ```bash
> docker compose -f docker-compose.hd.yaml run --build --rm hd-backtest
> ```

---

## 파이프라인

| 단계 | 하는 일 | 파일 |
| --- | --- | --- |
| 1 | Yahoo Finance 일봉 다운로드 | `download_price_data.py` |
| 2 | 피처 → 학습 → 예측 → 신호 CSV | `make_signals.py` · `hd_core.py` |
| 3 | LEAN 엔진이 신호대로 **주문 집행** | `HyundaiMLStrategy.py` |
| 4 | 예측 정확도 + 매매 성과 → HTML | `make_report.py` |

**예측과 집행을 분리한 이유**: 예측은 백테스트가 시작되기 전에 끝나 있고, LEAN 은 그 신호로
사고파는 체결·수수료·세금만 책임집니다. 이렇게 나눠야 "예측이 맞았는가"와 "돈이 됐는가"를
따로 측정할 수 있습니다.

### 산출물 (`lean-hyundai-results/`)

| 파일 | 내용 |
| --- | --- |
| `report.html` | **최종 리포트.** 자체완결이라 이 파일만 있으면 어디서든 열립니다 |
| `prediction.json` | 예측 지표 · 일자별 예측/실제 · 간이 백테스트 결과 |
| `prices.csv` | 내려받은 일봉 원본 |
| `signals.csv` | LEAN 에 넣은 신호 (재현·검증용 사본) |
| `HyundaiMLStrategy-summary.json` | LEAN 성과 통계 |
| `orders.csv` | 체결 내역 |
| `log.txt` | 실행 로그 (**이어붙음**) |

---

## 설정 바꾸기

전부 환경 변수입니다. `docker-compose.hd.yaml` 에 기본값이 있습니다.

```bash
# 삼성전자를 2024년으로 학습해 2025년 검증
HD_TICKER=005930.KS HD_NAME=삼성전자 HD_LEAN_SYMBOL=005930 \
HD_TRAIN_START=2024-01-01 HD_TRAIN_END=2024-12-31 \
HD_TEST_START=2025-01-01 HD_TEST_END=2025-12-31 \
  docker compose -f docker-compose.hd.yaml run --rm hd-backtest
```

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `HD_TICKER` | `005380.KS` | Yahoo 티커 (코스닥은 `.KQ`) |
| `HD_LEAN_SYMBOL` | `005380` | LEAN 안에서 쓸 심볼 이름 |
| `HD_TRAIN_START` / `HD_TRAIN_END` | `2025-01-01` / `2025-12-31` | 학습 구간 |
| `HD_TEST_START` / `HD_TEST_END` | `2026-01-01` / `2026-06-30` | 검증 구간 (out-of-sample) |
| `HD_WARMUP_DAYS` | `120` | 피처 워밍업용 여유 일수 |
| `HD_INITIAL_CASH` | `100000000` | 초기 자본 (원) |
| `HD_COMMISSION_RATE` | `0.00015` | 위탁수수료 (편도) |
| `HD_SELL_TAX_RATE` | `0.0015` | 매도세 — **가정값, 확인 후 조정** |
| `HD_SLIPPAGE_RATE` | `0.0005` | 슬리피지 (편도) |

---

## 브라우저에서 반복 실험하기

같은 코어(`hd_core.py`)를 쓰는 웹 화면이 있습니다.

```bash
docker compose up -d backend
```

→ <http://localhost:8000/pages/backtest-lab.html> (사이드바 **백테스트 실험실**)

종목·구간·비용을 바꿔가며 즉시 돌려보고, 마음에 드는 결과를 HTML 리포트로 내려받습니다.

> ⚠️ 실험 화면의 성과는 **벡터화 근사치**입니다. 정수 주 단위 체결과 주문별 비용까지
> 반영한 정본이 필요하면 위의 `docker compose -f docker-compose.hd.yaml` 로 LEAN 엔진을 돌리세요.
> (실측: 간이 −15.93% vs LEAN −15.78%)

---

## 설계 결정 세 가지

### 1. LightGBM 이 아니라 sklearn `HistGradientBoostingRegressor`

LEAN 이미지에는 LightGBM 4.6.0 이 있지만 **웹앱 백엔드 컨테이너에는 없습니다.**
두 환경에 공통으로 있는 부스팅 구현이 sklearn 뿐이라, 같은 코드가 양쪽에서 같은 결과를
내도록 sklearn 으로 통일했습니다.

### 2. RSI 는 Wilder(ewm) 가 아니라 단순이동평균(Cutler)

Wilder 원형은 `ewm` 이라 **첫 행부터 재귀적**입니다. 시세를 며칠 전부터 받았느냐에 따라
RSI 가 통째로 달라져, 같은 종목·같은 구간을 돌려도 결과가 재현되지 않습니다
(실제로 워밍업 시작일만 바꿨더니 전략 수익률이 −30.9% → −15.9% 로 움직였습니다).
rolling 평균으로 바꿔 **모든 피처의 참조 범위를 최근 20봉 이내로 한정**했습니다.

### 3. 신호 CSV 의 한 행 = 그날 종가에 확정된 신호

```
Date = t (신호 확정일) · Close = close[t] · Signal = t+1일 보유 여부
```

LEAN 이 t일 봉을 받는 순간 `Signal` 을 보고 `close[t]` 에 체결하고, 그 포지션이 t+1일 봉에서
평가됩니다. 예측이 겨냥한 구간(close[t] → close[t+1])과 정확히 맞습니다.
신호가 t+1 행에 붙으면 하루 늦게 들어가 완전히 다른 전략이 됩니다.

---

## 선견(lookahead) 차단

- 모든 피처는 t일 종가까지 확정된 값만 사용합니다.
- 학습 표본에서 **타깃 날짜가 검증 시작일 이후인 행을 제외**합니다.
  빼지 않으면 학습 마지막 행의 타깃(= 검증 첫날 수익률)이 새어 들어갑니다.
- 검증 구간에서 재학습하지 않습니다. 학습 구간으로 한 번 적합한 모델을 고정해 씁니다.

---

## 한계 — 결과를 실제 투자 성과로 읽으면 안 되는 이유

- **체결 가정이 낙관적입니다.** 신호는 t일 종가가 확정돼야 나오는데 체결도 t일 종가로 봅니다.
  현실에서는 종가를 보고 그 종가에 살 수 없습니다.
- **KRX 거래 캘린더를 쓰지 않습니다.** `force-exchange-always-open: true` 라 휴장일·거래정지·
  상하한가가 반영되지 않습니다.
- **배당이 빠져 있습니다.** 매수·보유의 실제 성과는 리포트 값보다 높습니다.
- **계좌 통화는 LEAN 기본값(USD)** 입니다. 환율 변환을 하지 않았으므로 금액은 전부
  **원(KRW)으로 읽으시면 됩니다.**
- **단일 종목·단일 구간**이라 통계적으로 결론을 내기에 표본이 부족합니다.
- **Yahoo Finance 비공식 엔드포인트**를 씁니다. 차단·형식 변경 가능성이 있고 수정주가 처리가
  공식 시세와 다를 수 있습니다.

---

## 트러블슈팅

| 증상 | 원인·대처 |
| --- | --- |
| `유효한 일봉이 0건입니다` | 티커·기간 확인. 코스피 `.KS`, 코스닥 `.KQ` |
| `HTTPError: 429` | Yahoo 요청 제한. 잠시 후 재시도 |
| `학습 구간에 사용할 표본이 없습니다` | 워밍업 부족. `HD_WARMUP_DAYS` 를 늘리세요 |
| 리포트만 실패 | 백테스트 산출물은 남아 있습니다. `make_report.py` 를 따로 실행하세요 |
| 코드를 고쳤는데 결과가 그대로 | `--build` 를 빠뜨린 것입니다 |

LEAN 엔진 자체(Docker·디스크·elan 충돌 등)는 저장소 루트의 `lean_guide.md` 9절을 보세요.
