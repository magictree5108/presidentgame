#!/usr/bin/env python3
"""
병맛 숏폼 광고 자동 생성 파이프라인
레퍼런스 이미지(나노바나나) -> Veo 3.1 클립 생성까지 한 번에

사용법:
    export GEMINI_API_KEY="your-key"
    python generate.py refs                  # 레퍼런스 이미지만 생성
    python generate.py refs A_ajae --force   # 특정 레퍼런스만 다시 생성
    python generate.py video --dry           # 호출 없이 프롬프트/예상 금액만 확인
    python generate.py video                 # 영상 생성 (금액 확인 후 진행)
    python generate.py video 03              # 특정 씬만 생성
    python generate.py video 02 --test       # 4초 시험 클립 (대사/레퍼런스 확인용)
    python generate.py video 02 --test --duration 8
    옵션: --yes 로 금액 확인 질문 생략
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

CONFIG = "scenes.json"
REF_DIR = Path("refs")
OUT_DIR = Path("output")
COST_LOG = OUT_DIR / "cost_log.json"
IMAGE_MODEL = "gemini-3-pro-image-preview"

KRW_PER_USD = 1400  # 가정 환율. 실제와 다를 수 있음
POLL_INTERVAL = 10
POLL_TIMEOUT = 20 * 60  # 초

# Veo 3.1 초당 요금 (USD, 720p)
RATES = {
    "veo-3.1-generate-preview": 0.40,
    "veo-3.1-fast-generate-preview": 0.10,
    "veo-3.1-lite-generate-preview": 0.05,
}


def won(usd):
    return f"{round(usd * KRW_PER_USD):,}원"


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def client():
    from google import genai

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY 환경변수가 없습니다.")
    return genai.Client(api_key=key)


def make_refs(cli, cfg, only=None, force=False):
    REF_DIR.mkdir(exist_ok=True)
    for name, ref in cfg["references"].items():
        if only and only != name:
            continue
        path = Path(ref["file"])
        if ref.get("manual"):
            if not path.exists():
                print(f"  [수동] {name}: {path} 에 실제 제품 사진을 직접 넣으세요")
            else:
                print(f"  [확인] {name}: 준비됨")
            continue
        if path.exists() and not force:
            print(f"  [건너뜀] {name}: 이미 있음 (다시 만들려면 --force)")
            continue

        print(f"  [생성중] {name} ...")
        resp = cli.models.generate_content(
            model=IMAGE_MODEL,
            contents=ref["prompt"],
        )
        saved = False
        for part in resp.candidates[0].content.parts:
            if getattr(part, "inline_data", None):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(part.inline_data.data)
                saved = True
                break
        print(f"  [완료] {path}" if saved else f"  [실패] {name}")


def plan_videos(cfg, only, test, duration):
    """이번 실행에서 만들 씬 목록과 각 씬의 길이/출력 경로를 계산한다."""
    plan = []
    for scene in cfg["scenes"]:
        if only and only not in scene["id"]:
            continue
        secs = duration or (4 if test else scene["duration"])
        name = f"test_{scene['id']}_{secs}s" if test else scene["id"]
        out = OUT_DIR / f"{name}.mp4"
        refs = [k for k in scene["refs"][:3]]
        missing = [k for k in refs if not Path(cfg["references"][k]["file"]).exists()]
        plan.append(
            {"scene": scene, "secs": secs, "out": out, "refs": refs, "missing": missing}
        )
    return plan


def print_plan(cfg, plan):
    rate = RATES.get(cfg["model"], 0.10)
    total_secs = 0
    for p in plan:
        s = p["scene"]
        if p["out"].exists():
            print(f"  [건너뜀] {s['id']}: {p['out'].name} 이미 있음")
            continue
        total_secs += p["secs"]
        print(f"\n  [{s['id']}] {p['secs']}초, {won(p['secs'] * rate)}, 레퍼런스 {p['refs']}")
        if p["missing"]:
            print(f"    경고: 레퍼런스 파일 없음 {p['missing']}")
        print(f"    프롬프트: {s['prompt']} {cfg['negative_suffix']}")
    print(f"\n  이번 실행 합계: {total_secs}초, {won(total_secs * rate)} (환율 {KRW_PER_USD}원 가정)")
    return total_secs, total_secs * rate


def log_cost(scene_id, secs, usd):
    OUT_DIR.mkdir(exist_ok=True)
    log = json.loads(COST_LOG.read_text(encoding="utf-8")) if COST_LOG.exists() else []
    log.append(
        {
            "time": datetime.now().isoformat(timespec="seconds"),
            "scene": scene_id,
            "seconds": secs,
            "won": round(usd * KRW_PER_USD),
        }
    )
    COST_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    누적 생성 비용: {sum(e['won'] for e in log):,}원")


def make_videos(cli, cfg, plan):
    from google.genai import types

    rate = RATES.get(cfg["model"], 0.10)
    for p in plan:
        scene, secs, out = p["scene"], p["secs"], p["out"]
        if out.exists():
            continue

        ref_objs = [
            types.VideoGenerationReferenceImage(
                image=types.Image(
                    image_bytes=Path(cfg["references"][k]["file"]).read_bytes(),
                    mime_type="image/png",
                ),
                reference_type=types.VideoGenerationReferenceType.ASSET,
            )
            for k in p["refs"]
            if k not in p["missing"]
        ]
        prompt = f"{scene['prompt']} {cfg['negative_suffix']}"
        print(f"  [생성중] {scene['id']} ({secs}초, 레퍼 {len(ref_objs)}장) ...")

        try:
            op = cli.models.generate_videos(
                model=cfg["model"],
                prompt=prompt,
                config=types.GenerateVideosConfig(
                    aspect_ratio=cfg["aspect_ratio"],
                    resolution=cfg["resolution"],
                    duration_seconds=secs,
                    reference_images=ref_objs or None,
                ),
            )
            waited = 0
            while not op.done:
                if waited >= POLL_TIMEOUT:
                    raise TimeoutError("생성 대기 시간 초과")
                time.sleep(POLL_INTERVAL)
                waited += POLL_INTERVAL
                op = cli.operations.get(op)

            if getattr(op, "error", None):
                raise RuntimeError(f"API 오류: {op.error}")
            videos = getattr(op.response, "generated_videos", None)
            if not videos:
                reasons = getattr(op.response, "rai_media_filtered_reasons", None)
                raise RuntimeError(f"결과 없음 (안전 필터 가능성): {reasons}")

            video = videos[0].video
            cli.files.download(file=video)
            video.save(str(out))
            print(f"  [완료] {out}")
            log_cost(scene["id"], secs, secs * rate)
        except Exception as e:  # 한 씬이 실패해도 나머지는 계속 진행
            print(f"  [실패] {scene['id']}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="all", choices=["refs", "video", "all"])
    ap.add_argument("target", nargs="?", help="refs: 레퍼런스 이름 / video: 씬 id 일부")
    ap.add_argument("--dry", action="store_true", help="API 호출 없이 계획과 금액만 출력")
    ap.add_argument("--test", action="store_true", help="4초 시험 클립")
    ap.add_argument("--duration", type=int, help="길이(초) 직접 지정")
    ap.add_argument("--force", action="store_true", help="이미 있는 레퍼런스도 다시 생성")
    ap.add_argument("--yes", action="store_true", help="금액 확인 질문 생략")
    args = ap.parse_args()

    cfg = load_config()
    print(f"\n[{cfg['project']}] 모델: {cfg['model']}")

    if args.mode in ("refs", "all") and not args.dry:
        print("\n레퍼런스 이미지")
        make_refs(client(), cfg, args.target if args.mode == "refs" else None, args.force)

    if args.mode in ("video", "all"):
        print("\n영상 클립")
        only = args.target if args.mode == "video" else None
        plan = plan_videos(cfg, only, args.test, args.duration)
        secs, usd = print_plan(cfg, plan)
        if args.dry or secs == 0:
            print("\n(사전 점검만 수행, API 호출 없음)\n" if args.dry else "")
            return
        if not args.yes:
            if input("  진행할까요? [y/N] ").strip().lower() != "y":
                sys.exit("취소했습니다.")
        make_videos(client(), cfg, plan)

    print("\n끝. output/ 폴더 확인하세요.\n")


if __name__ == "__main__":
    main()
