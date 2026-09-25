#!/bin/bash
# 비교 모드(약·중·강) + 친구 투표 스모크 테스트. 사용: npm run dev 후  bash scripts/smoke-compare-vote.sh
S=${TMPDIR:-/tmp}; FACE=${FACE:-scripts/test-face.jpg}; J=$S/after-cj.txt; V1=$S/after-v1.txt; V2=$S/after-v2.txt; rm -f $J $V1 $V2; B=${BASE_URL:-http://localhost:3000}
py() { python3 -c "import sys,json;d=json.load(sys.stdin);$1"; }
curl -s -c $J -X POST $B/api/session -H 'Content-Type: application/json' -d '{"ageConfirmed":true,"faceConsent":true}' >/dev/null
curl -s -b $J -F front=@$FACE $B/api/upload >/dev/null
SEL='{"selection":{"nose":{"enabled":true,"intensity":"low"},"eyes":{"enabled":true,"intensity":"mid"},"jawline":{"enabled":false,"intensity":"mid"},"forehead":{"enabled":false,"intensity":"mid"},"lips":{"enabled":false,"intensity":"mid"}},"compare":true}'
echo "== face gen (compare)"; R=$(curl -s -b $J -X POST $B/api/generate/face -H 'Content-Type: application/json' -d "$SEL"); echo "$R" | py 'print(d["generation"]["params"]["variants"], d["generation"]["params"]["variantLabels"])'; GID=$(echo "$R" | py 'print(d["generation"]["id"])')
for i in $(seq 1 10); do sleep 2; P=$(curl -s -b $J $B/api/generations/$GID); echo "$P" | py 'print(d["generation"]["status"], len(d["generation"]["outputs"]), "chosen", d["generation"]["chosen"])'; echo "$P" | grep -qE '"done"|"failed"' && break; done
echo "== choose variant 2 (강)"; curl -s -b $J -X POST $B/api/generate/face/choose -H 'Content-Type: application/json' -d '{"index":2}' | py 'print("chosen", d["generation"]["chosen"])'
echo "== photos"; PID=$(curl -s -b $J -X POST $B/api/generate/photos -H 'Content-Type: application/json' -d '{"place":"interview_id","mood":"daylight"}' | py 'print(d["generation"]["id"])')
for i in $(seq 1 10); do sleep 2; P=$(curl -s -b $J $B/api/generations/$PID); echo "$P" | py 'print(d["generation"]["status"], len(d["generation"]["outputs"]))'; echo "$P" | grep -qE '"done"|"failed"' && break; done
echo "== share"; SH=$(curl -s -b $J -X POST $B/api/share); echo $SH; SID=$(echo $SH | py 'print(d["share"]["id"])')
echo "== session.share"; curl -s -b $J $B/api/session | py 'print(d["session"]["share"]["question"], [c["label"] for c in d["session"]["share"]["choices"]], d["session"]["share"]["total"])'
echo "== story slides"; curl -s -b $J $B/api/share/$SID/story | py 'print(len(d["slides"]))'
i=0; for u in $(curl -s -b $J $B/api/share/$SID/story | py 'print("\n".join(d["slides"]))'); do i=$((i+1)); curl -s -o $S/s2-story-$i.jpg "$u"; done
echo "== share page"; curl -s $B/s/$SID | grep -oE '<meta property="og:title"[^>]*>|어디까지 하는 게 제일 나아|본인 픽' | sort -u
echo "== vote GET before (anon)"; curl -s -c $V1 -b $V1 $B/api/share/$SID/vote | py 'print("mine",d["mine"],"tally",d["tally"])'
echo "== vote POST voter1 → 1(중)"; curl -s -c $V1 -b $V1 -X POST $B/api/share/$SID/vote -H 'Content-Type: application/json' -d '{"choice":"1"}' | py 'print("mine",d["mine"],"tally",d["tally"],"total",d["total"])'
echo "== vote POST voter1 change → none"; curl -s -c $V1 -b $V1 -X POST $B/api/share/$SID/vote -H 'Content-Type: application/json' -d '{"choice":"none"}' | py 'print("mine",d["mine"],"tally",d["tally"],"total",d["total"])'
echo "== vote POST voter2 → 2"; curl -s -c $V2 -b $V2 -X POST $B/api/share/$SID/vote -H 'Content-Type: application/json' -d '{"choice":"2"}' | py 'print("mine",d["mine"],"tally",d["tally"],"total",d["total"])'
echo "== invalid choice"; curl -s -c $V2 -b $V2 -X POST $B/api/share/$SID/vote -H 'Content-Type: application/json' -d '{"choice":"yes"}' -w ' [%{http_code}]'; echo
echo "== owner view"; curl -s -b $J $B/api/share/$SID/vote | py 'print("owner",d["isOwner"],"tally",d["tally"])'
echo "== session tally"; curl -s -b $J $B/api/session | py 'print(d["session"]["share"]["tally"], d["session"]["share"]["total"])'
echo "== OG"; OG=$(curl -s $B/s/$SID | grep -oE 'og:image" content="[^"]+' | sed 's/.*content="//'); curl -s -o $S/s2-og.jpg "$OG" -w "og %{http_code}\n"
echo "== root OG"; curl -s -o $S/root-og.png -w "root og %{http_code} %{content_type}\n" $B/opengraph-image
echo "== privacy"; curl -s -o /dev/null -w "privacy %{http_code}\n" $B/privacy
