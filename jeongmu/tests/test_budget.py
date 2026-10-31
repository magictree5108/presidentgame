import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import budget  # noqa: E402
import llm  # noqa: E402


@pytest.fixture
def logs(tmp_path, monkeypatch):
    monkeypatch.setattr(budget, "LOGS", tmp_path)
    monkeypatch.setattr(llm, "LOGS", tmp_path)
    monkeypatch.delenv("JEONGMU_RUN_BUDGET_USD", raising=False)
    monkeypatch.delenv("MONTHLY_BUDGET_KRW", raising=False)
    budget.reset_run()
    yield tmp_path
    budget.reset_run()


def _write(path, recs, junk=False):
    lines = [json.dumps(r) for r in recs]
    if junk:
        lines.append('{"at": "2026-10-31T09:')  # 쓰다 끊긴 줄
    (path / "llm_usage.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_spent_sums_by_month_and_since(logs):
    _write(logs, [{"at": "2026-09-30T23:00:00", "cost_usd": 1.0},
                  {"at": "2026-10-01T08:00:00", "cost_usd": 0.25},
                  {"at": "2026-10-31T07:00:00", "cost_usd": 0.5}], junk=True)
    assert budget.month_spent_usd("2026-10") == 0.75
    assert budget.month_spent_usd("2026-09") == 1.0
    assert budget.spent_usd(since="2026-10-31T00:00:00") == 0.5
    assert budget.spent_usd() == 1.75


def test_run_cap_stops_and_alerts(logs, monkeypatch):
    monkeypatch.setenv("JEONGMU_RUN_BUDGET_USD", "0.01")
    budget.check("news_extract")  # 아직 0원 → 통과
    llm.log_usage("news_extract", {"input_tokens": 100_000, "output_tokens": 0}, model=llm.CHEAP_MODEL)  # $0.01
    assert budget.run_spent_usd() == pytest.approx(0.01)
    with pytest.raises(budget.BudgetExceeded):
        budget.check("news_extract")
    assert "실행 한도 도달" in (logs / "alerts.log").read_text(encoding="utf-8")


def test_monthly_cap(logs, monkeypatch):
    from datetime import date
    _write(logs, [{"at": date.today().isoformat() + "T01:00:00", "cost_usd": 10.0}])  # 약 14,000원
    monkeypatch.setenv("MONTHLY_BUDGET_KRW", "20000")
    budget.check()
    monkeypatch.setenv("MONTHLY_BUDGET_KRW", "10000")
    with pytest.raises(budget.BudgetExceeded):
        budget.check()


def test_no_cap_by_default(logs):
    llm.log_usage("x", {"input_tokens": 10_000_000}, model=llm.MODEL)  # $40
    budget.check()  # 한도 미설정이면 막지 않는다(매번 허락 원칙)


def _load_daily():
    spec = importlib.util.spec_from_file_location("daily", ROOT / "daily.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_runner(results):
    """results: 스크립트 이름 → (종료 코드, 통계 dict 또는 None)."""
    calls = []

    def run(cmd, cwd=None, env=None):
        script = Path(cmd[1]).name
        calls.append((script, cmd, env))
        code, st = results.get(script, (0, None))
        if st is not None and "--stats-out" in cmd:
            Path(cmd[cmd.index("--stats-out") + 1]).write_text(json.dumps(st), encoding="utf-8")
        return SimpleNamespace(returncode=code)
    return run, calls


def test_daily_dry_run_estimates_and_records(logs):
    daily = _load_daily()
    run, calls = _fake_runner({"news.py": (0, {"to_extract": 1000}), "polls.py": (0, {"new": 100})})
    assert daily.main([], runner=run) == 0
    news_cmd = next(c for s, c, _ in calls if s == "news.py")
    assert "--dry-run" in news_cmd
    assert [s for s, _, _ in calls] == ["update_assembly.py", "metrics.py", "heuristics.py", "news.py",
                                         "polls.py", "stances.py", "predictions.py"]
    rec = json.loads((logs / "daily_runs.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert rec["approved"] is False
    assert rec["estimate_usd"] == [0.13, 0.33]
    line = budget.one_line(rec)
    assert "뉴스 추출 대상 1000건" in line and "예상 약 182~462원" in line


def test_daily_approve_budget_stop_skips_rest(logs):
    daily = _load_daily()
    run, calls = _fake_runner({"news.py": (3, {"articles": 5, "facts": 9, "stopped_by_budget": True})})
    assert daily.main(["--approve", "--budget-krw", "300"], runner=run) == 0
    scripts = [s for s, _, _ in calls]
    assert "polls.py" not in scripts and "stances.py" in scripts  # 한도 정지 뒤 AI 단계는 건너뛰고 0원 단계는 계속
    news_env = next(e for s, _, e in calls if s == "news.py")
    assert float(news_env["JEONGMU_RUN_BUDGET_USD"]) == pytest.approx(300 / budget.KRW_PER_USD, rel=1e-4)
    rec = json.loads((logs / "daily_runs.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert rec["stopped_by_budget"] and "한도 정지" in budget.one_line(rec)
    assert "건너뜀" in (logs / "alerts.log").read_text(encoding="utf-8")


def test_daily_records_failure(logs):
    daily = _load_daily()
    run, _ = _fake_runner({"metrics.py": (1, None)})
    assert daily.main([], runner=run) == 1
    rec = json.loads((logs / "daily_runs.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert rec["failed"] == ["분석 지표"]
