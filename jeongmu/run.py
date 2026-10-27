"""한 줄 실행: python run.py  → 브라우저에서 http://127.0.0.1:8000"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import uvicorn

if __name__ == "__main__":
    print("정무상황실: http://127.0.0.1:8000  (끄려면 Ctrl+C)")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, app_dir=str(Path(__file__).parent / "src"))
