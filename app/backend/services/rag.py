"""F27 문서 검색 챗 — Service.

Controller(`routers/rag.py`) → **Service(여기)** → Repository(`clients/doc_chunk_repo.py`)
→ 전송(`clients/supabase_client.py`).

아키텍처 2.1절대로 **이 파일은 HTTP 도 DB 도 모른다.** `HTTPException` 을 던지지 않고
`fastapi` 를 import 하지 않으며, Supabase 도 부르지 않는다. 여기 있는 것은 순수 계산뿐이다 —
문서를 자르고, 벡터로 만들고, 검색 결과를 답변 문장으로 조립한다.

## 여기 모인 코드는 원래 세 곳에 흩어져 있었다

| 옮긴 것 | 원래 자리 | 왜 옮겼나 |
| --- | --- | --- |
| `chunk_text` | `scripts/upload_docs_to_qdrant.sh:90~105` (bash 힙독 안 python) | 색인 전용이라 서버가 같은 규칙을 알 수 없었다 |
| `hash_embed` | 위 스크립트 `:110~125` **와** `routers/rag.py:52~59` **두 벌** | 사본이 갈라져 있었다 |
| `compose_answer` | `routers/rag.py:105~114` | 라우터가 도메인 판단을 하고 있었다 |

**`hash_embed` 가 두 벌이던 것이 이 이관에서 가장 위험한 대목이었다.** 색인 쪽은 항상
384 로 만들고(`upload_docs_to_qdrant.sh:155`), 질의 쪽은 Qdrant 컬렉션의 `vectors.size`
를 읽어 그 값을 차원으로 썼다(`routers/rag.py:62~68`). 컬렉션이 768 이면 질의는 768차원
해시 벡터를 만드는데 색인 벡터와는 아무 관계가 없는 값이라, **오류 없이 조용히 틀린
검색 결과**가 나온다. 한 함수로 합치면서 그 갈래가 사라졌다.

두 사본의 동작이 실제로 같았다는 것은 `scripts/verify_rag_api.py` 가 원문을 파싱해
대조한다 — "합쳐도 값이 안 바뀐다" 를 주장이 아니라 실측으로 남긴다.

## 임베딩은 해시(384)다

`gemini-embedding-001`(768)이 ERD 4.3절의 채택안이지만 **사용자가 Gemini 키를 쓰지
않기로 결정했고**(2026-08-14), 키도 저장소에 없다. 따라서 `EMBED_METHOD` 는 `'hash'`
하나이고 검색은 `match_doc_chunk_hash` 를 탄다(마이그레이션 20260814120100).

**이것이 의미 검색이 아니라는 것을 숨기지 않는다.** 해싱 트릭은 어휘가 겹칠 때만 맞고
"분산투자" 와 "나누어 담는다" 를 잇지 못한다(CN-015). 응답의 `embed_method` 가 그
사실을 화면까지 실어 나른다.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

# ── 청킹 상수 ────────────────────────────────────────────────────────────────
#
# `upload_docs_to_qdrant.sh:11~12` 의 기본값을 그대로 옮겼다. 값을 바꾸면 이미 색인된
# 행의 `chunk_index` 체계가 달라져 재색인 전까지 검색 결과가 어긋난다.
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

# ── 임베딩 상수 ──────────────────────────────────────────────────────────────
EMBED_DIM = 384
EMBED_METHOD = "hash"

# ── 면책 (R-07 · CN-060) ─────────────────────────────────────────────────────
#
# 원문 요구: "AI 답변에는 교육용 정보이며 개인별 투자 조언이 아니라는 문구를 유지합니다"
#            (`docs/07.md:197`)
#
# 문구는 CN-060 이 확정한 `strong` 레벨 문장이고(`50-UI/화면-상세.md` 3.2절),
# `DISCLAIMER_CONTEXT` 는 같은 절이 F27 용으로 이미 적어 둔 한 문장이다. 새로 짓지 않았다.
#
# **서버가 이 문장을 응답에 싣는 이유**는 요구가 "AI 답변에는" 이라고 답변 자체를 지목하기
# 때문이다. 화면을 거치지 않고 API 를 직접 부르는 경로에서도 문구가 답변에 붙어 나간다.
# F03 이 같은 판단을 먼저 했다 (`services/recommendation.py:92~94`).
#
# 프런트에도 같은 문장이 `app/frontend/js/components/disclaimer.js` 에 있다. 두 사본이
# 갈라지면 화면과 API 가 다른 말을 하게 되므로, `scripts/verify_rag_api.py` 가 두 파일에서
# 문자열을 뽑아 `==` 로 대조한다. 사본을 없애지 못하는 것은 한쪽이 파이썬이고 한쪽이
# 브라우저 자바스크립트라 공유할 런타임이 없기 때문이고, 그래서 **대조를 자동화했다.**
DISCLAIMER = (
    "이 화면의 결과는 금융 교육을 위한 예시이며, 개인별 투자 조언이나 특정 상품 "
    "추천이 아닙니다. 투자 판단과 그 결과는 본인의 책임입니다."
)
DISCLAIMER_CONTEXT = (
    "AI 답변은 색인된 학습 문서를 근거로 생성되며, 원문에 없는 내용은 확인이 필요합니다."
)

# ── 답변 조립 ────────────────────────────────────────────────────────────────
ANSWER_EMPTY = "관련 문서를 찾지 못했습니다. 다른 표현으로 질문해 보세요."
ANSWER_HEAD = "문서에서 찾은 관련 내용입니다. 오른쪽 원문과 함께 확인하세요."
ANSWER_CHUNK_LIMIT = 3
ANSWER_EXCERPT_CHARS = 500

_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣_]+")


class RagInputError(ValueError):
    """사용자가 고칠 수 있는 입력 문제. 라우터가 422 로 번역한다."""


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """문서 한 편을 겹침 있는 고정 길이 조각으로 자른다.

    `upload_docs_to_qdrant.sh:90~105` 의 `chunk_text` 를 **동작까지 그대로** 옮겼다.
    미묘한 곳이 둘 있고, 둘 다 의도적으로 보존했다.

    ① **빈 조각은 건너뛰되 번호는 건너뛰지 않는다.** `strip()` 후 빈 조각은
       `chunks` 에 안 들어가므로, `chunk_index` 는 창(window)의 순번이 아니라
       *살아남은 조각*의 순번이다. 공백만 있는 구간이 중간에 있으면 둘이 어긋난다.
    ② **마지막 창은 `end >= len(text)` 로 끊는다.** `start += step` 만 쓰면 마지막
       조각이 겹침 길이만큼 한 번 더 나온다.
    """
    text = text.strip()
    if not text:
        return []
    if overlap >= chunk_size:
        # step 이 0 이하가 되어 무한 루프가 된다. 원본 스크립트에는 이 가드가 없었고
        # 인자를 상수로만 넘겨서 드러나지 않았을 뿐이다.
        raise RagInputError("overlap 은 chunk_size 보다 작아야 합니다.")

    chunks: list[str] = []
    step = chunk_size - overlap
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start += step
    return chunks


def hash_embed(text: str, dim: int = EMBED_DIM) -> list[float]:
    """의존성 없는 해시 임베딩. **색인과 질의가 같이 쓴다.**

    토큰을 sha256 으로 해싱해 앞 4바이트로 칸을, 5번째 바이트의 홀짝으로 부호를 정해
    누적한 뒤 L2 정규화한다(해싱 트릭). 코사인 거리로 비교하려면 정규화가 필요하다.

    `dim` 인자를 남겨 두었지만 **호출자는 기본값을 쓴다.** 질의 쪽 옛 사본이 저장소가
    알려 준 차원을 그대로 따라가다가 색인과 어긋날 수 있었던 것이 이 함수의 유일한
    위험이었고(모듈 docstring 참고), 지금은 차원이 `EMBED_DIM` 하나로 고정돼 있다.

    토큰이 없거나 부호가 상쇄돼 노름이 0이면 영벡터를 그대로 돌려준다 — 나눌 수 없다.
    영벡터는 코사인 유사도가 정의되지 않지만, `<=>` 는 오류 대신 값을 주므로 검색이
    깨지지는 않는다. 원본 두 사본도 같은 선택이었다.
    """
    vector = [0.0] * dim
    for token in _TOKEN_PATTERN.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        vector[int.from_bytes(digest[:4], "big") % dim] += 1.0 if digest[4] & 1 == 0 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def count_tokens(text: str) -> int:
    """`token_count` 컬럼에 넣을 값.

    테이블-정의서 4.7절이 이 컬럼을 "2,048 토큰 상한 감시용" 이라 적었는데, 그 상한은
    Gemini 의 것이다. 해시 임베딩에는 상한이 없다. **그래도 기록한다** — 나중에 Gemini
    로 옮길 때 "지금 청크가 상한에 걸리는가" 를 색인을 다시 돌리지 않고 알 수 있다
    (ERD 8절 미결 1번).

    다만 이 값은 **정규식 토큰 수이지 Gemini 의 토큰 수가 아니다.** 둘은 다르다.
    상한 판정에 그대로 쓰면 안 되고, 크기 감각을 주는 용도다.
    """
    return len(_TOKEN_PATTERN.findall(text.lower()))


def build_chunks(source_doc: str, content: str) -> list[dict[str, Any]]:
    """문서 한 편을 `doc_chunk` 행 모양으로 만든다. DB 에 넣지는 않는다.

    색인 스크립트와 관리자 재색인 경로가 **같은 함수를 쓴다.** 둘이 따로 자르면
    같은 문서가 경로에 따라 다르게 색인되고, `uq_doc_chunk(source_doc, chunk_index)`
    가 그것을 막아 주지도 않는다 — 제약은 번호의 중복만 보지 내용은 보지 않는다.
    """
    rows: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunk_text(content)):
        rows.append(
            {
                "source_doc": source_doc,
                "chunk_index": index,
                "content": chunk,
                "embedding_hash": hash_embed(chunk),
                "embed_method": EMBED_METHOD,
                "token_count": count_tokens(chunk),
            }
        )
    return rows


def to_source(row: dict[str, Any]) -> dict[str, Any]:
    """`match_doc_chunk_hash` 가 준 행을 화면이 아는 모양으로 되돌린다.

    `content` → `text` 로 이름만 바꾼다. 테이블-정의서 4.7절이 "응답 직렬화 단계에서
    되돌린다" 고 미리 정해 둔 것이고, 그래야 `ragChat.js:25` 의 `source.text` 가
    그대로 산다.

    `score` 를 4자리로 반올림하는 것은 옛 라우터(`routers/rag.py:87`)가 하던 그대로다.
    화면이 `toFixed(3)` 으로 다시 줄이므로(`ragChat.js:23`) 보이는 값은 바뀌지 않는다.
    """
    return {
        "score": round(float(row.get("score") or 0.0), 4),
        "source_doc": row.get("source_doc") or "",
        "chunk_index": int(row.get("chunk_index") or 0),
        "text": row.get("content") or "",
    }


def compose_answer(sources: list[dict[str, Any]]) -> str:
    """검색된 원문만 잘라 정리한다. 생성 모델이나 외부 지식은 쓰지 않는다.

    옛 `routers/rag.py:105~114` 를 그대로 옮겼다. 상위 3개를 500자로 자르는 것,
    말줄임표를 붙이는 조건, 공백을 한 칸으로 접는 것까지 같다.
    """
    if not sources:
        return ANSWER_EMPTY
    excerpts = []
    for source in sources[:ANSWER_CHUNK_LIMIT]:
        text = " ".join(str(source.get("text", "")).split())
        if text:
            ellipsis = "…" if len(text) > ANSWER_EXCERPT_CHARS else ""
            excerpts.append(f"• {text[:ANSWER_EXCERPT_CHARS]}{ellipsis}")
    return f"{ANSWER_HEAD}\n\n" + "\n\n".join(excerpts)


def build_llm_prompt(query: str, sources: list[dict[str, Any]]) -> str:
    """외부 AI 에게 보낼 프롬프트. 조립만 하고 부르지는 않는다 — 호출은 `clients/rag_llm.py`.

    옛 `routers/rag.py:125~134` 와 같은 문장이다. 14,000자 절단도 그대로 뒀다.
    """
    context = "\n\n".join(
        f"[출처 {index + 1}: {source.get('source_doc', '')} / 조각 "
        f"{int(source.get('chunk_index', 0)) + 1}]\n{source.get('text', '')}"
        for index, source in enumerate(sources)
    )[:14000]
    return (
        "아래 '검색 원문'만 근거로 사용자의 질문에 한국어로 간결하게 답하세요. "
        "원문에 없는 사실·숫자·투자 조언을 추가하지 말고, 정보가 부족하면 부족하다고 밝히세요. "
        "출처 번호를 [출처 1]처럼 표시하고 3개 이내의 짧은 문단 또는 목록으로 정리하세요.\n\n"
        f"사용자 질문: {query}\n\n검색 원문:\n{context}"
    )
