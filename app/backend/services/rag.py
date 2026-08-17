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


# `build_llm_prompt()` 가 여기 있었습니다 — 2026-08-16 삭제.
#
# 외부 OpenAI 호환 모델에 보낼 프롬프트를 조립하던 함수이고, 유일한 소비자가
# `clients/rag_llm.complete` 였습니다. 그 계층을 절대 제약 1("LLM 유료 API 비용 0원")
# 때문에 걷어내면서 함께 지웠습니다. 남겨 두면 "부를 곳이 있다" 는 신호가 됩니다.
#
# 답변 조립은 `compose_answer()` 하나입니다 — 검색된 원문만 씁니다.

# ── 후속 질문 (R-04 · CN-128) ────────────────────────────────────────────────
#
# 강사님 요구 원문: "모르는 용어 또는 결과를 질문 → 어려운 용어를 일상어로 바꾸고,
# **확인할 질문을 제안**" (`docs/07.md:157`). 명세 4.5절이 두 갈래를 제안했고
# (`20-기능명세/06-학습과-AI.md:352~367`), 여기서 구현하는 것은 **규칙 기반 갈래**다.
# LLM 프롬프트 갈래는 반영하지 않았다 — 근거는 CN-128.
#
# ## 이 절의 한 문장
#
# **후속 질문의 낱말은 전부 검색된 원문에서 온다.** 원문이 이미 물음표로 끝나면 그대로
# 쓰고, 제목이면 `FOLLOWUP_TEMPLATE` 한 문장에 끼운다. 그 템플릿을 빼면 이 모듈이
# 저작하는 문장은 하나도 없다. `build_llm_prompt` 가 "원문에 없는 사실·숫자·
# 투자 조언을 추가하지 말고" 로 막은 것과 충돌하지 않는 이유가 이것이다 — 사실 주장을
# 만들지 않고, 원문의 항목명을 「」 로 인용해 *문서가* 무엇을 말하는지 묻는다.
#
# ## 두 가지가 이 설계를 규정한다
#
# | 사실 | 이 절이 그래서 하는 일 |
# | --- | --- |
# | 해시 임베딩은 어휘가 겹칠 때만 맞는다 (CN-015 · CN-129 · 모듈 docstring) | 질의와 어간을 공유하지 않는 후보를 **버린다**(관문). 관문의 대가는 `FOLLOWUP_POOL` 로 갚는다 |
# | 말뭉치에 실명 종목·매매 권유·계절성 낚시가 실재한다 | `FOLLOWUP_BANNED_TERMS` 9갈래로 전수 차단 |
# | 청크는 1200자 고정 절단이라 코드블록 한가운데에서 시작하고, 첫 줄이 낱말 중간에서 잘려 있다 | 제목을 `#{2,6}` 로 좁히고, 첫 청크가 아니면 첫 줄을 버린다 (`followup_candidates` 참고) |
#
# ## 관문이 없으면 이 기능은 R-04 를 못 지킨다
#
# 관문을 끄면 질의와 어휘가 하나도 안 겹치는 제안이 대부분이 된다. 그런데 제안은
# 화면에서 **클릭 가능한 버튼**이라(`ragChat.js`), 무관한 제안은 무해한 잡음이 아니라
# 사용자를 물어본 용어에서 멀어지게 하는 유도 장치다. 그래서 "무관한 3개" 보다
# "빈 배열" 을 택했다 — 빈 배열은 R-04 미충족이지만, 무관한 버튼은 R-04 역행이다.
#
# **관문의 대가와 `FOLLOWUP_POOL` 을 60 으로 고른 근거(풀 크기별 커버리지 표)는
# 변경노트 CN-128 에 한 벌만 둔다.** 같은 표를 코드 주석에 복제했더니 세 곳이 서로 다른
# 숫자를 말하게 됐다 — 세는 값을 손으로 옮겨 적지 않는다(CN-121 · CN-126과 같은 부류).
# 아래 상수를 다시 고를 사람은 그 표를 보면 된다.
#
# 60 은 **검색이 고장 나 있는 동안의 보상값**이고, CN-021(의미 검색)이 해소되면
# 낮춰야 한다.
FOLLOWUP_MAX = 3
FOLLOWUP_POOL = 60
FOLLOWUP_MIN_CHARS = 8
FOLLOWUP_MAX_CHARS = 60
FOLLOWUP_MIN_TOKENS = 3
FOLLOWUP_BARE_LEAD_TOKENS = 5
FOLLOWUP_STEM_MIN = 2
FOLLOWUP_HEAD = "검색된 문서에 있는 확인 질문"

