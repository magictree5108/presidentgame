#!/bin/bash
# 전 구간 API 스모크 테스트 (단일 모드). 사용: npm run dev 후  CRON_SECRET=... bash scripts/smoke-flow.sh
# 사전: node scripts/make-test-face.mjs
S=${TMPDIR:-/tmp}; FACE=${FACE:-scripts/test-face.jpg}; J=$S/after-cj.txt; rm -f $J; B=${BASE_URL:-http://localhost:3000}
py() { python3 -c "import sys,json;d=json.load(sys.stdin);$1"; }
echo "== session";  curl -s -c $J -b $J -X POST $B/api/session -H 'Content-Type: application/json' -d '{"ageConfirmed":true,"faceConsent":true}'; echo
echo "== upload";   curl -s -b $J -F front=@$FACE -F side=@$FACE $B/api/upload | head -c 200; echo
SEL='{"selection":{"nose":{"enabled":true,"intensity":"low"},"eyes":{"enabled":true,"intensity":"mid"},"jawline":{"enabled":false,"intensity":"mid"},"forehead":{"enabled":false,"intensity":"mid"},"lips":{"enabled":false,"intensity":"mid"}}}'
echo "== face gen"; GID=$(curl -s -b $J -X POST $B/api/generate/face -H 'Content-Type: application/json' -d "$SEL" | py 'print(d["generation"]["id"])'); echo $GID
for i in $(seq 1 10); do sleep 2; P=$(curl -s -b $J $B/api/generations/$GID); echo "$P" | py 'print(d["generation"]["status"], d["generation"]["outputs"], d["credits"], d["generation"]["error"])'; echo "$P" | grep -qE '"done"|"failed"' && break; done
echo "== second face gen (expect 402)"; curl -s -b $J -X POST $B/api/generate/face -H 'Content-Type: application/json' -d "$SEL" -w ' [%{http_code}]'; echo
echo "== photos gen"; PID=$(curl -s -b $J -X POST $B/api/generate/photos -H 'Content-Type: application/json' -d '{"place":"jeju_sea","mood":"film"}' | py 'print(d["generation"]["id"])'); echo $PID
for i in $(seq 1 10); do sleep 2; P=$(curl -s -b $J $B/api/generations/$PID); echo "$P" | py 'print(d["generation"]["status"], len(d["generation"]["outputs"]), d["credits"], d["generation"]["error"])'; echo "$P" | grep -qE '"done"|"failed"' && break; done
echo "== photos again (expect 402)"; curl -s -b $J -X POST $B/api/generate/photos -H 'Content-Type: application/json' -d '{"place":"club","mood":"neon"}' -w ' [%{http_code}]'; echo
echo "== share"; SH=$(curl -s -b $J -X POST $B/api/share); echo $SH; SID=$(echo $SH | py 'print(d["share"]["id"])')
echo "== story"; curl -s -b $J $B/api/share/$SID/story | py 'print(len(d["slides"]), "slides"); [print(" ", s[:90]) for s in d["slides"]]'
echo "== share page (no cookie)"; curl -s $B/s/$SID | grep -oE '<meta[^>]*(og:image|og:title|twitter:card)[^>]*>'; curl -s -o /dev/null -w 'share page %{http_code}\n' $B/s/$SID
echo "== og image"; OG=$(curl -s $B/s/$SID | grep -oE 'og:image" content="[^"]+' | sed 's/.*content="//'); curl -s -o $S/og.jpg -w "og %{http_code} %{size_download}B\n" "$OG"
echo "== export slides"; i=0; for u in $(curl -s -b $J $B/api/share/$SID/story | py 'print("\n".join(d["slides"]))'); do i=$((i+1)); curl -s -o $S/story-$i.jpg "$u"; done; ls -la $S/*.jpg
echo "== after face"; AF=$(curl -s -b $J $B/api/session | py 'print(d["session"]["face"]["outputs"][0])'); curl -s -o $S/after.jpg "$AF"
echo "== rate limit (4 quick face calls; credits gone so 402 or 429)"; for i in 1 2 3 4 5; do curl -s -b $J -X POST $B/api/generate/face -H 'Content-Type: application/json' -d "$SEL" -o /dev/null -w '%{http_code} '; done; echo
echo "== cron unauthorized"; curl -s -X POST $B/api/cron/cleanup -w ' [%{http_code}]'; echo
echo "== cron ok"; curl -s -X POST $B/api/cron/cleanup -H "Authorization: Bearer $CRON_SECRET"; echo
echo "== delete"; curl -s -b $J -X POST $B/api/delete; echo
echo "== share page after delete"; curl -s -o /dev/null -w '%{http_code}\n' $B/s/$SID
