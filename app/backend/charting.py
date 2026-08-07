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
합쳐야 한다.
"""
from __future__ import annotations

from pathlib import Path

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