# 「」 로 감싸는 이유는 **한국어 조사를 피하려는 것**이다. `'{h}' 는 …` 로 쓰면 받침에
# 따라 은/는이 갈리고, 제목에 이미 따옴표가 든 경우(`‘업황 피크’…`)에 겹친다.
# 말뭉치 고유 제목 중 「 를 품은 것은 0개라 충돌하지 않는다.
#
# 이 문장의 낱말은 전부 `FOLLOWUP_STOP_PREFIXES` 에 걸려 어간을 하나도 만들지 않는다
# (문서·부분·어떻·설명). 그래서 관문은 **템플릿이 아니라 제목만** 잰다. 의도한 것이다.
FOLLOWUP_TEMPLATE = "「{heading}」 — 문서는 이 부분을 어떻게 설명하나요?"

# 관문에서 뺄 어간. **의문형 어미와 범용어가 만능 일치를 만드는 것을 막는다** —
# 빼지 않으면 '무엇인가요' 하나로 아무 질문이나 통과해 관문이 무력해진다.
FOLLOWUP_STOP_PREFIXES = (
    "무엇", "어떻", "어떤", "어디", "언제", "누가", "누구", "얼마", "어느", "무슨",
    "이것", "그것", "저것", "이거", "그거", "대해", "대한", "관련", "경우",
    "문서", "설명", "항목", "알려", "자세", "정말", "그리고", "하지만",
    "있나", "있는", "있습", "있을", "없나", "없는", "없습", "되나", "되는",
    "하나", "하는", "합니", "해요", "인가", "일까", "할까", "될까", "인지",
    "왜", "좀", "저는", "제가", "내가", "우리",
    "뜻", "의미", "다른", "다르", "같은", "부분", "내용",
)

# R-07 금칙어. **정본은 여기다** — 런타임에 도는 코드가 `scripts/` 를 import 할 수는
# 없기 때문이다(계층이 뒤집힌다). `verify_r07_expressions.py` 의 `BANNED_PRODUCTS`·`BANNED_BRANDS` 두 목록은
# 그대로 두고, `verify_rag_api.py` 가 **행동으로** 대조한다 —
# 그 21개를 `followup_banned_hit()` 에 직접 먹여 전부 적중하는지 본다.
# `build_followups` 를 통해 대조하면 길이·한글 하한이 대신 걸려 검사가 공허해진다.
#
# 갈래별로 나눈 이유는 **어느 축이 비어 있는지 보이게** 하기 위해서다. ⑥ 방향 단정과
# ⑦ 타이밍은 세 설계안 중 어느 것에도 없던 축이고, 심사가 실측으로 찾아냈다 —
# `docs/11.md:64` '산타 랠리: 연말에 오른다는 말은…' 처럼 **본문이 반박하려고 세운
# 낚시 제목**이 물음표로 끝나서 최상급 재료로 승격되고 있었다.
FOLLOWUP_BANNED_TERMS = (
    # ① 실명 종목·기업·인물·운용사 (`docs/04.md:61`·`06.md:3`·`03.md:602`·`05.md:594`·`03.md:706`)
    "삼성전자", "SK하이닉스", "하이닉스", "LG전자", "현대차", "카카오", "네이버",
    "테슬라", "엔비디아", "마이크로소프트", "TSMC", "마이크론", "인텔",
    "블랙록", "CXMT", "젠슨", "한화오션",
    # ② 운용사 접두 — `verify_r07_expressions.BANNED_BRANDS` 와 같은 값
    "KODEX", "TIGER", "ACE", "KBSTAR", "ARIRANG", "HANARO", "SOL ",
    # ③ 상품 유형어. BANNED_PRODUCTS 14개 중 접두가 없는 2건
    #    ('KB국민은행 정기예금'·'예금보험 적금')을 덮는다. 말뭉치 적중 0건이라
    #    재현율 비용이 0 이다(`grep -c 정기예금\|적금\|예금보험 docs/*.md` → 0).
    "정기예금", "적금", "예금보험",
    # ④ 투자의견 — `verify_r07_expressions` 의 투자의견 금지어 + 소문자·'추천'
    "매수", "매도", "관망", "Buy", "Sell", "Hold", "BUY", "SELL", "HOLD",
    "buy", "sell", "hold", "투자 매력", "분할 접근", "권고", "추천",
    # ⑤ 1인칭 거래·주문 실행. `docs/05.md:301`('사려는')·`06.md:283`('내가 살')·
    #    `05.md:304`('주문 대신')이 여기서 죽는다. **명사(주문·지정가·시장가)는 막지
    #    않는다** — 막으면 `ragChat.js:3` 의 예시 '지정가 주문과 시장가 주문의 차이는?'
    #    가 구조적으로 0개가 된다. 막는 것은 권유 형태와 1인칭 주어다.
    "사야", "살까", "사지", "사려", "내가 살", "팔아야", "팔까", "팔아",
    "익절", "손절", "추격", "물타기", "주문을 넣", "주문 대신", "분할 매수",
    # ⑥ 방향 단정·단정 부사. R-07 이 금지한 것은 **확정적 표현**인데, 세 설계안의
    #    금칙어는 추측형('오를까')만 담고 확정형('오른다')을 비워 두고 있었다.
    "오른다", "내린다", "오릅니다", "내립니다", "상승한다", "하락한다",
    "올랐", "떨어진다", "반드시", "항상", "언제나", "무조건", "확실", "틀림없",
    "수익률", "수익을", "돈을 번",
    # ⑦ 타이밍·계절성. `docs/03.md:473`·`11.md:49`·`11.md:64` — 셋 다 본문이 반박하는데
    #    제목만 떼어 버튼으로 만들면 반박이 따라오지 않는다.
    "언제 투자", "언제 사", "몇 월", "랠리", "타이밍", "좋은 시점", "좋은 시기",
    # ⑧ 교육 운영 안내 (`docs/06.md:41~46`)
    "팀별", "팀내", "보조강사", "교육과정", "프로젝트(전체", "차 교육",
    # ⑨ 실행 매뉴얼 (`docs/07.md:289` 이후 LEAN·Docker 부록)
    "Docker", "docker", "Compose", "LEAN", "설치", "실행하기", "준비 사항",
)

