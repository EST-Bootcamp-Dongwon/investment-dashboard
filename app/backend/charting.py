"""Matplotlib 차트에 한글 폰트를 적용하는 공용 헬퍼.

## 이 모듈이 생긴 이유

강사님 원본에서 `routers/quant.py` 는 `configure_matplotlib_korean_font(plt)` 를
5곳에서 호출하지만 **어디에서도 import 하지 않는다.** 이 함수는 `main.py` 와
`routers/ml.py` 가 각자 따로 정의하고 있어서, `quant.py` 의 네임스페이스에는
존재하지 않는다. 그 결과 아래 다섯 엔드포인트가 호출 즉시 `NameError` 로
500 을 반환한다.

    POST /api/quant/backtest
    POST /api/quant/portfolio
    POST /api/quant/financial-knowledge
    POST /api/quant/risk
    POST /api/quant/pipeline

`quant.py` 를 그대로 두면 백테스트·포트폴리오 최적화·리스크 분석이 전부 죽은
상태가 되므로, 정의를 이 모듈로 옮기고 `quant.py` 가 import 하도록 고쳤다.
자세한 내용은 저장소 루트의 NOTICE.md 를 참고한다.

## v2.0 에서 할 일

`main.py` 와 `routers/ml.py` 에도 같은 함수의 사본이 각각 남아 있다. 동작에는
문제가 없어 v1.0 에서는 건드리지 않았지만, 설계 정리 단계에서 이 모듈 하나로
합쳐야 한다. **→ 2026-08-16 CN-066 이 정리했다. 지금 정의는 이 모듈 하나뿐이다.**

## `require_matplotlib()` — matplotlib 이 없는 환경이 생겼다 (2026-08-17)

Vercel 배포본에는 **matplotlib 이 들어가지 않는다.** 500MB 한도 안에 들어가려면
빼야 하고, 그 결정과 실측은 [배포-전략 3절](../../docs/spec/60-운영/배포-전략.md#3-500-mb-안에-들어가는가--cn-019-의-확인-필요-해소)
에 있다. 그래서 이 저장소에는 **차트를 그릴 수 있는 환경과 없는 환경이 둘 다** 생겼다.

조치를 안 하면 없는 쪽에서 `ModuleNotFoundError` 가 그대로 올라가 **500** 이 되고,
화면에는 `오류: Internal Server Error` 만 뜬다. 사용자가 할 수 있는 일이 없는 문구다.
`routers/backtest_lab.py:139` 가 `hd_core` 를 못 불렀을 때 이미 같은 문제를 다르게
풀어 두었다 — **503 과 함께 무엇을 해야 하는지 알려 준다.** 그 형태를 따른다.

`require_matplotlib()` 는 겸사겸사 **네 줄짜리 준비 코드를 한 줄로** 만든다. 차트 함수
16곳이 전부 이렇게 시작하고 있었다.

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    configure_matplotlib_korean_font(plt)

`gridspec`·`patches` 는 각자 import 한 채로 둔다 — `import matplotlib` 이 통과한
뒤라면 그 둘은 실패하지 않으므로, 가드가 필요한 것은 **맨 앞 한 줄**뿐이다.
"""
from __future__ import annotations

from pathlib import Path

try:
    from .services.errors import DomainError
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services.errors import DomainError  # type: ignore

# 폰트 등록은 프로세스마다 한 번이면 충분하다. 요청마다 다시 하면
# font_manager 스캔 비용이 반복된다.
_FONT_CONFIGURED = False

# 컨테이너 이미지에 설치되는 순서대로 시도한다 (Dockerfile 이 fonts-nanum 을 넣는다).
_FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
    Path("/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
)


def configure_matplotlib_korean_font(plt) -> None:
    """설치된 한글 폰트를 Matplotlib 기본 글꼴로 지정한다.

    한글 폰트가 하나도 없으면 글꼴은 그대로 두고 음수 기호 설정만 적용한다.
    (라벨이 네모로 깨질 뿐 차트 생성 자체는 실패하지 않는다.)
    """
    global _FONT_CONFIGURED
    if _FONT_CONFIGURED:
        return

    import matplotlib.font_manager as fm

    for font_path in _FONT_CANDIDATES:
        if font_path.exists():
            fm.fontManager.addfont(str(font_path))
            plt.rcParams["font.family"] = fm.FontProperties(fname=str(font_path)).get_name()
            break

    # 한글 글꼴은 유니코드 마이너스를 갖지 않는 경우가 많아 ASCII 하이픈을 쓰게 한다.
    plt.rcParams["axes.unicode_minus"] = False
    _FONT_CONFIGURED = True


# 배포본에서 차트를 부르면 이 문장이 화면에 그대로 나간다. **무엇을 해야 하는지까지**
# 적는다 — "사용할 수 없습니다" 만 적으면 사용자가 다음에 할 일을 모른다.
CHART_UNAVAILABLE = (
    "이 차트는 로컬 전용입니다. 배포본에는 그림을 그리는 라이브러리(matplotlib)가 "
    "들어 있지 않습니다. 저장소를 내려받아 `docker compose up` 으로 열면 보입니다."
)


def require_matplotlib(*, korean_font: bool = True):
    """Agg 백엔드까지 준비된 `pyplot` 을 돌려준다.

    matplotlib 이 없는 환경(=배포본)에서는 `DomainError(503)` 을 던진다.
    `ModuleNotFoundError` 를 그대로 올려보내면 500 이 되고, 500 은 화면에서
    "서버가 고장났다" 로 읽힌다. 여기서는 **환경이 그런 것**이지 고장이 아니다.

    `korean_font=False` 는 `services/ml_charts.py` 다섯 곳뿐이다. 그쪽 차트는 축·범례가
    전부 영문이라 원래 폰트를 지정하지 않았고(`routers/ml.py:23~29` 가 사본을 지운 근거),
    여기서 한글 글꼴을 걸면 **없던 서체 변경이 생긴다.** 가드를 붙이는 작업이
    그림을 바꾸면 안 된다.
    """
    try:
        import matplotlib
    except ModuleNotFoundError as exc:
        raise DomainError(503, CHART_UNAVAILABLE) from exc

    # 서버에는 디스플레이가 없다. `pyplot` 을 import 하기 전에 걸어야 한다.
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if korean_font:
        configure_matplotlib_korean_font(plt)
    return plt
