"""매일 실행용: 국회 데이터 증분 갱신 → 지표 → 경험칙 검증 → 뉴스(비용 추정만) → 예측 채점. 모두 0원.

비용이 드는 뉴스 AI 추출은 사용자 허락이 있어야 한다(2026-10-28 사용자 지시).
  python daily.py              # 0원 단계만 실행하고, 뉴스는 대상 건수·예상 비용만 출력
  python daily.py --approve    # 허락받은 경우에만: 뉴스 AI 추출까지 실행
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
STEPS = [
    ("국회 데이터", ["src/update_assembly.py"]),
    ("분석 지표", ["src/metrics.py"]),
    ("경험칙 검증", ["src/heuristics.py"]),
    ("뉴스 동향", ["src/news.py", "collect"] + ([] if "--approve" in sys.argv else ["--dry-run"])),
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
