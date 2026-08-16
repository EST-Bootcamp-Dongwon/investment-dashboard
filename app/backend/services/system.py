"""서버 상태·접속자 — 도메인 계층.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦.
`main.py` 에 있던 3개 라우트의 본문과 그것이 쓰던 헬퍼·상수를 그대로 옮겼다.
HTTP 를 모른다 — 실패는 `services/errors.DomainError` 로 올리고, 상태 코드로
번역하는 일은 `main.py` 의 예외 처리기 한 곳이 맡는다.

옮기면서 계산과 문구는 건드리지 않았다. 바뀐 것은 ⓐ 요청 모델 대신 키워드 인자를
받는 것과 ⓑ `HTTPException` → `DomainError` 둘뿐이다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from time import monotonic
import os
import time

try:
    from .errors import DomainError
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services.errors import DomainError  # type: ignore


ACTIVE_VISITOR_TTL_SECONDS = 90


_active_visitors: dict[str, float] = {}


_active_visitors_lock = Lock()


def _read_cpu_times() -> tuple[int, int]:
    """Return total and idle CPU ticks from Linux procfs."""
    with open("/proc/stat", encoding="utf-8") as proc_stat:
        first_line = proc_stat.readline().split()
    values = [int(value) for value in first_line[1:]]
    total = sum(values)
    # Linux reports idle and iowait separately; both mean the CPU was not
    # executing application work for this interval.
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return total, idle


def _memory_usage() -> tuple[int, int]:
    """Return total and used memory bytes, preferring MemAvailable on Linux."""
    meminfo: dict[str, int] = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as proc_meminfo:
            for line in proc_meminfo:
                key, raw_value, *_ = line.split()
                meminfo[key.rstrip(":")] = int(raw_value) * 1024
        total = meminfo["MemTotal"]
        available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
        return total, max(total - available, 0)
    except (FileNotFoundError, KeyError, ValueError):
        page_size = os.sysconf("SC_PAGE_SIZE")
        total = os.sysconf("SC_PHYS_PAGES") * page_size
        available = os.sysconf("SC_AVPHYS_PAGES") * page_size
        return total, max(total - available, 0)


def health_check() -> dict[str, str]:
    return {"status": "ok"}


def system_resources() -> dict[str, object]:
    """Return host CPU, memory and root-disk utilization for the admin view."""
    try:
        total_before, idle_before = _read_cpu_times()
        time.sleep(0.1)
        total_after, idle_after = _read_cpu_times()
        total_delta = total_after - total_before
        idle_delta = idle_after - idle_before
        cpu_used = 0.0 if total_delta <= 0 else (1 - idle_delta / total_delta) * 100

        memory_total, memory_used = _memory_usage()
        disk = os.statvfs("/")
        disk_total = disk.f_frsize * disk.f_blocks
        disk_free = disk.f_frsize * disk.f_bavail
        disk_used = max(disk_total - disk_free, 0)

        def usage(total: int, used: int) -> dict[str, int | float]:
            percent = (used / total * 100) if total else 0.0
            return {"total_bytes": total, "used_bytes": used,
                    "free_bytes": max(total - used, 0), "used_percent": round(percent, 1)}

        return {
            "cpu": {"used_percent": round(max(0.0, min(cpu_used, 100.0)), 1),
                    "logical_cores": os.cpu_count() or 1},
            "memory": usage(memory_total, memory_used),
            "disk": usage(disk_total, disk_used),
            "disk_mount": "/",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except OSError as exc:
        raise DomainError(503, f"서버 리소스 정보를 읽을 수 없습니다: {exc}") from exc


def visitor_heartbeat(*, visitor_id: str) -> dict[str, int]:
    """Register one browser briefly and return the current active-browser count.

    This is an in-memory presence indicator, not an analytics counter. A browser
    remains active for 90 seconds after its latest heartbeat, so closed tabs
    disappear without retaining personally identifiable visit history.
    """
    now = monotonic()
    with _active_visitors_lock:
        expired = [
            visitor_id
            for visitor_id, last_seen in _active_visitors.items()
            if now - last_seen > ACTIVE_VISITOR_TTL_SECONDS
        ]
        for visitor_id in expired:
            _active_visitors.pop(visitor_id, None)
        _active_visitors[visitor_id] = now
        count = len(_active_visitors)
    return {"active_visitors": count}