_FOLLOWUP_FENCE = re.compile(r"^\s*(?:```|~~~)")
# **H1 을 일부러 뺐다.** 파이썬 주석이 정확히 `# ` 이고, 청크가 코드블록 한가운데에서
# 시작하면(178 중 5개) 펜스 추적이 뒤집혀 그 주석이 제목으로 읽힌다.
# `docs/07.md:548` 에 '# … 1주 추가 매수합니다.' 가 실재한다. H1 8줄은 전부
# `# 주식 N` 류 문서 제목이라 잃어도 후속 질문 가치가 0 이다.
_FOLLOWUP_HEADING = re.compile(r"^(#{2,6})\s+(.+?)\s*#*\s*$")
_FOLLOWUP_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_FOLLOWUP_LIST_LEAD = re.compile(r"^\s*(?:[-*+]\s+|\d+\s*[.)]\s*)")
_FOLLOWUP_NUM_LEAD = re.compile(r"^\d+\s*[.)]\s*")
_FOLLOWUP_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+")
# **여는 따옴표로 시작하는 질문만** 잡는다. `[모든따옴표]` 로 쓰면
# '‘업황 피크’라는 걱정은 무엇일까요?' 가 닫는 따옴표에서 매치돼 안전한 질문이 죽는다.
_FOLLOWUP_QUOTED_Q = re.compile(r"[\"'“‘「『][^\"'”’」』]*\?")
_FOLLOWUP_CODEISH = re.compile(r"[=;{}<>\[\]]|\]\(|https?://|www\.")
_FOLLOWUP_STOCK_CODE = re.compile(r"(?<!\d)\d{6}(?!\d)")
_FOLLOWUP_PERCENT = re.compile(r"\d\s*%")
_FOLLOWUP_KEY = re.compile(r"[^0-9a-z가-힣]")


