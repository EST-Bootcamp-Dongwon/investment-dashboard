"""외부 OpenAI 호환 모델 호출 — 전송 계층.

`routers/rag.py:117~160` 의 `_openai_compatible_answer` 를 옮긴 것이다. 옮긴 이유는 둘이다.

① **라우터가 외부 HTTP 를 직접 부르고 있었다.** 아키텍처 2.1절이 외부 호출을 두는
   자리는 `clients/` 다.
② **검증에서 치환할 자리가 생긴다.** F04·F28 이 시세 경계(`clients/yahoo_prices` ·
   `clients/lean_prices`)를 가짜로 바꿔 원격 왕복을 결정적으로 만든 것과 같은
   방식으로, `scripts/verify_rag_api.py` 가 이 모듈의 `complete` 를 바꿔치기해
   외부 모델 없이 `provider='openai_compatible'` 경로를 밟는다.
   CN-104 가 남긴 문장 그대로다 — **검증과 구조는 번갈아 서로를 가능하게 한다.**

`supabase_client.py` 와 같은 규칙을 지킨다: `HTTPException` 을 던지지 않고 표준
라이브러리 `urllib` 만 쓴다(Vercel 500MB 상한 · D-10).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

_TIMEOUT_SECONDS = 30


class RagLlmError(Exception):
    """외부 모델 호출 실패. 라우터가 502 로 번역한다."""


class RagLlmNotConfigured(RagLlmError):
    """`RAG_LLM_API_KEY`·`RAG_LLM_MODEL` 이 없다. 라우터가 503 으로 번역한다.

    `SupabaseNotConfigured` 와 달리 상위 예외와 **다른 HTTP 코드로 번역된다.**
    미설정은 "이 서버는 그 기능을 안 켰다"(503)이고 호출 실패는 "남의 서버가
    말썽이다"(502)라, 사용자가 기다려서 될 일인지가 다르다.
    """


def is_configured() -> bool:
    """두 환경변수가 다 있는지. 화면이 선택지를 켤지 정하는 데 쓴다."""
    return bool(os.getenv("RAG_LLM_API_KEY") and os.getenv("RAG_LLM_MODEL"))


def complete(prompt: str) -> str:
    """프롬프트를 보내고 답변 문장을 받는다.

    프롬프트를 **여기서 만들지 않는다** — 조립은 `services/rag.build_llm_prompt` 다.
    이 모듈은 보내고 받기만 한다.
    """
    api_key = os.getenv("RAG_LLM_API_KEY")
    model = os.getenv("RAG_LLM_MODEL")
    base_url = (os.getenv("RAG_LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    if not (api_key and model):
        raise RagLlmNotConfigured(
            "외부 AI를 사용하려면 RAG_LLM_API_KEY와 RAG_LLM_MODEL을 설정하세요."
        )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "당신은 제공된 RAG 문서만 다듬어 설명하는 도우미입니다."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
        answer = str(result.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
    except urllib.error.HTTPError as exc:
        # 외부 응답 원문을 그대로 흘리지 않는다. 옛 코드는 200자를 잘라 detail 에
        # 실었는데(`routers/rag.py:158`), 남의 서버 오류 본문에 우리 키가 되비쳐
        # 나오는 경우가 있다. 상태 코드만 남긴다.
        raise RagLlmError(f"외부 AI 응답 오류({exc.code})") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RagLlmError(f"외부 AI 에 연결하지 못했습니다: {exc}") from exc
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise RagLlmError("외부 AI 응답을 읽을 수 없습니다.") from exc

    if not answer:
        raise RagLlmError("외부 AI 가 빈 답변을 돌려주었습니다.")
    return answer
