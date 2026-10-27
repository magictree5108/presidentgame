"""경로와 .env 설정. 외부 패키지 없이 .env를 읽는다."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
LOGS = DATA / "logs"
DOCS = ROOT / "docs"

ASSEMBLY_DB = DATA / "assembly.sqlite"
METRICS_DB = DATA / "metrics.sqlite"
PREDICTIONS_DB = DATA / "predictions.sqlite"
NEWS_DB = DATA / "news.sqlite"

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


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default