def _followup_stems(text: str) -> set[str]:
    """관문이 쓸 어간 집합. 한국어 조사를 형태소 분석기 없이 흡수한다.

    토큰의 **모든 접두사**(2자 이상)를 넣는다. '분산투자의' → {분산, 분산투, 분산투자,
    분산투자의} 이므로 '분산투자' 와 교집합이 생긴다. `_followup_key` 같은 완전 정규화로는
    이 둘이 안 붙는다.

    `FOLLOWUP_STOP_PREFIXES` 로 시작하는 토큰은 통째로 버린다 — 접두사만 걸러서는
    '무엇인가요' 의 짧은 접두 '무엇' 을 지운 뒤 '무엇인'·'무엇인가' 가 남는다.
    """
    stems: set[str] = set()
    for token in _TOKEN_PATTERN.findall(text.lower()):
        if len(token) < FOLLOWUP_STEM_MIN:
            continue
        if token.startswith(FOLLOWUP_STOP_PREFIXES):
            continue
        for size in range(FOLLOWUP_STEM_MIN, len(token) + 1):
            stems.add(token[:size])
    return stems


def _followup_clean(raw: str) -> str:
    """마크다운 장식을 벗긴다. **낱말은 바꾸지 않는다.**

    링크는 표시 텍스트만 남기고, 백틱·강조 표기·목록 마커·번호 접두를 지운다.
    번호 접두는 버리는 게 아니라 **정규화**다 — `### 3. 물가: 왜 주식 투자자가 볼까요?`
    가 '물가: 왜 주식 투자자가 볼까요?' 로 살아난다. 말뭉치에 번호 접두 제목이 46개다.
    """
    text = _FOLLOWUP_LINK.sub(r"\1", raw)
    text = text.replace("`", "")
    text = re.sub(r"\*\*|__|~~|\*", "", text)
    text = _FOLLOWUP_LIST_LEAD.sub("", text)
    text = _FOLLOWUP_NUM_LEAD.sub("", text)
    return " ".join(text.split())


def followup_banned_hit(text: str) -> list[str]:
    """R-07 금칙어 적중 목록. **검사에서 직접 부르라고 공개했다.**

    `build_followups` 를 통해 금칙어를 시험하면 길이·한글 하한이 먼저 걸려 통과해 버려,
    금칙어 목록이 비어도 검사가 초록으로 뜬다. `verify_rag_api.py` 는 이 함수에
    `BANNED_PRODUCTS`·`BANNED_BRANDS` 21개를 직접 먹인다.
    """
    return [word for word in FOLLOWUP_BANNED_TERMS if word in text]


def followup_rejected(text: str) -> str | None:
    """후보 한 개의 거부 사유. 통과하면 `None`.

    **사유 문자열을 돌려주는 이유**는 검사와 디버깅 때문이다. `bool` 만 주면
    "왜 안 나왔나" 를 코드를 읽어 추론해야 한다.

    | 조건 | 무엇을 막나 |
    | --- | --- |
    | 길이 8~60 | 2자 제목(`배당`)과 124자 정의문(`docs/07.md:237`) |
    | 한글 3자 미만 | URL 쿼리스트링 오탐(조사 2 실측 18건) |
    | `|` | 표 셀 오염 — 질문문장의 17.5% |
    | 코드·링크 기호 | 코드 조각, `docs/07.md:291` 의 URL 제목 |
    | 큰따옴표 · 여는따옴표+물음표 | **인용 맥락 소실.** `docs/07.md:488` 이 *반박하려고* 인용한 매매 질문이 여기서 죽는다 |
    | 6자리 종목코드 | `005930` (`docs/05.md:35` 등 7곳). 기존 목록에 코드 형태가 전혀 없었다 |
    | `숫자%` | 수치 약속. `verify_r07_expressions.py:109` 의 `연 \\d+~\\d+%` 를 일반화 |
    | 금칙어 | 9갈래 (위 상수) |
    | 토큰 3개 미만 | 표 머리칸 `왜 필요한가요?`(2토큰) |
    | 의문사로 시작하며 토큰 5개 미만 | 주어 없는 파편 `무엇을 배울 수 있나요?` |

    마지막 두 줄이 갈린 것은 실측 때문이다. 토큰 하한을 일괄 5로 올리면 명세가
    "좋은 후속 질문의 모범" 으로 든 `docs/07.md:181` 의 두 문장이 함께 죽는다 —
    `빨간 신호는 무엇을 뜻하나요?`(4토큰) · `보수적 흐름은 손실 확정인가요?`(4토큰).
    차이는 길이가 아니라 **주어의 유무**라서 그것으로 갈랐다.

    ## 하한이 4가 아니라 3인 이유 — 실측으로 정했다

    설계 종합안은 4를 제시하면서 근거로 표 머리칸 `왜 필요한가요?` 를 들었는데, 그것은
    **2토큰이라 하한 3에서도 죽는다.** 4로 두면 근거가 막으려던 것이 아니라 멀쩡한
    3토큰 질문이 죽었다 — `이동평균선은 왜 볼까요?` · `양봉과 음봉은 무엇일까요?` ·
    `KOSPI는 어떻게 계산할까요?` 같은 것들이다.

    4→3 으로 낮추면 말뭉치 전수에서 후보가 **35개 늘고, 그중 금칙어·종목코드·수치
    약속 위반은 0개**다(2026-08-14 측정). 안전 비용 없이 재현율만 오르므로 3을 쓴다.
    """
    if not (FOLLOWUP_MIN_CHARS <= len(text) <= FOLLOWUP_MAX_CHARS):
        return "길이"
    if len(re.findall(r"[가-힣]", text)) < 3:
        return "한글부족"
    if "|" in text:
        return "표셀"
    if _FOLLOWUP_CODEISH.search(text):
        return "코드·링크"
    if '"' in text or "“" in text or "”" in text:
        return "따옴표"
    if _FOLLOWUP_QUOTED_Q.search(text):
        return "인용질문"
    if _FOLLOWUP_STOCK_CODE.search(text):
        return "종목코드"
    if _FOLLOWUP_PERCENT.search(text):
        return "수치약속"
    hit = followup_banned_hit(text)
    if hit:
        return f"금칙어:{hit[0]}"
    tokens = _TOKEN_PATTERN.findall(text)
    if len(tokens) < FOLLOWUP_MIN_TOKENS:
        return "토큰부족"
    if tokens[0].startswith(FOLLOWUP_STOP_PREFIXES) and len(tokens) < FOLLOWUP_BARE_LEAD_TOKENS:
        return "주어없음"
    return None


