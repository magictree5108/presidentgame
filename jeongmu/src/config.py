"""경로와 .env 설정. 외부 패키지 없이 .env를 읽는다."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
LOGS = DATA / "logs"
DOCS = ROOT / "docs"


# 22대 국회 임기 시작일
TERM_START = "2024-05-30"
AGE = 22
TOTAL_SEATS = 300


def load_env(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()


# 테스트·시연용으로 DB 위치를 바꿀 수 있다(JEONGMU_DB_DIR)
_DBDIR = Path(os.environ["JEONGMU_DB_DIR"]) if os.environ.get("JEONGMU_DB_DIR") else DATA
ASSEMBLY_DB = _DBDIR / "assembly.sqlite"
METRICS_DB = _DBDIR / "metrics.sqlite"
PREDICTIONS_DB = _DBDIR / "predictions.sqlite"
NEWS_DB = _DBDIR / "news.sqlite"
METRICS_JSON = _DBDIR / "metrics"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default
