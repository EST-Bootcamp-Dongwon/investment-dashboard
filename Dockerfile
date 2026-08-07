FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash \
      curl \
      fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    grep -v '^torch$' requirements.txt > requirements.nogpu.txt \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r requirements.nogpu.txt

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

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=10 \
    CMD curl --fail http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
