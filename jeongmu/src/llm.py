"""Anthropic API 호출 공용 함수. 호출마다 토큰과 비용을 data/logs/llm_usage.jsonl 에 남긴다.

모델: claude-opus-5-5 (Anthropic 공식 문서 기준, 2026-10 확인)
가격: 입력 $4 / 출력 $20 / 캐시 읽기 $0.20 (100만 토큰당). 캐시 쓰기는 입력의 1.25배.
거절(refusal) 시 서버측 대체 모델(fallbacks="default")을 켜 둔다.
"""
import json
from datetime import datetime

from config import LOGS, env

MODEL = "claude-opus-5-5"          # 판단·워게임
CHEAP_MODEL = "claude-haiku-5-5"   # 기사 사실 추출(사용자 결정 2026-10-28: 비용 절감)
# $/MTok. Haiku 5.5 가격은 요청 10만 토큰 이하 기준(기사 추출은 항상 그 이하)
PRICES = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125},
}
PRICE = PRICES[MODEL]


class LLMUnavailable(RuntimeError):
    pass


def cost_usd(u: dict, model: str = MODEL) -> float:
    pr = PRICES.get(model, PRICE)
    return round((u.get("input_tokens", 0) * pr["input"]
                  + u.get("output_tokens", 0) * pr["output"]
                  + u.get("cache_read_input_tokens", 0) * pr["cache_read"]
                  + u.get("cache_creation_input_tokens", 0) * pr["cache_write"]) / 1e6, 6)


def log_usage(purpose: str, usage: dict, run_id: str | None = None, model: str = MODEL) -> dict:
    LOGS.mkdir(parents=True, exist_ok=True)
    rec = {"at": datetime.now().isoformat(timespec="seconds"), "purpose": purpose, "run_id": run_id,
           "model": model, **usage, "cost_usd": cost_usd(usage, model)}
    with (LOGS / "llm_usage.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def usage_summary() -> dict:
    p = LOGS / "llm_usage.jsonl"
    if not p.exists():
        return {"calls": 0, "cost_usd": 0, "by_purpose": {}, "avg_per_wargame_usd": None}
    recs = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    by: dict = {}
    for r in recs:
        b = by.setdefault(r["purpose"], {"calls": 0, "cost_usd": 0.0})
        b["calls"] += 1
        b["cost_usd"] = round(b["cost_usd"] + r["cost_usd"], 6)
    games: dict = {}
    for r in recs:
        if r["purpose"].startswith("wargame") and r.get("run_id"):
            games[r["run_id"]] = games.get(r["run_id"], 0) + r["cost_usd"]
    return {"calls": len(recs), "cost_usd": round(sum(r["cost_usd"] for r in recs), 4), "by_purpose": by,
            "wargames": len(games),
            "avg_per_wargame_usd": round(sum(games.values()) / len(games), 4) if games else None}


def call_json(system: str, user: str, schema: dict, *, purpose: str, run_id: str | None = None,
              effort: str = "high", max_tokens: int = 16000, model: str = MODEL) -> dict:
    """JSON 스키마로 출력을 강제해 호출하고 dict 를 돌려준다."""
    if not env("ANTHROPIC_API_KEY"):
        raise LLMUnavailable("ANTHROPIC_API_KEY가 .env에 없습니다.")
    import anthropic

    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    kw = dict(model=model, max_tokens=max_tokens,
              system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
              output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
              messages=[{"role": "user", "content": user}])
    if model == MODEL:  # 서버측 대체 모델은 Opus 에서만 지원(Haiku 는 미지원)
        kw.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        stream_cm = client.beta.messages.stream(**kw)
    else:
        stream_cm = client.messages.stream(**kw)
    with stream_cm as stream:
        msg = stream.get_final_message()
    u = msg.usage
    usage = {k: getattr(u, k, 0) or 0 for k in
             ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
    log_usage(purpose, usage, run_id, model=getattr(msg, "model", model))
    if msg.stop_reason == "refusal":
        raise LLMUnavailable("모델이 요청을 거절함")
    if msg.stop_reason == "max_tokens":
        raise LLMUnavailable("출력이 max_tokens에서 잘림")
    text = "".join(b.text for b in msg.content if b.type == "text")
    return json.loads(text)
