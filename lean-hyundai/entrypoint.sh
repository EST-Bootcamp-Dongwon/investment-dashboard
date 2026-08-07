#!/usr/bin/env sh
# 예측 → 백테스트 → 리포트를 한 번에 수행합니다.
#
#   1) Yahoo Finance 에서 일봉을 받고
#   2) 학습 구간으로 모델을 적합해 검증 구간 신호를 만들고
#   3) LEAN 엔진이 그 신호로 실제 주문을 집행하고
#   4) 예측 정확도와 매매 성과를 한 장의 HTML 로 묶습니다.
set -eu

TICKER="${HD_TICKER:-005380.KS}"
NAME="${HD_NAME:-현대차}"
TRAIN_START="${HD_TRAIN_START:-2025-01-01}"
TRAIN_END="${HD_TRAIN_END:-2025-12-31}"
TEST_START="${HD_TEST_START:-2026-01-01}"
TEST_END="${HD_TEST_END:-2026-06-30}"
# 피처 워밍업용 여유 구간. SMA20·RSI14 등이 학습 첫날부터 값을 가지려면
# 학습 시작일보다 앞선 데이터가 필요합니다.
#
# 고정 날짜가 아니라 학습 시작일에서 역산합니다. 웹앱의 실험실 API 도 같은 규칙
# (train_start - warmup_days)을 쓰기 때문에, 두 경로가 같은 시세 구간을 받아
# 같은 결과를 냅니다. 고정해 두면 학습 구간을 바꿀 때마다 둘이 어긋납니다.
WARMUP_DAYS="${HD_WARMUP_DAYS:-120}"
DATA_START="${HD_DATA_START:-$(date -d "${TRAIN_START} -${WARMUP_DAYS} days" +%Y-%m-%d)}"
INITIAL_CASH="${HD_INITIAL_CASH:-100000000}"

mkdir -p /Lean/Data /results

echo "=============================================="
echo " 1/4  일봉 다운로드  ${TICKER}  ${DATA_START} ~ ${TEST_END}"
echo "=============================================="
python3 /module/download_price_data.py \
  --ticker "${TICKER}" \
  --output /results/prices.csv \
  --start "${DATA_START}" \
  --end "${TEST_END}"

echo
echo "=============================================="
echo " 2/4  예측 모델 학습 → 신호 생성"
echo "      학습 ${TRAIN_START} ~ ${TRAIN_END}  /  검증 ${TEST_START} ~ ${TEST_END}"
echo "=============================================="
cd /module
python3 /module/make_signals.py \
  --prices /results/prices.csv \
  --signals-out "/Lean/Data/${HD_SIGNAL_FILE:-hyundai_signals.csv}" \
  --json-out /results/prediction.json \
  --ticker "${TICKER}" \
  --name "${NAME}" \
  --train-start "${TRAIN_START}" \
  --train-end "${TRAIN_END}" \
  --test-start "${TEST_START}" \
  --test-end "${TEST_END}" \
  --initial-cash "${INITIAL_CASH}"

# 신호 CSV 사본을 결과 폴더에도 남겨 재현·검증이 가능하게 합니다.
cp "/Lean/Data/${HD_SIGNAL_FILE:-hyundai_signals.csv}" /results/signals.csv

echo
echo "=============================================="
echo " 3/4  LEAN 백테스트"
echo "=============================================="
cp /module/config.json /results/config.json
cd /results
dotnet /Lean/Launcher/bin/Debug/QuantConnect.Lean.Launcher.dll

echo
echo "=============================================="
echo " 4/4  HTML 리포트 생성"
echo "=============================================="
# 리포트가 실패해도 백테스트 산출물은 이미 확보돼 있으므로 실행 자체를 죽이지 않습니다.
if python3 /module/make_report.py \
    --prediction /results/prediction.json \
    --lean-results /results \
    --output /results/report.html; then
  echo "리포트: /results/report.html (호스트의 ./lean-hyundai-results/report.html)"
else
  echo "경고: 리포트 생성에 실패했습니다. 백테스트 결과 파일은 /results 에 남아 있습니다." >&2
fi
