#!/usr/bin/env bash
#
# 테스트-계획 5절 자동화 최소셋 + 기능별 왕복 검증을 한 번에 돌린다.
#
# 왜 있는가 — 검사가 12벌이 되면서 세션마다 "회귀 N벌 전량 재실행" 을 **손으로
# 세게** 됐다. CN-121·CN-126 이 두 번 보여 준 그대로, 손으로 적은 숫자는 언젠가
# 어긋난다. 목록을 파일에 두고 파일이 세게 한다.
#
# 아래 표는 검사 하나당 한 줄이고, 칸은 이렇다:
#
#     5.1절 항목 | 스크립트 | 허용 종료 코드 | 네트워크 | 무엇을 보는가
#
# **허용 종료 코드**가 이 러너의 핵심이다. 두 검사는 0 이 아닌 값을 정상으로 낸다 —
# `check_layers.py` 의 2 는 *"계층 분해가 아직 안 끝났다(회귀는 없다)"* 이고,
# `verify_smoke.py` 의 2 는 *"자격증명이 없어 DB 구간을 건너뛰었다"* 다.
# 그 둘을 실패로 세면 러너가 **언제나 빨간불**이 되고, 언제나 빨간 신호는 꺼진
# 신호와 같다.
#
# 실행
#     bash scripts/run_all_checks.sh              # 전부
#     bash scripts/run_all_checks.sh --offline    # 네트워크가 필요 없는 것만
#
# 종료 코드 — 0 전부 허용 범위 · 1 하나라도 벗어남 · 2 표에 없는 검사가 있음
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROOT}/.venv/bin/python"
cd "${ROOT}" || exit 1

[ -x "${PY}" ] || PY="python3"

OFFLINE_ONLY=0
[ "${1:-}" = "--offline" ] && OFFLINE_ONLY=1

# 순서는 **빠르고 네트워크가 필요 없는 것부터**다. 셋째 줄에서 깨졌는데 원격 왕복
# 여섯 벌을 기다린 뒤에 알게 되면 고치는 속도가 그만큼 늦다.
CHECKS=(
  "E|check_forbidden_terms.py|0|off|금지 표현 (3.4절 4-1·4-2)"
  "F|check_layers.py|0 2|off|계층 규칙 (아키텍처 5절 6개 명령)"
  "H|check_routes.py|0|off|라우트 68개 보존 (CN-065 분해 안전망)"
  "B|verify_dart_scoring.py|0|off|DART 재무 비율·점수"
  "C|verify_walkforward.py|0|off|hd_core 워크포워드"
  "A|verify_recommendation_rule.py|0|off|F03 판정 규칙 27조합"
  "-|verify_r07_expressions.py|0|off|R-07 확정적 표현 (F23·F25·F19)"
  "-|check_spec_links.py|0|off|docs/spec 문서 간 링크·앵커"
  "G|verify_smoke.py|0 2|on|스모크 (/api/health + A등급 4개)"
  "D|verify_recommendation_api.py|0|on|F03 추천 4개 · 원격 왕복"
  "-|verify_simulation_api.py|0|on|F05 시뮬레이션 · 원격 왕복"
  "-|verify_combination_api.py|0|on|F04 조합 · 원격 왕복"
  "-|verify_backtest_api.py|0|on|F28 백테스트 · 원격 왕복"
  "-|verify_rag_api.py|0|on|F27 RAG · 원격 왕복"
)

# ── 표에 없는 검사가 있는가 ──────────────────────────────────────────────────
# 새 검사를 만들고 여기 적는 것을 잊으면 러너가 조용히 그것을 빼고 돈다.
listed=""
for row in "${CHECKS[@]}"; do
  listed="${listed} $(echo "${row}" | cut -d'|' -f2)"
done

unlisted=""
for path in scripts/verify_*.py scripts/check_*.py; do
  name="$(basename "${path}")"
  case " ${listed} " in
    *" ${name} "*) ;;
    *) unlisted="${unlisted} ${name}" ;;
  esac
done

if [ -n "${unlisted}" ]; then
  echo "표에 없는 검사가 있습니다 —${unlisted}"
  echo "scripts/run_all_checks.sh 의 CHECKS 에 추가하세요."
  exit 2
fi

# ── 실행 ────────────────────────────────────────────────────────────────────
printf '\n%-4s %-32s %-6s %s\n' "항목" "검사" "종료" "결과"
printf '%s\n' "────────────────────────────────────────────────────────────────────"

failed=0
skipped=0
log_dir="$(mktemp -d)"

for row in "${CHECKS[@]}"; do
  item="$(echo "${row}" | cut -d'|' -f1)"
  script="$(echo "${row}" | cut -d'|' -f2)"
  allowed="$(echo "${row}" | cut -d'|' -f3)"
  network="$(echo "${row}" | cut -d'|' -f4)"
  what="$(echo "${row}" | cut -d'|' -f5)"

  if [ "${OFFLINE_ONLY}" = "1" ] && [ "${network}" = "on" ]; then
    printf '%-4s %-32s %-6s %s\n' "${item}" "${script}" "-" "건너뜀 (--offline)"
    skipped=$((skipped + 1))
    continue
  fi

  log="${log_dir}/${script}.log"
  "${PY}" "scripts/${script}" > "${log}" 2>&1
  code=$?

  # 검사가 스스로 센 건수를 그대로 옮긴다. 러너가 따로 세지 않는다.
  tally="$(grep -oE '[0-9]+ / [0-9]+ 통과' "${log}" | tail -1)"
  [ -z "${tally}" ] && tally="${what}"

  ok=0
  for good in ${allowed}; do
    [ "${code}" = "${good}" ] && ok=1
  done

  if [ "${ok}" = "1" ]; then
    printf '%-4s %-32s %-6s %s\n' "${item}" "${script}" "${code}" "${tally}"
  else
    printf '%-4s %-32s %-6s %s\n' "${item}" "${script}" "${code}" "실패 — ${tally}"
    failed=$((failed + 1))
    sed -n '/FAIL/,+3p' "${log}" | head -20 | sed 's/^/      /'
  fi
done

printf '%s\n' "────────────────────────────────────────────────────────────────────"
total=$(( ${#CHECKS[@]} - skipped ))
if [ "${failed}" = "0" ]; then
  echo "${total}벌 전부 허용 범위입니다. (로그: ${log_dir})"
  exit 0
fi
echo "${total}벌 중 ${failed}벌이 허용 범위를 벗어났습니다. (로그: ${log_dir})"
exit 1
