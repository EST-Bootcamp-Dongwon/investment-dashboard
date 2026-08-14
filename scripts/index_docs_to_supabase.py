#!/usr/bin/env python3
"""`docs/*.md` 를 Supabase `doc_chunk` 에 색인한다. **F27 색인의 정본이다.**

`scripts/upload_docs_to_qdrant.sh` 를 대체한다 (D-08 · CN-021). Qdrant 컬렉션
`investment_docs` 가 하던 일을 pgvector 테이블이 받는다.

## 관리자 화면이 있는데 왜 스크립트가 정본인가

`POST /api/admin/rag/reindex` 로도 같은 일을 할 수 있다. 그래도 이쪽이 정본인 이유는
**서버가 없어도 돌아야 하기 때문**이다 — 새 환경에 처음 배포할 때는 색인이 0행이고,
그 상태에서는 화면이 "문서 색인 필요" 배지만 띄운다. 관리자가 로그인해서 버튼을 누르려면
그 전에 계정과 `app_admin` 행이 있어야 하는데, 그것도 아직 없다. 최초 적재는 사람이
service_role 키로 직접 하는 것 말고 방법이 없다.

**같은 `services.rag.build_chunks` 를 쓴다.** 두 경로가 따로 자르면 색인 경로에 따라
같은 문서가 다르게 들어간다.

## 임베딩은 해시(384)다

`gemini-embedding-001`(768)이 ERD 4.3절의 채택안이지만 사용자가 Gemini 키를 쓰지 않기로
결정했고(2026-08-14), 검색은 `match_doc_chunk_hash` 를 탄다(마이그레이션 20260814120100).
**의미 검색이 아니라 어휘 일치**라는 한계는 그대로다(CN-015).

## 실행

    .venv/bin/python scripts/index_docs_to_supabase.py            # 전량
    .venv/bin/python scripts/index_docs_to_supabase.py --doc 07.md
    .venv/bin/python scripts/index_docs_to_supabase.py --dry-run  # DB 를 건드리지 않음

저장소 루트의 `.env` 에서 `SUPABASE_URL`·`SUPABASE_SERVICE_ROLE_KEY` 를 읽는다.
`--dry-run` 은 키 없이도 돌아간다 — 몇 청크가 나오는지만 세어 본다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app" / "backend"))


def load_dotenv(path: Path) -> None:
    """`.env` 를 읽어 환경변수에 넣는다. 검증 스크립트 4벌과 같은 함수다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(ROOT / ".env")

from clients import doc_chunk_repo, supabase_client  # noqa: E402
from services import rag as service  # noqa: E402

# `glob("*.md")` 는 비재귀다. `docs/spec/` 45개는 색인에서 빠진다 — 의도된 제외이고,
# 말뭉치는 투자 상식 문서이지 명세서가 아니다.
DOCS_DIR = Path(os.getenv("DOCS_DIR") or (ROOT / "docs"))


def main() -> int:
    parser = argparse.ArgumentParser(description="docs/*.md 를 Supabase doc_chunk 에 색인")
    parser.add_argument("--doc", default=None, help="이 파일만 색인 (예: 07.md)")
    parser.add_argument("--dry-run", action="store_true", help="자르기만 하고 저장하지 않음")
    args = parser.parse_args()

    if not DOCS_DIR.is_dir():
        print(f"[ERROR] 문서 폴더가 없습니다: {DOCS_DIR}")
        return 1

    files = sorted(DOCS_DIR.glob("*.md"))
    if args.doc:
        files = [path for path in files if path.name == args.doc]
        if not files:
            print(f"[ERROR] 색인 대상 문서가 아닙니다: {args.doc}")
            return 1
    if not files:
        print(f"[ERROR] markdown 파일이 없습니다: {DOCS_DIR}")
        return 1

    if not args.dry_run and not supabase_client.is_configured():
        # 막다른 길로 만들지 않는다 — 무엇을 해야 하는지까지 적는다.
        print(
            "[ERROR] SUPABASE_URL · SUPABASE_SERVICE_ROLE_KEY 가 없습니다.\n"
            f"        저장소 루트의 .env 에 두 값을 넣고 다시 실행하세요 ({ROOT / '.env'}).\n"
            "        키를 확인하려면: Supabase 대시보드 → Project Settings → API"
        )
        return 1

    print(f"[INFO] 문서 {len(files)}개 · 청킹 {service.CHUNK_SIZE}자 / 겹침 {service.CHUNK_OVERLAP}자")
    print(f"[INFO] 임베딩 {service.EMBED_METHOD} · {service.EMBED_DIM}차원")
    if args.dry_run:
        print("[INFO] --dry-run — DB 를 건드리지 않습니다")

    total = 0
    max_tokens = 0
    for path in files:
        rows = service.build_chunks(path.name, path.read_text(encoding="utf-8"))
        tokens = max((int(row["token_count"]) for row in rows), default=0)
        max_tokens = max(max_tokens, tokens)

        if args.dry_run:
            inserted = len(rows)
        else:
            try:
                inserted = doc_chunk_repo.replace_document(path.name, rows)
            except supabase_client.SupabaseError as exc:
                # 어디서 멈췄는지 남긴다. 이 문서만 색인이 빈 상태일 수 있고,
                # 다시 돌리면 복구된다 (원본은 저장소에 그대로 있다).
                print(f"[ERROR] {path.name} 색인 실패: {exc}")
                print(f"[ERROR] 이 문서는 색인이 비었을 수 있습니다. 다시 실행하세요.")
                return 1

        total += inserted
        print(f"  {path.name:<12} {inserted:>4} 청크 (최대 토큰 {tokens})")

    print(f"[OK] 총 {total} 청크 · 최대 토큰 {max_tokens}")

    # Gemini 로 옮길 때를 위한 관찰값이다. 상한 2,048 은 Gemini 의 토큰 기준이고
    # 여기 값은 정규식 토큰 수라 서로 다르다 — 크기 감각으로만 읽는다 (ERD 8절 미결 1).
    if max_tokens > 2048:
        print(f"[WARN] 최대 토큰 {max_tokens} 이 2,048 을 넘습니다. Gemini 로 옮길 때 CHUNK_SIZE 를 낮춰야 할 수 있습니다.")

    if not args.dry_run:
        print(f"[OK] 저장소 합계 {doc_chunk_repo.total_chunks()} 청크")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
