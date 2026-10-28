"""읽기 전용 미리보기 페이지(스냅샷) 만들기 → web/snapshot.html

서버 없이 열리는 한 장짜리 HTML. 실제 DB 값을 그대로 넣는다(AI 호출 없음, 0원).
새 판단·워게임은 서버가 필요해 미리보기에서는 막고, 본회의 대기 법안 몇 건의 '규칙 기반 판단'(AI 없음)만 미리 계산해 넣는다.
사용: python src/export_snapshot.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import engine
import server
from config import ROOT
from db import connect

OUT = ROOT / "web" / "snapshot.html"


def build() -> dict:
    con = connect()
    snap = {
        "/api/status": server.status(),
        "/api/seats": server.seats(),
        "/api/committees": server.committees(),
        "/api/network?min_w=3": server.network(min_w=3),
        "/api/rules": server.rules(),
        "/api/government": server.government(),
        "/api/groups": server.groups(),
        "/api/predictions": server.predictions(),
        "/api/backtest": server.backtest_report(),
        "/api/usage": server.usage(),
    }
    try:
        snap["/api/strategy/latest"] = server.strategy_latest()
    except Exception:
        pass
    al = server.alerts()
    if not isinstance(al, list) or not al:  # 오늘 기사가 없으면 가장 최근 날짜 알림
        from news import nconnect, alerts
        last = nconnect().execute("SELECT MAX(pub_date) FROM articles").fetchone()[0]
        al = alerts(last) if last else []
    snap["/api/alerts"] = al
    members = {}
    for m in snap["/api/seats"]["members"]:
        d = server.member(m["member_id"])
        members[m["member_id"]] = d
    snap["members"] = members
    # 크기 절약: 배열로 담고(상세 링크는 bill_id 로 다시 만든다) 화면에서 객체로 풀어 쓴다
    snap["bills"] = [list(r) for r in con.execute(
        """SELECT bill_id, bill_name, proposer, propose_dt, committee, stage
           FROM bills ORDER BY propose_dt DESC""")]
    judged = {}
    for r in con.execute("SELECT bill_id FROM bills WHERE stage='본회의 대기' ORDER BY propose_dt DESC LIMIT 8"):
        j = engine.judge({"bill_id": r[0]}, use_ai=False, record_prediction=False, con=con)
        j["member_forecast"] = j["member_forecast"][:300]
        judged[r[0]] = j
    snap["judged"] = judged
    return snap


SHIM = r"""
<script>
// 미리보기(스냅샷) 모드: 서버 대신 페이지에 넣어 둔 데이터를 쓴다.
window.SNAP = __SNAP__;
window.SNAPSHOT_MODE = true;
window.fetch = async (p, opt) => {
  const ok = (v, text) => ({ ok: true, headers: { get: () => text ? "text/plain" : "application/json" },
                             json: async () => v, text: async () => v });
  const fail = (msg) => ({ ok: false, text: async () => msg, headers: { get: () => "text/plain" } });
  const S = window.SNAP;
  if (p.startsWith("/api/members/")) return ok(S.members[decodeURIComponent(p.slice(13))] || {});
  if (p.startsWith("/api/bills")) {
    const q = decodeURIComponent((p.split("q=")[1] || "").split("&")[0]);
    const hit = S.bills.filter(b => b[1].includes(q));
    hit.sort((a, b) => (b[1].startsWith(q) - a[1].startsWith(q)));
    return ok(hit.slice(0, 30).map(b => ({bill_id: b[0], bill_name: b[1], proposer: b[2], propose_dt: b[3],
      committee: b[4], stage: b[5], detail_link: "https://likms.assembly.go.kr/bill/billDetail.do?billId=" + b[0]})));
  }
  if (p === "/api/judge") {
    const body = JSON.parse(opt.body);
    const j = S.judged[body.bill_id];
    return j ? ok(j) : fail("미리보기에서는 '본회의 대기' 법안 중 미리 계산한 " + Object.keys(S.judged).length +
      "건만 판단을 볼 수 있습니다. 다른 법안의 판단과 AI 판단은 내 PC에서 프로그램을 켜면 됩니다.");
  }
  if (p.startsWith("/api/wargame")) return fail("워게임은 내 PC에서 프로그램을 켜야 할 수 있습니다(미리보기에서는 불가).");
  if (p.startsWith("/api/rules/heuristic")) return fail("경험칙 추가는 내 PC 실행에서 저장됩니다.");
  if (p.startsWith("/api/seats")) return ok(S["/api/seats"]);
  if (p.startsWith("/api/network")) return ok(S["/api/network?min_w=3"]);
  if (p.startsWith("/api/alerts")) return ok(S["/api/alerts"]);
  if (p in S) return ok(S[p], p === "/api/backtest");
  return fail("미리보기에 없는 데이터: " + p);
};
</script>
"""

BANNER = """<div class="snapbar">미리보기 · {asof} 기준 실제 데이터 · 정무 전략은 마지막 분석 결과 · 법안 판단은 본회의 대기 {n}건만(규칙 기반) · 새 분석·워게임은 요청 시 실행</div>"""


def main():
    snap = build()
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    # 게시용: 문서 뼈대 태그를 걷어 내고 제목·스타일·본문만 남긴다
    title = re.search(r"<title>.*?</title>", html, re.S).group(0)
    style = re.search(r"<style>.*?</style>", html, re.S).group(0)
    body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
    style = style.replace("<style>", """<style>
:root{color-scheme:dark}
body{background:#0b1016}
main{padding-left:max(16px, env(safe-area-inset-left, 0px));padding-right:max(16px, env(safe-area-inset-right, 0px))}
header{padding-left:max(16px, env(safe-area-inset-left, 0px));padding-right:max(16px, env(safe-area-inset-right, 0px));top:env(safe-area-inset-top, 0px)}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top, 0px);z-index:10;background:#0e151d}
.snapbar{background:#1d2a12;color:#cfe8a9;font-size:12px;padding:6px max(16px, env(safe-area-inset-left, 0px));border-bottom:1px solid #2f4520}
""", 1)
    # prompt()·alert() 는 게시 페이지에서 동작하지 않으므로 워게임 버튼을 막는다
    body = body.replace('<button class="act" id="wgBtn">워게임 시작</button>',
                        '<button class="act" id="wgBtn" disabled title="내 PC 실행에서 가능">워게임(PC 전용)</button>')
    body = body.replace('<label class="small"><input type="checkbox" id="useAi" checked> AI 판단 사용</label>',
                        '<label class="small"><input type="checkbox" id="useAi" disabled> AI 판단(PC 전용)</label>')
    body = body.replace("alert(", "(m=>{const d=document.getElementById('judge'); if(d) d.insertAdjacentHTML('afterbegin', '<div class=\"warn small\">'+esc(m)+'</div>');})(")
    asof = snap["/api/status"]["today"]
    data = json.dumps(snap, ensure_ascii=False, default=str).replace("</", "<\\/")
    out = (title + '\n<meta name="claude:viewport-fit-sides" content="cover">\n' + style + "\n"
           + BANNER.format(asof=asof, n=len(snap["judged"])) + "\n"
           + SHIM.replace("__SNAP__", data) + body)
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT} {len(out.encode()) / 1e6:.1f}MB, 의원 {len(snap['members'])}명, 법안 {len(snap['bills'])}건, 판단 {len(snap['judged'])}건")


if __name__ == "__main__":
    main()
