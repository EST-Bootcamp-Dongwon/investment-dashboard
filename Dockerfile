FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash \
      curl \
      fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

# 로컬 이미지는 **dev 쪽**을 쓴다. 배포본(`requirements.txt`)에서 빠진 matplotlib·pykrx 가
# 여기서는 있어야 서버 렌더 차트 16곳과 시가총액 보강이 돈다. dev 파일이 배포용을
# `-r` 로 포함하므로 두 벌이 갈라지지 않는다.
COPY requirements.txt requirements-dev.txt ./
# `grep -v '^torch$'` + CPU 인덱스 2단 설치가 여기 있었다. `torch`·`diffusers`·
# `opencv-python-headless` 를 의존성에서 걷어내면서(AGENTS.md) 할 일이 없어졌다 —
# 이미지도 749.6 MB 가볍다(절대 제약 5).
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-dev.txt

COPY app/ ./app/
RUN mkdir -p app/frontend/vendor \
    && python -c "import pathlib, urllib.request; pathlib.Path('app/frontend/vendor/mermaid.min.js').write_bytes(urllib.request.urlopen('https://cdn.jsdelivr.net/npm/mermaid@11.16.0/dist/mermaid.min.js', timeout=90).read())" \
    && test -s app/frontend/vendor/mermaid.min.js
# 백테스트 실험실 라우터가 import 하는 예측 코어. LEAN 컨테이너와 같은 파일을 씁니다.
COPY lean-hyundai/hd_core.py lean-hyundai/download_price_data.py lean-hyundai/make_report.py ./lean-hyundai/
COPY docs/ ./docs/
COPY scripts/upload_docs_to_qdrant.sh ./scripts/upload_docs_to_qdrant.sh
COPY scripts/build_sidebar_partial.py ./scripts/build_sidebar_partial.py
RUN chmod +x ./scripts/upload_docs_to_qdrant.sh \
    && python ./scripts/build_sidebar_partial.py

# 비루트로 돈다 (01 검증본 5.2절). 컨테이너가 뚫렸을 때 root 로 시작하지 않게 한다.
#
# `app/generated/` 를 **여기서 미리 만들고 소유권을 넘긴다.** 그 폴더는
# `.dockerignore` 가 빼므로 이미지에 없고, `paths.ensure()` 가 쓰는 시점에 만드는데,
# 그때는 이미 appuser 라 `/app/app/` 에 mkdir 할 권한이 없다. 만들어 두지 않으면
# `/api/genai/*` · `/api/cv/*` · 백테스트 리포트 저장이 전부 조용히 실패한다.
RUN useradd --create-home --uid 1001 appuser \
    && mkdir -p /app/app/generated \
    && chown -R appuser:appuser /app/app/generated
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=10 \
    CMD curl --fail http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
