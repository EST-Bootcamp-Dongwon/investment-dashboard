"""도메인 계층이 실패를 알리는 방법.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑥. `main.py` 의
라우트 22개를 `services/` 로 옮기려면 그 본문에 있던 **`HTTPException` 24건**을 어떻게
할지부터 정해야 한다. 그대로 옮기면 아키텍처 5절 4번 명령 —
*"서비스가 HTTP 를 모름"* — 이 곧바로 깨진다.

## 왜 F03~F28 과 다른 방식인가

먼저 만든 다섯(F03·F04·F05·F27·F28)은 **의미마다 예외를 따로** 두었다 —
`CombinationInputError`(→400) · `CombinationDataError`(→503) 처럼. 라우터가 그
의미를 읽어 상태 코드를 정한다. 계층 분리로는 그쪽이 더 옳다. 도메인은 "무엇이
잘못됐나" 만 말하고, "그것이 몇 번인가" 는 HTTP 를 아는 쪽이 정하기 때문이다.

**여기서는 그렇게 하지 않았다.** 옮겨야 할 24건이 서로 다른 일곱 화면에 흩어져
있고, 각각을 의미별 예외로 다시 설계하면 **상태 코드가 바뀔 위험**이 생긴다.
지금 화면들은 400·404·422·502·503 을 구분해 다른 문구를 띄운다
(`app/frontend/js/api.js`). 이번 작업은 **계층을 옮기는 것이지 동작을 바꾸는
것이 아니다** — 그래서 상태 코드를 값으로 들고 다니는 쪽을 택했다.

    raise HTTPException(status_code=404, detail="…")   # 옮기기 전
    raise DomainError(404, "…")                        # 옮긴 뒤

바뀐 것은 예외 타입 하나뿐이고, 나가는 응답은 상태 코드도 본문도 같다.

## 그래서 이것은 절충이다

`DomainError` 는 HTTP 상태 코드를 안다. 순수한 도메인 예외가 아니다.
**`fastapi` 를 import 하지 않을 뿐이다.** 판정 명령은 통과하지만, 계층 분리의
정신으로는 F03~F28 쪽이 낫다. 나중에 화면별로 의미를 정리할 때 이 예외를
의미별 예외로 나누는 것이 다음 단계다 — 그때 상태 코드가 바뀌지 않는지
화면과 대조해야 한다.

## 번역은 한 곳에서 한다

`main.py` 가 `@app.exception_handler(DomainError)` 를 하나 등록한다. 라우터마다
`try/except` 를 쓰지 않는 이유는, 22개 라우트가 전부 같은 번역을 하게 되어
빠뜨린 곳이 생기면 **500 으로 새기** 때문이다.
"""

from __future__ import annotations


class DomainError(Exception):
    """도메인이 처리를 멈춘 이유. 상태 코드와 사용자에게 보일 문장을 함께 지닌다.

    `detail` 은 **화면에 그대로 나가는 문장**이다. 내부 사정(스택·모듈 이름)을
    담지 않는다. 원본 `HTTPException` 의 `detail` 을 글자 그대로 옮겼으므로
    지금 화면에 뜨는 문구와 같다.
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