def followup_candidates(source: dict[str, Any]) -> list[tuple[int, int, str]]:
    """청크 하나에서 `(tier, 등장순서, 질문)` 후보를 뽑는다.

    tier 는 재료의 질이다 — **0: 원문 물음표 제목 · 1: 원문 물음표 문장 · 2: 제목 변환.**
    0·1 은 낱말을 하나도 더하지 않고, 2 만 `FOLLOWUP_TEMPLATE` 한 문장을 두른다.
    tier2 를 빼면 제목이 마르는 구간이 메워지지 않고, tier0·1 을 빼면 원문 그대로인
    최상급 재료가 사라진다. 말뭉치 전수 후보 수는 손으로 적지 않는다 —
    `scripts/verify_rag_api.py` 의 ⑤ 가 세어 대조하므로 바뀌면 거기서 걸린다.

    ## 코드펜스 — 이 함수의 가장 조심스러운 대목

    청크는 1200자 고정 절단이라 **코드블록 한가운데에서 시작할 수 있다**(178 중 5개:
    03.md#7 · 07.md#16·21·24 · 10.md#3). 그때 처음 만나는 ``` 는 *닫는* 펜스인데 이
    함수는 *여는* 것으로 세므로 상태가 통째로 뒤집힌다. 순수 계산층은 문서 전체를 못
    보므로 이 패리티를 알 방법이 없다.

    그래서 **패리티를 맞추는 대신, 뒤집혀도 누출이 되지 않게** 했다. 세 겹이다.

    1. 제목은 `#{2,6}` 만 — 파이썬·bash 주석의 `# ` 이 제목이 되지 못한다.
    2. 문장 후보는 `#` · `>` 로 시작하는 줄, 4칸 이상 들여쓴 줄, 코드 기호가 든 줄에서
       뽑지 않는다.
    3. 말뭉치 실측: 코드펜스 안에서 `^#{2,6} ` 인 줄 **0건**, `?` 로 끝나면서 `#` 으로
       시작하지 않는 줄 **0건**. 즉 지금 말뭉치에서는 뒤집혀도 나올 것이 없다.

    남는 것은 **누락**이다. 뒤집힌 5개 청크에서는 진짜 제목이 "펜스 안" 으로 읽혀 버려진다.
    누출과 누락 중 누락을 택했다 — R-07 화면에서 두 오류의 비용이 다르다.

    ## 절단 — 청크의 **양 끝**을 다 버린다

    청크는 1200자 고정 절단이라 **첫 줄과 마지막 줄이 낱말 중간에서 잘려 있을 수 있다.**
    양쪽 다 버린다.

    | 끝 | 조건 | 왜 |
    | --- | --- | --- |
    | 꼬리 | `order == len(lines) - 1` 인 **제목** | 반쪽만 남은 제목이 후보가 되는 것을 막는다 |
    | 머리 | `chunk_index > 0` 인 청크의 `order == 0` 줄 (제목·문장 **양쪽**) | 앞이 잘려나간 조각을 막는다 |

    **머리 가드가 꼬리보다 중요하다.** 꼬리에서 잘린 문장은 `?` 로 끝나지 못해
    `piece.endswith("?")` 가 자동으로 걸러 준다. 그런데 **머리에서 잘린 문장은 뒤가
    온전해서 물음표로 멀쩡히 끝난다** — 아무 검사에도 안 걸린다. 실제로
    `docs/06.md` 청크 2의 첫 줄이 `가도 버틸 수 있나요?` 인데, 원문은
    `가격이 많이 내려가도 버틸 수 있나요?` 이고 경계가 `내려|가도` 를 쪼갠 것이다.
    이것이 버튼으로 나가면 깨진 한국어가 화면에 뜨고, 누르면 그 조각이 새 질의가 된다.

    `chunk_index` 는 이미 인자 dict 안에 있으므로 문서별 총 청크 수를 받지 않아도 된다 —
    순수성이 유지된다. 첫 청크(`chunk_index == 0`)의 첫 줄은 문서의 진짜 시작이라 남긴다.
    """
    text = str(source.get("text") or "")
    if not text:
        return []

    try:
        chunk_index = int(source.get("chunk_index") or 0)
    except (TypeError, ValueError):
        chunk_index = 0

    lines = text.split("\n")
    out: list[tuple[int, int, str]] = []
    in_fence = False
    for order, line in enumerate(lines):
        if _FOLLOWUP_FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        # 머리 절단 — 첫 청크가 아니면 첫 줄은 앞이 잘려 있을 수 있다.
        if order == 0 and chunk_index > 0:
            continue

        stripped = line.strip()
        heading_match = _FOLLOWUP_HEADING.match(stripped)
        if heading_match:
            if order == len(lines) - 1:
                continue  # 절단 제목
            heading = _followup_clean(heading_match.group(2))
            if followup_rejected(heading):
                continue
            if heading.endswith("?"):
                out.append((0, order, heading))
            else:
                shaped = FOLLOWUP_TEMPLATE.format(heading=heading)
                if len(shaped) <= FOLLOWUP_MAX_CHARS:
                    out.append((2, order, shaped))
            continue

        # 문장 후보 — 코드로 보이는 줄은 전부 뺀다(위 ②).
        if stripped.startswith("#") or stripped.startswith(">"):
            continue
        if _FOLLOWUP_CODEISH.search(stripped) and "|" not in stripped:
            continue
        if stripped and line[:4].strip() == "":
            continue

        # `|` 는 낱말이 아니라 칸 구분자다. 쪼개는 쪽이 문장 경계를 깨는 게 아니라
        # 되살린다 — 표를 통째로 버리면 '이익과 현금이 함께 늘었나요?' 처럼
        # 가장 R-04 다운 문장들이 함께 사라진다.
        for cell in stripped.split("|"):
            for piece in _FOLLOWUP_SENT_SPLIT.split(cell):
                piece = _followup_clean(piece)
                if not piece.endswith("?"):
                    continue
                if followup_rejected(piece):
                    continue
                # `order` 는 tier 가 같을 때만 비교된다 — 순서를 가르는 것은 tier 다
                # (tier0 원문 제목 → tier1 원문 문장 → tier2 제목 변환).
                # 전에 여기 `1000 + order` 로 오프셋을 두고 "제목이 항상 앞선다" 고
                # 적어 두었는데, 둘 다 틀렸다: 오프셋을 빼도 출력이 바뀌지 않고
                # (질의 240 × 소스집합 298 전수 대조에서 불일치 0), tier2 제목은
                # order 와 무관하게 tier1 문장보다 **뒤에** 온다.
                out.append((1, order, piece))
    return out


