"""Vercel Python Function 진입점.

## 왜 이 파일이 따로 있는가

Vercel 은 저장소 루트의 **`api/` 폴더**에 있는 파이썬 파일을 함수로 만든다. 앱 정본은
`app/backend/main.py` 이고 거기 있는 `app` 을 그대로 내보내는 것이 이 파일의 전부다.
로직을 여기 두지 않는다 — 두면 "로컬에서는 되는데 배포본에서는 다르다" 가 시작된다.

    로컬·Docker :  uvicorn app.backend.main:app     (Dockerfile CMD)
    Vercel      :  api/index.py 의 `app`            (이 파일)

**같은 객체다.** 미들웨어·라우터·예외 처리기가 한 벌뿐이라는 뜻이다.

## `sys.path` 를 손대는 이유

`app/backend/main.py` 는 패키지 안의 모듈이라 `app.backend.main` 으로 부를 수 있어야
한다. Vercel 함수의 작업 디렉터리는 프로젝트 루트이지만 `sys.path` 에 들어 있다는
보장이 없어서, 루트를 명시적으로 얹는다. `__init__.py` 유무에 기대지 않으려고
`importlib` 이 아니라 경로 + 일반 import 를 쓴다.

## 정적 파일은 이 함수를 지나지 않는다

`main.py:185` 의 `app.mount("/", StaticFiles(...))` 는 **로컬에서만** 일한다.
Vercel 에서는 `vercel.json` 의 `outputDirectory` 가 `app/frontend/` 를 CDN 에 얹고,
`/api/*` 만 이 함수로 온다(배포-전략 4.2절). `styles.css` 한 장까지 파이썬 함수를
깨우면 콜드 스타트와 실행 시간을 그냥 태우기 때문이다.

그래서 이 파일에서 mount 를 지우지 않는다 — **지우면 로컬이 깨진다.** 배포본에서는
그 라우트에 요청이 도달하지 않을 뿐이다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.backend.main import app  # noqa: E402

# Vercel 의 Python 런타임이 이 이름을 찾는다. 재할당이 아니라 재노출이다.
__all__ = ["app"]
