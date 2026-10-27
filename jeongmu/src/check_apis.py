"""열린국회정보 API를 실제로 호출해 서비스 코드와 필드명을 확인한다.

사용: python src/check_apis.py
결과: docs/api_samples/<코드>.json (응답 표본 3건)
      docs/api_check.md (서비스별 확인 결과, 없는 필드, OPENSRVAPI 목록에서 찾은 후보)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import assembly_api as api
from api_fields import SERVICES, TO_DISCOVER
from config import DOCS

OUT = DOCS / "api_samples"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [f"# 열린국회정보 API 실호출 확인 ({datetime.now():%Y-%m-%d %H:%M})", "",
             "| 용도 | 서비스 코드 | 결과 | 전체 건수 | 응답에 없는 예상 필드 |",
             "|---|---|---|---|---|"]
    for key, s in SERVICES.items():
        params = dict(s["params"])
        if key == "member_votes":
            # 의원별 표결은 BILL_ID가 필요하다. 의안별 표결현황 첫 건으로 부른다.
            try:
                rows, _ = api.call(SERVICES["bill_votes"]["code"], SERVICES["bill_votes"]["params"],
                                   size=1, use_cache=False)
                if rows:
                    params["BILL_ID"] = rows[0].get("BILL_ID")
            except api.AssemblyAPIError:
                pass
        try:
            rows, total = api.call(s["code"], params, size=3, use_cache=False)
            (OUT / f"{s['code']}.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            got = set(rows[0].keys()) if rows else set()
            missing = [c for c in s["fields"].values() if rows and c not in got]
            res = "확인됨" if rows and not missing else ("필드 불일치" if rows else "데이터 없음")
            lines.append(f"| {s['name']} | `{s['code']}` | {res} | {total} | {', '.join(missing) or '-'} |")
            if rows:
                lines.append(f"|  ↳ 실제 필드 | | | | {', '.join(sorted(got))} |")
        except api.AssemblyAPIError as e:
            lines.append(f"| {s['name']} | `{s['code']}` | 실패: {str(e)[:80]} | | |")

    # API 목록에서 아직 코드를 모르는 것 찾기
    lines += ["", "## OPENSRVAPI 목록에서 찾은 후보", ""]
    try:
        catalog = list(api.fetch_all("OPENSRVAPI", {}, use_cache=False, size=1000))
        (OUT / "OPENSRVAPI.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
        for key, words in TO_DISCOVER.items():
            hits = [c for c in catalog if any(w.replace(" ", "") in json.dumps(c, ensure_ascii=False).replace(" ", "") for w in words)]
            lines.append(f"### {key} ({' / '.join(words)})")
            for h in hits[:10]:
                lines.append(f"- {json.dumps(h, ensure_ascii=False)[:300]}")
            if not hits:
                lines.append("- 찾지 못함")
            lines.append("")
    except api.AssemblyAPIError as e:
        lines.append(f"목록 조회 실패: {e}")
    (DOCS / "api_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
