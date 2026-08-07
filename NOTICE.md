# 출처 표기 (NOTICE)

이 저장소는 **처음부터 직접 작성한 코드가 아닙니다.** 아래 원본을 기반으로 가져와
필요한 기능만 남기고 재구성한 개인 프로젝트입니다.

## 원본

| 항목 | 내용 |
| --- | --- |
| 원본 저장소 | <https://github.com/edumgt/investment-analysis> |
| 가져온 시점의 원본 커밋 | `6fcbb04` (`Recreate Docker Hub publish workflow configuration`) |
| 가져온 날짜 | 2026-08-07 (KST) |
| 저작자 | 강사님 / edumgt |
| 사용 허가 | 수업 중 구두로 **자유로운 사용·수정·개인 프로젝트화**를 허가받았습니다. |

## 라이선스에 관한 중요한 안내

**원본 저장소에는 LICENSE 파일이 없습니다.** 저작권법상 라이선스가 명시되지 않은
저작물은 기본적으로 모든 권리가 저작자에게 유보된 상태입니다. 따라서 이 저장소는
원본 코드에 대해 임의의 오픈소스 라이선스(MIT 등)를 부여하지 **않습니다.**

- 이 저장소를 제3자가 재사용하려면 **원저작자(edumgt)의 허가가 별도로 필요합니다.**
- 이 저장소가 Public 인 것은 학습·포트폴리오 목적의 공개일 뿐, 재배포 허가를 뜻하지 않습니다.
- 향후 원본에 라이선스가 명시되거나 서면 허가를 받으면 이 문서와 함께 `LICENSE` 파일을 추가합니다.

## 원본에서 제외한 기능

포트폴리오 분석 서비스에 필요하지 않아 가져오는 단계에서 제거했습니다.

| 구분 | 제거한 것 |
| --- | --- |
| 학습 | 학습 문서 뷰(`learn-03`~`learn-07`), `views/learn.js`, `data/learnDocs.js`, `GET /api/learn/doc/{doc_id}`, `scripts/sync_learning_menu.py` |
| 지난주 학습 정리 | 복습 문서 뷰(`learn-10`, `learn-11`) — 위 학습 기능과 같은 모듈을 사용했습니다 |
| 퀴즈 | `views/quiz.js`, `views/vocabularyExam.js`, `routers/quiz.py`, `routers/vocabulary_exam.py`, `quiz_seed.sql`, `scripts/init_quiz_mongodb.sh`, `docs/voca-exam.md` |
| 위 기능에 딸린 것 | **MongoDB 전체** (`app/backend/db.py`, `motor`·`pymongo` 의존성, Compose 의 `mongo`·`quiz-init` 서비스) — 퀴즈·단어장 시험 외에는 사용처가 없었습니다 |
| CI/CD | `.github/workflows/*` — 원본의 EC2(`/opt/investment-analysis`)와 `stock-trade` 등 **강사님 인프라 전용**이라 이 저장소에서는 동작할 수 없습니다. 배포 파이프라인은 v2.0 설계에서 다시 만듭니다 |

`docs/*.md` 학습 문서 자체는 **문서 검색(RAG) 색인의 원본**으로 계속 사용하므로 남겨 두었습니다.

## 원본에서 고친 것 — 실행되지 않던 버그 4건

가져오는 과정에서 컨테이너를 띄우고 전체 엔드포인트를 호출해 본 결과, **원본 상태로는
동작하지 않는 엔드포인트가 있었습니다.** 아래는 기능을 추가하거나 설계를 바꾼 것이
아니라, 이미 있는 코드가 실행되게 만든 최소 수정입니다.

| # | 증상 | 원인 | 조치 |
| --- | --- | --- | --- |
| 1 | `/api/quant/{backtest, portfolio, financial-knowledge, risk, pipeline}` 5개가 **모두 500** | `routers/quant.py` 가 `configure_matplotlib_korean_font` 를 5곳에서 호출하는데 import 가 없음. 정의는 `main.py`·`routers/ml.py` 에만 존재 | `app/backend/charting.py` 신설 후 `quant.py` 에서 import |
| 2 | `/api/quant/pipeline` 이 위를 고친 뒤에도 500 | 같은 파일이 `_calc_rsi` 를 호출하는데 import 가 없음. 정의는 `main.py` 에만 존재하고, `main.py` 는 `quant.py` 를 import 하므로 역방향 import 는 순환 참조 | `app/backend/indicators.py` 신설 후 `quant.py` 에서 import |
| 3 | (위 두 건에 가려져 있던 잠복 오류) | `quant.py` 가 `base64`·`io` 를 5곳에서 쓰는데 import 가 없음 | `quant.py` 상단에 `import base64`, `import io` 추가 |
| 4 | `/api/cv/circle-animation` 이 500 | `requirements.txt` 의 `opencv-python` 은 GUI 빌드라 `python:3.12-slim` 에 없는 `libxcb.so.1` 을 요구해 `import cv2` 자체가 실패 | 서버용 `opencv-python-headless` 로 교체 (이 앱은 `VideoWriter`·`circle` 만 사용) |

추가로 `routers/ml.py` 의 `/api/genai/text-to-image` 에도 `import os` 가 빠져 있었습니다.
CUDA 가 없는 환경에서는 그 앞의 `503` 가드에 먼저 걸려 드러나지 않던 잠복 버그라 함께 고쳤습니다.

수정 뒤 전체 API 를 다시 호출해 **36개가 200** 을 반환하는 것을 확인했습니다.
남은 비정상 응답은 모두 정상적인 것입니다 — 필수 필드를 비운 요청의 `422`,
`DART_API_KEY` 미설정의 `503`, CUDA 부재의 `503`.

### v2.0 에서 정리할 것

`configure_matplotlib_korean_font` 와 `_calc_rsi` 의 **사본이 `main.py` 에 아직 남아** 있습니다.
동작에는 문제가 없어 v1.0 에서는 손대지 않았지만, 설계 정리 단계에서
`charting.py`·`indicators.py` 하나로 합쳐야 합니다. `routers/ml.py` 의 폰트 함수 사본도 같습니다.

## 그 밖에는 원본 그대로입니다

위 표에 없는 코드는 강사님 원본을 **수정 없이** 가져왔습니다. 이는 의도된 것으로,
이 저장소의 첫 커밋을 **"기획서 v1.0 = 강사님 원본"** 기준선으로 삼아 이후 v2.0 설계·구현의
변경분을 명확히 구분하기 위해서입니다.

원본 대비 실제 변경 파일은 다음으로 확인할 수 있습니다.

```bash
diff -r --brief \
  ../../learning/08-investment-analysis/lecture \
  . \
  -x .git -x __pycache__ -x lean-results
```
