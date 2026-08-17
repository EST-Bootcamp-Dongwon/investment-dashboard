"""생성 산출물이 어디에 떨어지는가 — **한 곳에서 정한다.**

## 왜 생겼나 — 서버리스는 `/tmp` 말고 전부 읽기 전용이다

[배포-전략 5절](../../docs/spec/60-운영/배포-전략.md#5-콜드-스타트에서-죽는-코드--cn-017-구체화)
이 `mkdir` 세 곳을 세고 위험도를 갈랐다. 그중 하나가 **모듈 import 시점**에
디렉터리를 만들고 있었다.

    routers/ml.py:19~20   GENERATED_DIR = ROOT/app/generated ; .mkdir(...)   ← import 시점

`main.py` 가 `ml.py` 를 import 하므로, 이 한 줄이 실패하면 **앱 전체가 안 뜬다.**
라우터 하나가 못 뜨는 것이 아니라 `/api/health` 까지 같이 죽는다. 서버리스 파일시스템은
`/tmp` 를 빼면 읽기 전용이라 이것이 첫 배포에서 그대로 터질 자리였다.

`routers/backtest_lab.py:336` 은 처음부터 옳게 되어 있었다 — 요청을 처리하는 중에,
`try/except OSError` 안에서 만든다. **이 파일은 그 형태를 규칙으로 굳힌 것이다.**

## 두 겹으로 막는다

| 겹 | 무엇 | 없으면 |
| --- | --- | --- |
| ① `GENERATED_DIR` 환경변수 | Vercel 에서 `/tmp/generated` 로 돌린다 (`vercel.json`) | 쓰기가 실패한다 |
| ② import 시점에 `mkdir` 하지 않는다 | 만드는 일은 `ensure()` 가 쓰는 시점에 한다 | **앱이 안 뜬다** |

②가 없으면 ①을 **한 번 잊는 순간 앱이 통째로 죽는다.** 설정 실수의 대가가
"기능 하나 실패" 여야지 "전면 장애" 가 되면 안 된다. 그래서 기본값을 `/tmp` 로
바꾸지 않고 저장소 경로로 두었다 — 로컬·Docker 의 동작을 바꾸지 않으면서, 배포에서는
①이 경로를 옮기고 ②가 안전망이 된다.

## 로컬에서는 아무것도 달라지지 않는다

기본값이 예전 그대로(`<저장소>/app/generated`)다. `.dockerignore` 가 이 폴더를
제외하고 있는 것도, `/files/{name}` 이 여기서 파일을 읽는 것도 그대로다.
"""

from __future__ import annotations

import os
from pathlib import Path

# `paths.py` → `backend` → `app` → 저장소 루트.
ROOT_DIR = Path(__file__).resolve().parents[2]

_DEFAULT = ROOT_DIR / "app" / "generated"

# 환경변수는 **import 시점에 한 번** 읽는다. `main.py` 가 라우터를 부르기 전에
# `.env` 를 이미 실었고, Vercel 은 프로세스 환경에 넣어 준다.
GENERATED_DIR = Path(os.environ["GENERATED_DIR"]) if os.environ.get("GENERATED_DIR") else _DEFAULT


def ensure(subdir: str = "") -> Path:
    """쓰기 직전에 디렉터리를 만들고 경로를 준다. **import 시점에 부르지 않는다.**

    `OSError` 를 삼키지 않는다 — 부르는 쪽이 "저장만 건너뛴다" 와 "요청이 실패한다"
    중 무엇인지 알고 있고, 여기서 정할 일이 아니다.
    """
    target = GENERATED_DIR / subdir if subdir else GENERATED_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def describe(path: Path) -> str:
    """응답에 실을 경로 문자열.

    저장소 안이면 상대경로(`app/generated/…`)로 짧게, 밖이면(`/tmp/…`) 절대경로
    그대로 준다. **`Path.relative_to` 는 밖이면 `ValueError` 를 던진다** — 경로를
    `/tmp` 로 옮기는 순간 그 예외가 `OSError` 가드를 그냥 지나쳐 500 이 된다.
    이 함수가 있는 이유가 그 한 줄이다.
    """
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)