def _followup_rank_key(source: dict[str, Any]) -> tuple[float, str, int]:
    """검색 결과를 다시 정렬할 키. **어떤 값이 와도 예외를 던지지 않는다.**

    `to_source()` 를 거친 행은 `score` 가 이미 float 이고 `chunk_index` 가 int 다.
    그래도 방어하는 이유는 `build_followups` 가 *부가물*이라서다 — 후속 질문을 못 만드는
    것은 빈 목록으로 끝나야 할 일이고, 답변까지 500 으로 끌고 내려갈 일이 아니다.
    `float("x")` 가 `ValueError` 를 던지는 것을 실제로 확인해서 넣었다(2026-08-14).
    """
    try:
        score = float(source.get("score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    try:
        index = int(source.get("chunk_index") or 0)
    except (TypeError, ValueError):
        index = 0
    return (-score, str(source.get("source_doc") or ""), index)


def build_followups(
    query: str, sources: list[dict[str, Any]], limit: int = FOLLOWUP_MAX
) -> list[str]:
    """검색된 청크에서 '확인할 질문' 을 규칙으로 고른다. 실패해도 예외를 던지지 않는다.

    입력은 `to_source()` 가 만든 dict 리스트 그대로다(`score`·`source_doc`·
    `chunk_index`·`text`). 부가물이므로 못 만들면 `[]` 이고 `RagInputError` 를 쓰지 않는다.

    ## 관문 — 질의와 어간을 하나도 공유하지 않으면 버린다

    이 한 줄이 이 기능의 성패를 가른다. 관문을 끄면 개수는 늘지만 질의와 무관한 질문이
    버튼으로 붙는다. **관문을 켠 출력은 정의상 전부 질의와 어간을 공유한다.**

    ## 순서

    `(tier, -공유어간수, 검색순위, 청크내 등장순서)` 오름차순. 넷 다 정수라 부동소수가
    순서를 흔들 여지가 없고, 마지막 둘이 전순서라 동점이 남지 않는다.
    `score` 는 **정렬 키로 쓰지 않는다** — `sources` 를 함수 안에서 다시 정렬해 순위를
    매기므로, 라우터가 준 순서가 달라도 결과가 같다.

    ## 경계

    | 상황 | 동작 | 근거 |
    | --- | --- | --- |
    | `sources` 0건 | `[]` | `ANSWER_EMPTY` 와 같은 취지. 라우터가 근거 0건에 외부 AI 를 안 부르는 자리(`routers.rag.rag_ask` 의 provider 분기)와 같은 판단 |
    | 후보 0개 | `[]`. **폴백 없음** | 억지로 채우려면 원문 밖 문장을 지어야 한다. 실측 28질의 중 6건이 빈 배열이고, 화면은 블록 자체를 안 그린다 |
    | 중복 | 정규화 키로 제거 | 겹침 200자 때문에 인접 청크 쌍의 25.3% 가 같은 제목을 공유한다(조사 1) |
    | 질의 반향 | 질의 키가 4자 이상이고 서로 포함하면 버림 | 방금 물은 것을 되돌려 주지 않는다. 4자 하한이 없으면 한 글자 질의('요')가 후보를 전멸시킨다 |
    """
    if not sources or limit <= 0:
        return []
    query_stems = _followup_stems(query)
    if not query_stems:
        return []

    ordered = sorted(sources, key=_followup_rank_key)
    scored: list[tuple[int, int, int, int, str]] = []
    for rank, source in enumerate(ordered):
        for tier, order, text in followup_candidates(source):
            shared = len(query_stems & _followup_stems(text))
            if not shared:
                continue  # ← 관문
            scored.append((tier, -shared, rank, order, text))
    scored.sort()

    # `set` 을 순회하지 않는다 — 파이썬 set 순회 순서는 해시 시드에 의존한다.
    # `dict` 는 삽입 순서를 보장하므로 중복 제거와 순서 보존을 함께 한다.
    picked: dict[str, str] = {}
    query_key = _FOLLOWUP_KEY.sub("", query.lower())
    for _tier, _shared, _rank, _order, text in scored:
        key = _FOLLOWUP_KEY.sub("", text.lower())
        if key in picked:
            continue
        if len(query_key) >= 4 and (query_key in key or key in query_key):
            continue
        picked[key] = text
        if len(picked) >= limit:
            break
    return list(picked.values())
