# AGENTS.md — investment-dashboard

> **이 저장소 자체가 규칙 정본이다** (2026-09-15). 공통 규칙 저장소였던
> `quant-contract` 는 서브모듈 제거와 호스트 저장소 삭제로 더 이상 존재하지
> 않는다 — 이 모듈은 이제 독립적으로 완성되는 개인 프로젝트다.

## 검증 명령

- 전체 검증: `invoke check` (ruff → pytest → uv export → docker build)
- 문서 검증: `invoke docs-check` (markdownlint → lychee --offline → openapi export)
- **CI가 아니라 이 명령이 정본이다.** CI는 이 명령을 호출만 한다.

## 금지

### 승격된 것 — 더 이상 legacy 가 아니다 (2026-08-16)

이 둘은 `upstream`(강사님 원본) 원격이 없어 3-way merge 계보 부담이 없다.
그래서 **복사하지 않고 폴더를 개명해 그 자리에서 발전시킨다.** 히스토리가 이어진다.

| 기호 | 이전 이름 | 현재 |
|---|---|---|
| ④ | `api-test` | **`projects/data-service`** |
| ① | `investment-portfolio-site` | **`projects/investment-dashboard`** |

### 읽기 전용 — 수정 금지

코드를 옮길 때는 이 모듈 안에 **복사한 뒤** 수정한다.

| 기호 | 경로 | 스택 | 계보 |
|---|---|---|---|
| ② | `C:\Users\kik32\workspace\Research-Prompt-Engineering` | Python | **projects 밖!** |
| ③ | `projects/stock-coin-trade` | Django 5.2.17 + DRF 3.18 + HTMX/Alpine | `upstream` + `upstream-main` |
| ⑤ | `projects/docker-class` | Docker·DevSecOps 실습 | `upstream` + `upstream-main` |
| — | `projects/investment-analysis` | 강의 원본 | `upstream` |

**③⑤와 investment-analysis 는 폴더를 이동·개명하지 않는다.** 강사님 원본과 3-way merge
계보가 살아 있어서(`upstream-main` 브랜치), 파일을 대거 이동한 뒤 upstream 을 얹으면
병합이 깨진다. ③은 추가로 **체결 리팩터링의 회귀 확인 대상**이라 계속 돌아가야 한다.

각 레포의 `NOTICE.md`(원저작자 edumgt 표시)는 승격 후에도 유지한다.

- `requirements.txt` 직접 편집 (`uv export` 생성물)
- 매매 신호 생성 경로에 LLM 호출 추가 (ADR-CT-0001)
- `docs/decisions/` 번호 재사용 — 폐기 시 status만 `superseded`로 바꾼다

## 이 모듈 특화

- **프론트 프레임워크 전환 제안 금지** (ADR-DB-0001, 절대 제약 7).
  Next.js·React·Vue·번들러 파이프라인·TypeScript 도입을 제안하지 않는다.
- **차트 라이브러리는 CDN `<script>` 한 줄로 붙는 것만.** npm 빌드가 필요하면 탈락.
- **백엔드 응답을 그대로 신뢰하지 않는다.** `js/api.js`가 단일 진입점이므로
  데이터 계층 교체는 거기서 한다.
- **BI 파일(`.pbix`/`.twbx`)은 바이너리다.** diff가 안 되고 용량이 크다.
  스크린샷은 커밋하되, 원본 파일은 용량을 보고 판단한다(Git LFS 또는 제외).
- `data/exports/`는 `.gitignore`. 익스포트 CSV는 금방 수십 MB가 된다.
- ①의 `Dockerfile`에서 **torch · diffusers · opencv-python-headless를 제거**한다.
  웹 요청 경로에서 쓰이지 않는다.
