"""열린국회정보 Open API 클라이언트.

- 요청 간격 최소 1초(수집 예절)
- 응답은 data/cache/assembly/ 에 저장해 같은 요청을 반복하지 않는다
- 응답 형식: {"<코드>": [{"head": [{"list_total_count": N}, {"RESULT": {...}}]}, {"row": [...]}]}
  데이터가 없으면 {"RESULT": {"CODE": "INFO-200", ...}} 형태로 온다.
"""
import hashlib
import json
import time
from pathlib import Path

import requests

from config import CACHE, env

BASE = "https://open.assembly.go.kr/portal/openapi/"
# 브라우저 식별 헤더가 없으면 서버가 "Bad Request."로 거절한다(2026-10-28 확인)
HEADERS = {"User-Agent": "Mozilla/5.0 (jeongmu research tool)", "Accept": "application/json"}
MIN_INTERVAL = 1.0
_last_call = 0.0


class AssemblyAPIError(RuntimeError):
    pass


def _cache_path(service: str, params: dict) -> Path:
    key = json.dumps(params, sort_keys=True, ensure_ascii=False)
    h = hashlib.sha1(key.encode()).hexdigest()[:16]
    return CACHE / "assembly" / service / f"{h}.json"


def call(service: str, params: dict | None = None, *, page: int = 1, size: int = 1000,
         use_cache: bool = True, retries: int = 6) -> tuple[list[dict], int]:
    """한 페이지를 가져온다. (rows, 전체 건수) 반환."""
    global _last_call
    key = env("ASSEMBLY_API_KEY")
    if not key:
        raise AssemblyAPIError("ASSEMBLY_API_KEY가 .env에 없습니다. docs/keys.md 참고.")
    q = {"Type": "json", "pIndex": page, "pSize": size, **(params or {})}
    cp = _cache_path(service, q)
    if use_cache and cp.exists():
        data = json.loads(cp.read_text(encoding="utf-8"))
    else:
        for attempt in range(retries):
            wait = MIN_INTERVAL - (time.time() - _last_call)
            if wait > 0:
                time.sleep(wait)
            _last_call = time.time()
            try:
                r = requests.get(BASE + service, params={"KEY": key, **q}, headers=HEADERS, timeout=60)
                r.raise_for_status()
                data = r.json()
                break
            except (requests.RequestException, ValueError) as e:
                if attempt == retries - 1:
                    raise AssemblyAPIError(f"{service} 요청 실패: {e}") from e
                time.sleep(2 ** (attempt + 1))
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return parse(service, data)


def parse(service: str, data: dict) -> tuple[list[dict], int]:
    if "RESULT" in data:  # 데이터 없음 또는 오류
        code = data["RESULT"].get("CODE", "")
        if code == "INFO-200":
            return [], 0
        raise AssemblyAPIError(f"{service}: {data['RESULT']}")
    body = data.get(service)
    if not body:
        raise AssemblyAPIError(f"{service}: 예상하지 못한 응답 {str(data)[:200]}")
    head = body[0]["head"]
    total = head[0].get("list_total_count", 0)
    result = head[1]["RESULT"]
    if result.get("CODE") not in ("INFO-000", None):
        raise AssemblyAPIError(f"{service}: {result}")
    rows = body[1]["row"] if len(body) > 1 else []
    return rows, total


def fetch_all(service: str, params: dict | None = None, *, size: int = 1000,
              use_cache: bool = True, max_pages: int = 10000):
    """모든 페이지를 차례로 내보낸다."""
    page = 1
    seen = 0
    while page <= max_pages:
        # 마지막 페이지는 데이터가 늘었을 수 있으므로 캐시를 쓰지 않는다
        rows, total = call(service, params, page=page, size=size, use_cache=use_cache)
        if seen + len(rows) >= total and use_cache:
            rows, total = call(service, params, page=page, size=size, use_cache=False)
        yield from rows
        seen += len(rows)
        if not rows or seen >= total:
            return
        page += 1
