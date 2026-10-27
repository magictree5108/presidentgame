"""data/rules_institutional.json 의 근거 조문을 법제처 현행 원문과 대조한다.

사용: python src/verify_rules.py [--refresh]
각 규칙의 verification 칸에 결과(검증됨/불일치/조문없음/조회실패), 대조일, 법령 시행일, 원문 발췌를 쓴다.
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import laws
from config import DATA

PATH = DATA / "rules_institutional.json"


def _norm(s: str) -> str:
    return "".join(s.split())


def verify(refresh: bool = False) -> dict:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    cache: dict[str, dict] = {}
    summary = {"검증됨": 0, "불일치": 0, "조문없음": 0, "조회실패": 0}
    for rule in data["rules"]:
        results = []
        for b in rule["basis"]:
            res = {"law": b["law"], "article": b["article"]}
            try:
                if b["law"] not in cache:
                    cache[b["law"]] = laws.fetch_law(b["law"], refresh=refresh)
                law = cache[b["law"]]
                res["law_enforce_date"] = laws.info(law)["enforce_date"]
                text = laws.article(law, b["article"])
                if text is None:
                    res["status"] = "조문없음"
                else:
                    missing = [p for p in b["must_contain"] if _norm(p) not in _norm(text)]
                    res["status"] = "불일치" if missing else "검증됨"
                    if missing:
                        res["missing"] = missing
                    res["excerpt"] = text[:400]
            except Exception as e:  # 네트워크 등
                res["status"] = "조회실패"
                res["error"] = str(e)[:200]
            results.append(res)
        statuses = {r["status"] for r in results}
        overall = "검증됨" if statuses == {"검증됨"} else next(
            s for s in ("조회실패", "조문없음", "불일치") if s in statuses)
        summary[overall] += 1
        rule["verification"] = {
            "status": overall, "checked_at": date.today().isoformat(),
            "source": "법제처 국가법령정보 공동활용 API(lawService.do) 현행 원문", "details": results,
        }
    data["_verified_summary"] = {**summary, "checked_at": date.today().isoformat()}
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    s = verify(refresh="--refresh" in sys.argv)
    print(s)
    data = json.loads(PATH.read_text(encoding="utf-8"))
    for r in data["rules"]:
        v = r["verification"]
        bad = [d for d in v["details"] if d["status"] != "검증됨"]
        print(f"{r['id']:4} {v['status']:5} {r['title']}" + (f"  ← {bad}" if bad else ""))
