# investment-dashboard — ADR 인덱스 (ADR-DB)

파일명은 `NNNN-title.md`, 문서 내 참조 키는 `ADR-DB-NNNN`.

> **2026-09-15 갱신** — 전역 ADR(`ADR-CT-*`)을 담던 `quant-contract` 는 서브모듈
> 제거와 호스트 저장소 삭제로 더 이상 존재하지 않는다. 이 저장소의 `ADR-DB-*` 가
> 이제 유일한 ADR 계열이다.

모듈 국소 결정은 여기에 쌓는다.

## 목록

| 번호 | 결정 | 상태 | 출처 |
|---|---|---|---|
| [DB-0001](0001-vanilla-js-and-no-typescript.md) | vanilla JS 를 유지하고 빌드 단계를 만들지 않는다 (TypeScript 미도입 포함) | ✅ 채택 2026-08-16 | 00 검수 · 절대 제약 7 · 배포-전략 §4.2 |
| [DB-0002](0002-single-chart-library-apexcharts.md) | 차트 라이브러리를 ApexCharts 하나로 유지하고, 캔들 성능 실측에서만 예외를 둔다 | ✅ 채택 2026-08-16 | 05 검증본 §5.4 · 레포 실측 |
| [DB-0003](0003-portfolio-and-risk-stay-here.md) | 포트폴리오 최적화·리스크는 이 레포 안에서 완성한다 (portfolio-service 분리 철회) | ✅ 채택 2026-08-17 | 06 구조 재설계 §1.3 · CONTEXT rev.7 |
| [DB-0004](0004-skfolio-is-a-baseline-not-a-replacement.md) | skfolio 는 교차검증 기준선이고 이 레포의 구현이 정본이다 | ✅ 채택 2026-08-17 | 06 구조 재설계 §1.3 · CONTEXT §9 |
| DB-0005 | BI 도구를 택1한다 (Power BI vs Tableau) | ☐ | 08 리서치 후 |

> **DB-0003 은 폐기된 `ADR-PF-*` 스코프를 흡수한다.** `portfolio-service` 를 만들지
> 않기로 했으므로 그 레포에 갈 예정이던 결정이 여기로 온다.
>
> **BI 도구 택1은 0003 → 0005 로 밀렸다.** 번호 재사용이 아니다 — 그 자리표는
> 실물 파일이 없는 예약이었고, CONTEXT rev.7 §6 이 0003·0004 를 각각
> 포트폴리오·skfolio 로 배분했다. 채택된 ADR 의 번호는 바꾸지 않는다.

> DB-0001 은 05 원본의 ADR-001(vanilla JS) + ADR-002(TypeScript 미도입)를 합친 것이다 —
> 둘은 "빌드 단계를 만들지 않는다" 는 같은 결정의 두 면이다 (05 검증본 §5.6).

## 템플릿 (MADR-minimal)

```markdown
# ADR-DB-000N: <결정을 동사로 한 줄>

## 상태
채택됨 / 개정됨(YYYY-MM-DD, rev.N) / superseded by ADR-DB-000M

## 맥락
무엇 때문에 이 결정이 필요했는가. **근거가 외부 정책에 의존하면 그 사실을 여기 적는다.**

## 결정
무엇을 하기로 했는가. 번호를 매겨 명확하게.

## 근거
왜 그렇게 했는가. **1차 출처(레포·논문·공식문서)만 인용한다.**

## 결과
이 결정 때문에 무엇이 쉬워지고 무엇이 어려워지는가.
```
