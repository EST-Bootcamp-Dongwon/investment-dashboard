# LEAN 백테스트 운영

> - **버전**: v2.1
> - **최종 수정**: 2026-08-10 (KST)
> - **상태**: 초안
> - **기준 코드**: `main` @ `718f161`
> - **역할**: F28(백테스트 실험실)과 LEAN 엔진의 **실행 방식·용량 관리·재현 절차**를 고정한다.
> - **관련**: [CN-002](../00-index/변경이력.md#cn-002) 컨테이너 용량 ·
>   [CN-019](../00-index/변경이력.md#cn-019) F28 로컬 전용 ·
>   [API-상세명세 3.1절](../40-API/API-상세명세.md#31-f28--apibacktest-lab)

---

## 0. 한 장 요약

| 항목 | 값 |
| --- | --- |
| LEAN 베이스 이미지 | `quantconnect/lean:latest` — **42.5 GB** (1벌) |
| 파생 이미지 | `hyundai-lean-module` · `samsung-lean-module` |
| **파생 1개의 실제 증가분** | **현대차 148.1 KiB · 삼성 56.0 KiB** (실측) |
| 실행 위치 | **로컬 전용** ([D-06](../00-index/마스터인덱스.md#2-지금-확정된-설계-결정)) |
| 웹앱(F28)이 부르는 것 | LEAN 엔진 **아님** — `hd_core` 벡터화 근사 |
| v2.0 변경 | `COPY` → **볼륨 마운트** 전환 |

---

## 1. [CN-002](../00-index/변경이력.md#cn-002) 재실측 — 전제는 여전히 틀렸고, 이번엔 정밀합니다

### 1.1 제기됐던 우려

> "42.5GB 짜리 lean 모듈을 전략마다 일일이 받으면 디스크가 부족해진다."

### 1.2 CN-002 가 근거로 삼은 것

CN-002(2026-08-07)는 `docker system df` 총계(62.23 GB)가 42.5 × 3 = 127.5 GB 가
아니라는 점을 들어 "공유 베이스라 중복 계산된 것" 이라고 판단했습니다.
**결론은 맞았지만 근거가 간접적이었습니다** — 총계만으로는 *무엇이* 공유되는지 모릅니다.

### 1.3 레이어 단위로 다시 쟀습니다 (2026-08-10)

```
$ docker image inspect <이미지> --format '{{range .RootFS.Layers}}{{println .}}{{end}}'
$ comm -12 base.txt hd.txt | wc -l                        # 실측 2026-08-10
```

| 이미지 | 레이어 수 | 베이스와 공통 | **고유** |
| --- | ---: | ---: | ---: |
| `quantconnect/lean:latest` | 35 | — | — |
| `hyundai-lean-module:local` | 43 | **35** | **8** |
| `samsung-lean-module:local` | 40 | **35** | **5** |

**베이스 35개 레이어가 한 벌도 빠짐없이 공유됩니다.**

### 1.4 고유 레이어의 실제 바이트

```
$ docker history <이미지> --format '{{.Size}}\t{{.CreatedBy}}'    # 실측 2026-08-10
```

| `hyundai-lean-module` 고유 8개 | 바이트 |
| --- | ---: |
| `RUN chmod +x /module/entrypoint.sh && mkdir -p /results` | 8,189 |
| `COPY entrypoint.sh` | 12,300 |
| `COPY config.json` | 12,300 |
| `COPY HyundaiMLStrategy.py` | 16,400 |
| `COPY download_price_data.py` | 12,300 |
| `COPY make_report.py` | 45,100 |
| `COPY make_signals.py` | 12,300 |
| `COPY hd_core.py` | 32,800 |
| **합계** | **151,689 B (148.1 KiB)** |

| `samsung-lean-module` 고유 5개 | 바이트 |
| --- | ---: |
| `RUN chmod +x …` | 8,189 |
| `COPY entrypoint.sh` · `config.json` · `download_samsung_data.py` · `SamsungBuyAndHold.py` | 12,300 × 4 |
| **합계** | **57,389 B (56.0 KiB)** |

> **CN-002 의 "전략 하나가 늘어도 실제 증가분은 수백 KB" 가 정확히 확인됐습니다.**
> 148.1 KiB 와 56.0 KiB 입니다. **42.5 GB 는 전략 수와 무관하게 딱 한 번 지불합니다.**

### 1.5 디스크 총계 재측정

```
$ docker system df                                         # 실측 2026-08-10
TYPE          TOTAL  ACTIVE  SIZE     RECLAIMABLE
Images        18     5       67.5GB   43.57GB (64%)
Build Cache   125    0       2.907GB  2.907GB
```

| 항목 | 2026-08-07 (CN-002) | **2026-08-10** |
| --- | ---: | ---: |
| 이미지 총계 | 62.23 GB | **67.5 GB** (이미지 14 → 18) |
| 회수 가능 | 43.88 GB (70 %) | **43.57 GB (64 %)** |
| 빌드 캐시 | 2.818 GB | **2.907 GB** |

> 이 저장소만의 값이 아닙니다. `docker system df` 는 **머신 전체**를 보여 주므로
> `ollama`(8.04 GB) · `investment-analysis-*`(2.61 GB × 2) 등 다른 프로젝트가 섞여 있습니다.
> LEAN 3형제가 차지하는 실제 몫은 **베이스 42.5 GB + 파생 0.2 MB** 입니다.

---

## 2. v2.0 결정 — `COPY` 를 볼륨 마운트로 바꿉니다

### 2.1 지금 구조

```dockerfile
# lean-hyundai/Dockerfile
FROM quantconnect/lean:latest
USER root
COPY hd_core.py /module/hd_core.py
COPY make_signals.py /module/make_signals.py
…                                        ← 코드 7개를 이미지에 굽는다
RUN chmod +x /module/entrypoint.sh && mkdir -p /results
ENV PYTHONPATH=/module
ENTRYPOINT ["/module/entrypoint.sh"]
```

**대가는 용량이 아니라 절차입니다.** `docker-compose.hd.yaml` 주석이 직접 경고합니다.

> "전략 코드나 모델을 고쳤다면 `--build` 를 반드시 붙이세요.
> **코드가 COPY 로 이미지에 구워지기 때문에 안 붙이면 예전 코드가 그대로 돕니다.**"

### 2.2 v2.0 구조

코드를 굽지 않고 **실행 시점에 얹습니다.**

```yaml
# docker-compose.hd.yaml (v2.0 방향)
services:
  hd-backtest:
    image: quantconnect/lean:latest     # 파생 이미지를 만들지 않는다
    entrypoint: ["/bin/sh", "/module/entrypoint.sh"]
    environment:
      PYTHONPATH: /module               # Dockerfile 의 ENV 를 여기로
      HD_TICKER: ${HD_TICKER:-005380.KS}
      …
    volumes:
      - ./lean-hyundai:/module:ro       # 코드를 마운트
      - ./lean-hyundai-results:/results
```

### 2.3 무엇이 좋아지나

| | 지금 (`COPY`) | v2.0 (마운트) |
| --- | --- | --- |
| 코드 수정 후 | **`--build` 필수** (잊으면 옛 코드가 돎) | **바로 반영** |
| 전략 추가 | Dockerfile + compose 서비스 신설 | **폴더 + compose 서비스** |
| 유지 이미지 | `quantconnect/lean` + 파생 N개 | **`quantconnect/lean` 1벌** |
| 이미지 목록 | 3개 | **1개** |

**CN-002 조치 1을 확정합니다.** 용량 절감은 0.2 MB 로 미미하지만,
**"안 붙이면 예전 코드가 돈다" 는 재현성 함정이 사라집니다.**
백테스트에서 재현성은 부수적인 성질이 아닙니다.

### 2.4 전환할 때 옮겨야 하는 것 3가지

`COPY` 를 빼면 Dockerfile 이 하던 일도 함께 옮겨야 합니다.

| Dockerfile 이 하던 일 | 옮길 곳 |
| --- | --- |
| `ENV PYTHONPATH=/module` | compose `environment:` |
| `ENTRYPOINT ["/module/entrypoint.sh"]` | compose `entrypoint:` |
| `RUN chmod +x /module/entrypoint.sh` | **`sh /module/entrypoint.sh` 로 호출** (실행 비트에 의존하지 않음) |
| `RUN mkdir -p /results` | `entrypoint.sh:26` 이 이미 `mkdir -p /Lean/Data /results` 를 합니다 |

> ⚠ **`chmod` 를 대체하는 방식이 핵심입니다.** 마운트된 파일의 실행 비트는 호스트
> 파일시스템에 좌우됩니다. 이 저장소는 WSL 경유 Windows 마운트라 지금은 `-rwxrwxrwx`
> 이지만(실측 2026-08-10), 다른 환경에서 클론하면 다를 수 있습니다.
> **`entrypoint: ["/bin/sh", "/module/entrypoint.sh"]` 로 호출하면 실행 비트가
> 필요 없습니다.**

### 2.5 함께 할 정리

| # | 조치 | 회수량 (2026-08-10 기준) |
| --- | --- | ---: |
| 1 | `docker builder prune` | **2.907 GB** |
| 2 | 전환 후 파생 이미지 2개 삭제 | 약 0.2 MB (레이어 기준) |
| 3 | `docker image prune` (미사용 정리) | 회수 가능 **43.57 GB** 중 일부 |

> **3번은 신중히 하세요.** 회수 가능 43.57 GB 에는 **다른 프로젝트의 이미지**가
> 섞여 있습니다(`mongo:7` · `mariadb:11.4` · `ollama/ollama` 등).
> `docker image prune -a` 는 쓰지 않습니다.

---

## 3. 실행 경로가 둘입니다 — 헷갈리지 않게

이 프로젝트에는 백테스트 경로가 **두 개**이고, **서로 다른 것을 계산합니다.**

| | ⓐ 웹앱 F28 (`/api/backtest-lab/*`) | ⓑ LEAN 엔진 (`docker compose`) |
| --- | --- | --- |
| 실행 | 브라우저에서 즉시 | 터미널에서 수 분 |
| 계산 | **벡터화 근사** | **실제 주문 집행 시뮬레이션** |
| 코드 | `hd_core.simple_backtest()` | `QuantConnect.Lean.Launcher.dll` |
| 산출 | JSON (화면 렌더) | `/results` 의 JSON·CSV·`report.html` |
| 위상 | 탐색용 | **정본** |

`backtest_lab.py` 의 docstring 이 이 관계를 명시합니다.

> "이 라우터는 LEAN 엔진을 부르지 않고 벡터화 계산으로 성과를 근사합니다
> (**웹 요청 안에서 42.5GB 컨테이너를 띄울 수는 없습니다**). 정본이 필요하면
> `docker compose -f docker-compose.hd.yaml run --rm hd-backtest` 로 엔진을 돌리세요."
> — `app/backend/routers/backtest_lab.py:6~10`

### 3.1 둘이 같은 신호를 쓰는 이유

**같은 모듈을 import 합니다.**

```python
# app/backend/routers/backtest_lab.py:25~30
_LEAN_HD = _ROOT / "lean-hyundai"
sys.path.insert(0, str(_LEAN_HD))
import hd_core
```

`lean-hyundai/Dockerfile:5` 의 주석도 같은 말을 합니다 —
"`hd_core` 는 `make_signals`(컨테이너 안)와 웹앱 백엔드(컨테이너 밖) 양쪽에서 import 됩니다."

**워밍업 규칙도 일치시켜 놓았습니다.**

| | 규칙 | 위치 |
| --- | --- | --- |
| ⓑ 컨테이너 | `DATA_START = TRAIN_START − WARMUP_DAYS` | `entrypoint.sh:23` |
| ⓐ 웹앱 | `data_start = train_start − warmup_days` | `backtest_lab.py:176~178` |

> `entrypoint.sh:19~22` 주석이 이유를 적습니다 — "고정 날짜가 아니라 학습 시작일에서
> 역산합니다. 웹앱의 실험실 API 도 같은 규칙을 쓰기 때문에, 두 경로가 같은 시세 구간을
> 받아 같은 결과를 냅니다. **고정해 두면 학습 구간을 바꿀 때마다 둘이 어긋납니다.**"

**이 정합성은 v2.0 에서 반드시 지켜야 하는 제약입니다.** 한쪽만 고치면 조용히 갈라집니다.

### 3.2 화면에 무엇이라 적혀 있나

`/api/backtest-lab/config` 가 화면에 내려보내는 문구 3개입니다.

```python
# app/backend/routers/backtest_lab.py:243~247
"notes": [
    "검증 구간은 학습 구간보다 뒤여야 하고, 오늘 이전이어야 합니다.",
    "이 화면의 성과는 벡터화 근사치입니다. 정본은 LEAN 엔진 실행 결과입니다.",
    "체결은 신호 확정일 종가로 가정합니다. 실제로는 그 가격에 살 수 없습니다.",
]
```

**세 번째 문장이 특히 중요합니다.** [R-07](../00-index/강사님-요구사항-대조표.md#1-대조표)
관점에서 이 화면은 이미 모범적입니다 — 근사임을 밝히고, 체결 가정의 비현실성까지
스스로 말합니다. [CN-060](../00-index/변경이력.md#cn-060) 면책 컴포넌트를 적용할 때
**이 문구를 지우지 않습니다.**

---

## 4. 재현 절차

### 4.1 정본 백테스트 (현대차)

```bash
# 저장소 루트에서
docker compose -f docker-compose.hd.yaml run --rm hd-backtest
# 결과: ./lean-hyundai-results/
#   prices.csv · signals.csv · prediction.json · config.json
#   <LEAN 산출 JSON> · report.html
```

`entrypoint.sh` 가 4단계를 순서대로 돕니다.

| 단계 | 하는 일 | 실패 시 |
| --- | --- | --- |
| 1/4 | Yahoo 에서 일봉 다운로드 | `set -eu` 로 즉시 중단 |
| 2/4 | 학습 → 신호 CSV 생성 | 〃 |
| 3/4 | LEAN 엔진 실행 | 〃 |
| 4/4 | HTML 리포트 | **중단하지 않음** (`entrypoint.sh:70~84`) |

> 4단계만 예외입니다 — "리포트가 실패해도 백테스트 산출물은 이미 확보돼 있으므로
> 실행 자체를 죽이지 않습니다"(`entrypoint.sh:70`). 옳은 설계입니다.

### 4.2 파라미터

전부 환경변수이고 기본값이 `docker-compose.hd.yaml` 에 있습니다.

| 변수 | 기본값 | 비고 |
| --- | --- | --- |
| `HD_TICKER` | `005380.KS` | Yahoo 티커 |
| `HD_TRAIN_START` / `_END` | `2025-01-01` / `2025-12-31` | 학습 |
| `HD_TEST_START` / `_END` | `2026-01-01` / `2026-06-30` | 검증 |
| `HD_WARMUP_DAYS` | `120` | 3.1절 |
| `HD_INITIAL_CASH` | `100000000` | 1억 원 |
| `HD_COMMISSION_RATE` | `0.00015` | 위탁수수료 0.015 % |
| `HD_SELL_TAX_RATE` | `0.0015` | 매도세 0.15 % — **compose 주석이 "가정, 확인 필요" 라고 적음** |
| `HD_SLIPPAGE_RATE` | `0.0005` | 슬리피지 0.05 % |

> ⚠ **`HD_SELL_TAX_RATE` 는 코드 주석 스스로 "(확인 필요)" 입니다**
> (`docker-compose.hd.yaml:37`). 백테스트 성과에 직접 들어가는 값이므로
> **v2.1 에서 근거를 확정해야 합니다.** 지금은 가정임을 명시한 상태로 둡니다.

### 4.3 산출물은 커밋하지 않습니다

```
# .gitignore:25~33
lean-results/          lean-results-old/          lean-hyundai-results/
lean-cli/              # data/ 만 226MB
```

`.gitignore` 주석이 이유를 적습니다 — "실행할 때마다 타임스탬프 파일이 쌓이고,
`docker compose … run --rm` 으로 언제든 다시 만든다."

**재현 가능한 산출물은 저장소에 넣지 않습니다.** 대신 재현 명령을 문서에 둡니다.

---

## 5. LEAN CLI 는 대안이 아닙니다

[CN-002](../00-index/변경이력.md#cn-002) 가 이미 확인한 내용입니다.

`lean init` 이 **QuantConnect 계정 로그인을 요구합니다.** 엔진 자체는 인증하지 않는데
CLI 의 init 단계가 강제합니다. 무인 실행·심사 시연에 부적합합니다.

저장소에 `lean-cli/` 폴더가 있으나 `.gitignore:33` 로 제외돼 있고
(`data/` 만 226 MB), **v2.0 실행 경로에 포함되지 않습니다.**

---

## 6. 배포와의 관계

| 질문 | 답 |
| --- | --- |
| LEAN 을 Vercel 에 올리나? | **아니오.** 42.5 GB 는 500 MB 제약의 85배입니다 |
| F28 화면은 배포되나? | **예.** `pages/backtest-lab.html` 은 정적 파일입니다 |
| F28 API 는 배포되나? | **예.** `hd_core` 벡터화 근사는 `sklearn` 만 있으면 됩니다 |
| 그럼 배포본에서 F28 은 무엇을 하나? | ⓐ 경로(근사)만 동작. ⓑ 정본은 로컬에서만 |

> [배포-전략 3.6절](배포-전략.md#36-requirementstxt-를-다시-써야-합니다)이
> 이 때문에 `scikit-learn` 을 배포 의존성에 **남겨 둡니다.**
> `backtest_lab.py:31` 이 모듈 import 시점에 `hd_core` 를 부르고,
> `hd_core.py:25` 가 `HistGradientBoostingRegressor` 를 import 하기 때문입니다.

---

## 7. 남은 확인 사항

| # | 내용 | 상태 |
| --- | --- | --- |
| 1 | `HD_SELL_TAX_RATE = 0.0015` 의 근거 | **(확인 필요)** — 코드 주석이 스스로 "가정" 이라고 적음 |
| 2 | 볼륨 마운트 전환 후 LEAN 이 `/module` 을 `:ro` 로 읽어도 되는지 (엔진이 `/module` 에 쓰지는 않는지) | **(확인 필요)** — `entrypoint.sh` 는 `/Lean/Data` 와 `/results` 에만 씁니다. 전환 시 1회 실행으로 확인 |
| 3 | `quantconnect/lean:latest` 의 태그가 움직이면 재현성이 깨짐 | **(확인 필요)** — 다이제스트 핀 검토. `latest` 는 재현 가능한 참조가 아닙니다 |
| 4 | 삼성 전략(`lean-samsung/`)을 v2.0 에 유지할지 | 수업 실습 산출물. F28 은 현대차만 씁니다. **유지하되 문서에서 "동작 확인용" 으로 위치를 명시** |
</content>
</invoke>
