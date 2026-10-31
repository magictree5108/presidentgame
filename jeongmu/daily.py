"""매일 실행 묶음(로드맵 A): 국회 데이터 → 지표 → 경험칙 → 뉴스 → 여론조사 기사 → 쟁점 입장 기록 → 예측 채점.

비용이 드는 AI 추출(뉴스·여론조사)은 매번 사용자 허락이 있어야 한다(2026-10-28 지시, 2026-10-31 '매번 허락 유지' 재확인).
예약 실행은 아직 등록하지 않는다(2026-10-31 사용자 결정).
  python daily.py                          # 0원: AI 없는 단계 + 뉴스·여론조사 대상 건수와 예상 비용
  python daily.py --approve                # 허락받은 경우에만: AI 추출까지
  python daily.py --approve --budget-krw 300   # 이번 실행 상한. 닿으면 그 자리에서 멈추고 알림
실행마다 data/logs/daily_runs.jsonl 에 한 줄 기록, 한도 정지는 data/logs/alerts.log 에도 남는다.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

import budget  # noqa: E402

# 건당 예상 단가(달러): 하한은 실측(Haiku), 상한은 여유
NEWS_PER = (0.00012, 0.0003)
POLLS_PER = (0.0001, 0.0003)
BUDGET_EXIT = 3  # news.py / polls.py 가 한도로 멈췄을 때의 종료 코드


def plan(approve: bool, tmp: Path) -> list[tuple[str, list[str], str | None]]:
    """(이름, 명령, 통계 파일 키) 목록."""
    dry = [] if approve else ["--dry-run"]
    return [
        ("국회 데이터", ["src/update_assembly.py"], None),
        ("분석 지표", ["src/metrics.py"], None),
        ("경험칙 검증", ["src/heuristics.py"], None),
        ("뉴스 동향", ["src/news.py", "collect", *dry, "--stats-out", str(tmp / "news.json")], "news"),
        ("여론조사 기사", ["src/polls.py", "collect", *dry, "--stats-out", str(tmp / "polls.json")], "polls"),
        ("쟁점 입장 기록", ["src/stances.py"], None),
        ("예측 채점", ["src/predictions.py", "score"], None),
    ]


def estimate(news: dict, polls: dict) -> tuple[float, float]:
    n, p = news.get("to_extract", 0), polls.get("new", 0)
    return (round(n * NEWS_PER[0] + p * POLLS_PER[0], 4), round(n * NEWS_PER[1] + p * POLLS_PER[1], 4))


def main(argv=None, runner=subprocess.run) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--approve", action="store_true", help="사용자 허락을 받은 경우에만: AI 추출 실행")
    ap.add_argument("--budget-krw", type=float, help="이번 실행 AI 비용 상한(원). 닿으면 정지")
    a = ap.parse_args(argv)

    started = datetime.now().isoformat(timespec="seconds")
    cap_usd = a.budget_krw / budget.KRW_PER_USD if a.budget_krw else None
    failed, stats, stopped = [], {}, False
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name, cmd, key in plan(a.approve, tmp):
            print(f"== {name}", flush=True)
            envv = dict(os.environ)
            if key and a.approve and cap_usd is not None:
                left = cap_usd - budget.spent_usd(since=started)
                if left <= 0 or stopped:
                    budget.alert(f"실행 한도 {a.budget_krw:.0f}원 소진 → '{name}' AI 추출 건너뜀")
                    stopped = True
                    continue
                envv["JEONGMU_RUN_BUDGET_USD"] = f"{left:.6f}"
            r = runner([sys.executable, *cmd], cwd=ROOT, env=envv)
            if key and (tmp / f"{key}.json").exists():
                stats[key] = json.loads((tmp / f"{key}.json").read_text(encoding="utf-8"))
            if r.returncode == BUDGET_EXIT:
                stopped = True
            elif r.returncode != 0:
                failed.append(name)

    stances_issues = None
    sp = ROOT / "data" / "stances.json"
    if sp.exists() and "쟁점 입장 기록" not in failed:
        try:
            stances_issues = len(json.loads(sp.read_text(encoding="utf-8")).get("issues", {}))
        except (json.JSONDecodeError, OSError):
            pass

    summary = {
        "date": date.today().isoformat(), "started": started,
        "finished": datetime.now().isoformat(timespec="seconds"),
        "approved": a.approve, "budget_krw": a.budget_krw,
        "news": stats.get("news", {}), "polls": stats.get("polls", {}),
        "stances_issues": stances_issues,
        "cost_usd": budget.spent_usd(since=started),
        "month_usd": budget.month_spent_usd(),
        "estimate_usd": estimate(stats.get("news", {}), stats.get("polls", {})),
        "stopped_by_budget": stopped, "failed": failed,
    }
    print("요약:", budget.record_run(summary))
    if not a.approve:
        print("AI 추출은 하지 않았습니다. 위 예상 비용으로 허락받은 뒤 `python daily.py --approve` 로 실행하세요.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
