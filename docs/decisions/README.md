# investment-dashboard — ADR 인덱스 (ADR-DB)

파일명은 `NNNN-title.md`, 문서 내 참조 키는 `ADR-DB-NNNN`.
전역 결정은 `../../../quant-contract/docs/decisions/` (ADR-CT-*)에 있다.

**전역 ADR은 10개가 상한**이다. 넘어가면 통합·재분류 신호다(CONTEXT §6).
모듈 국소 결정은 여기에 쌓는다.

## 목록

| 번호 | 결정 | 상태 | 출처 |
|---|---|---|---|
| [DB-0001](0001-vanilla-js-and-no-typescript.md) | vanilla JS 를 유지하고 빌드 단계를 만들지 않는다 (TypeScript 미도입 포함) | ✅ 채택 2026-08-16 | 00 검수 · 절대 제약 7 · 배포-전략 §4.2 |
| [DB-0002](0002-single-chart-library-apexcharts.md) | 차트 라이브러리를 ApexCharts 하나로 유지하고, 캔들 성능 실측에서만 예외를 둔다 | ✅ 채택 2026-08-16 | 05 검증본 §5.4 · 레포 실측 |
| DB-0003 | BI 도구를 택1한다 (Power BI vs Tableau) | ☐ | 08 리서치 후 |

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
