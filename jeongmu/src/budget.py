"""AI 비용 공통 장치(로드맵 A): 사용량 합산, 한도 검사, 알림, 실행 요약 1줄 기록.

- 사용량은 llm.py 가 남기는 호출 로그 data/logs/llm_usage.jsonl 을 합산한다(별도 장부 없음).
- 한도 두 가지(둘 다 선택, 기본은 없음):
  · 실행 한도: 환경변수 JEONGMU_RUN_BUDGET_USD — 이 프로세스에서 쓴 비용이 닿으면 다음 호출 전에 멈춘다.
    daily.py --budget-krw N 이 단계마다 남은 금액을 계산해 넣어 준다.
  · 월 한도: .env 의 MONTHLY_BUDGET_KRW — 이번 달 누적이 닿으면 멈춘다.
    현재 운영 원칙은 '매번 허락'(2026-10-31 사용자 결정)이라 설정하지 않는다. 안전장치로만 둔다.
- 한도에 닿으면 BudgetExceeded 를 던지고 data/logs/alerts.log 에 한 줄 남긴다.
"""
import json
import os
from datetime import date, datetime
from pathlib import Path

from config import LOGS, env

KRW_PER_USD = 1400  # 비용 표시용 환산(고정). 실제 청구는 달러

_run_spent = 0.0


class BudgetExceeded(RuntimeError):
    pass


def _usage_path() -> Path:
    return LOGS / "llm_usage.jsonl"


def records(path: Path | None = None) -> list[dict]:
    p = path or _usage_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 쓰다 끊긴 줄은 건너뜀
    return out


def spent_usd(prefix: str = "", since: str | None = None, path: Path | None = None) -> float:
    """호출 로그 합산. prefix: 'at' 이 이 문자열로 시작하는 것만(예: '2026-10' 이번 달, '2026-10-31' 오늘).
    since: 이 시각(ISO) 이후 것만."""
    return round(sum(r.get("cost_usd", 0) for r in records(path)
                     if str(r.get("at", "")).startswith(prefix)
                     and (since is None or str(r.get("at", "")) >= since)), 6)


def month_spent_usd(month: str | None = None, path: Path | None = None) -> float:
    return spent_usd(month or date.today().isoformat()[:7], path=path)


def krw(usd: float) -> int:
    return round(usd * KRW_PER_USD)


def _float_env(name: str) -> float | None:
    v = os.environ.get(name) or env(name)
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def run_cap_usd() -> float | None:
    return _float_env("JEONGMU_RUN_BUDGET_USD")


def monthly_cap_krw() -> float | None:
    return _float_env("MONTHLY_BUDGET_KRW")


def add(cost: float) -> None:
    """llm.log_usage 가 호출마다 부른다."""
    global _run_spent
    _run_spent += cost


def run_spent_usd() -> float:
    return round(_run_spent, 6)


def reset_run() -> None:
    global _run_spent
    _run_spent = 0.0


def check(purpose: str = "") -> None:
    """AI 호출 직전에 부른다. 한도에 닿았으면 알림을 남기고 BudgetExceeded."""
    cap = run_cap_usd()
    if cap is not None and _run_spent >= cap:
        msg = f"실행 한도 도달: 이번 실행 ${_run_spent:.4f} ≥ ${cap:.4f} (약 {krw(cap)}원) → '{purpose}' 호출 전 정지"
        alert(msg)
        raise BudgetExceeded(msg)
    mcap = monthly_cap_krw()
    if mcap is not None:
        m = month_spent_usd()
        if krw(m) >= mcap:
            msg = f"월 한도 도달: 이번 달 약 {krw(m)}원 ≥ {mcap:.0f}원 → '{purpose}' 호출 전 정지"
            alert(msg)
            raise BudgetExceeded(msg)


def alert(msg: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    with (LOGS / "alerts.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(f"[알림] {msg}", flush=True)


def record_run(summary: dict) -> str:
    """실행 결과를 data/logs/daily_runs.jsonl 에 한 줄(JSON)로 남기고, 사람이 읽는 1줄 요약을 돌려준다."""
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / "daily_runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return one_line(summary)


def one_line(s: dict) -> str:
    parts = [s.get("date", ""), "실행" if s.get("approved") else "추정만"]
    n = s.get("news") or {}
    if s.get("approved"):
        parts.append(f"뉴스 새 기사 {n.get('articles', 0)}·사실 {n.get('facts', 0)}")
    else:
        parts.append(f"뉴스 추출 대상 {n.get('to_extract', 0)}건")
    p = s.get("polls") or {}
    parts.append(f"여론조사 {'추출 ' + str(p.get('extracted', 0)) if s.get('approved') else '대상 ' + str(p.get('new', 0))}건")
    if s.get("stances_issues") is not None:
        parts.append(f"쟁점 {s['stances_issues']}개")
    if s.get("approved"):
        parts.append(f"비용 약 {krw(s.get('cost_usd', 0))}원")
    else:
        lo, hi = s.get("estimate_usd", (0, 0))
        parts.append(f"예상 약 {krw(lo)}~{krw(hi)}원")
    parts.append(f"이번 달 누적 약 {krw(s.get('month_usd', 0))}원")
    if s.get("stopped_by_budget"):
        parts.append("한도 정지")
    if s.get("failed"):
        parts.append("실패: " + ",".join(s["failed"]))
    return " | ".join(parts)
