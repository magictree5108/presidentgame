"""매일 새벽 예약 실행용: 국회 데이터 증분 갱신 → 지표 → 경험칙 검증 → 뉴스 동향 → 예측 채점.
사용: python daily.py   (실패한 단계는 이름을 출력한다)
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
STEPS = [
    ("국회 데이터", ["src/update_assembly.py"]),
    ("분석 지표", ["src/metrics.py"]),
    ("경험칙 검증", ["src/heuristics.py"]),
    ("뉴스 동향", ["src/news.py", "collect"]),
    ("예측 채점", ["src/predictions.py", "score"]),
]
failed = []
for name, cmd in STEPS:
    print(f"== {name}", flush=True)
    r = subprocess.run([sys.executable, *cmd], cwd=ROOT)
    if r.returncode != 0:
        failed.append(name)
print("완료" if not failed else f"실패한 단계: {', '.join(failed)}")
sys.exit(1 if failed else 0)
