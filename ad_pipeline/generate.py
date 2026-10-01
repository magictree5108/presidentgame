#!/usr/bin/env python3
"""
병맛 숏폼 광고 자동 생성 파이프라인
레퍼런스 이미지(나노바나나) -> Veo 3.1 클립 생성까지 한 번에

사용법:
    export GEMINI_API_KEY="your-key"
    python generate.py refs          # 레퍼런스 이미지만 생성
    python generate.py video         # 영상만 생성 (레퍼런스 이미 있을 때)
    python generate.py all           # 둘 다
    python generate.py video 03      # 특정 씬만 재생성
"""

import json
import os
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

CONFIG = "scenes.json"
REF_DIR = Path("refs")
OUT_DIR = Path("output")
IMAGE_MODEL = "gemini-3-pro-image-preview"

# Veo 3.1 per-second rates (Gemini API, 720p)
RATES = {
    "veo-3.1-generate-preview": 0.40,
    "veo-3.1-fast-generate-preview": 0.10,
    "veo-3.1-lite-generate-preview": 0.05,
}


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY 환경변수가 없습니다.")
    return genai.Client(api_key=key)


def make_refs(cli, cfg):
    REF_DIR.mkdir(exist_ok=True)
    for name, ref in cfg["references"].items():
        path = Path(ref["file"])
        if ref.get("manual"):
            if not path.exists():
                print(f"  [수동] {name}: {path} 에 실제 제품 사진을 직접 넣으세요")
            else:
                print(f"  [확인] {name}: 준비됨")
            continue
        if path.exists():
            print(f"  [건너뜀] {name}: 이미 있음")
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


def make_videos(cli, cfg, only=None):
    OUT_DIR.mkdir(exist_ok=True)
    model = cfg["model"]
    suffix = cfg["negative_suffix"]

    for scene in cfg["scenes"]:
        if only and only not in scene["id"]:
            continue

        out = OUT_DIR / f"{scene['id']}.mp4"
        if out.exists():
            print(f"  [건너뜀] {scene['id']}: 이미 있음 (재생성하려면 파일 삭제)")
            continue

        # 레퍼런스 이미지 최대 3장
        images = []
        missing = []
        for ref_key in scene["refs"][:3]:
            p = Path(cfg["references"][ref_key]["file"])
            if not p.exists():
                missing.append(ref_key)
                continue
            images.append(
                types.Image(
                    image_bytes=p.read_bytes(),
                    mime_type="image/png",
                )
            )
        if missing:
            print(f"  [경고] {scene['id']}: 레퍼런스 없음 {missing}")

        prompt = f"{scene['prompt']} {suffix}"
        print(f"  [생성중] {scene['id']} ({scene['duration']}초, 레퍼 {len(images)}장) ...")

        op = cli.models.generate_videos(
            model=model,
            prompt=prompt,
            reference_images=images or None,
            config=types.GenerateVideosConfig(
                aspect_ratio=cfg["aspect_ratio"],
                resolution=cfg["resolution"],
                duration_seconds=scene["duration"],
            ),
        )

        while not op.done:
            time.sleep(10)
            op = cli.operations.get(op)

        video = op.response.generated_videos[0].video
        cli.files.download(file=video)
        video.save(str(out))
        print(f"  [완료] {out}")


def estimate(cfg):
    rate = RATES.get(cfg["model"], 0.10)
    total = sum(s["duration"] for s in cfg["scenes"])
    print(f"  총 {total}초 x ${rate}/초 = ${total * rate:.2f} (1회 성공 기준)")
    print("  실패하거나 다시 뽑으면 그만큼 더 나갑니다.")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    only = sys.argv[2] if len(sys.argv) > 2 else None

    cfg = load_config()
    cli = client()

    print(f"\n[{cfg['project']}] 모델: {cfg['model']}")
    estimate(cfg)

    if mode in ("refs", "all"):
        print("\n레퍼런스 이미지")
        make_refs(cli, cfg)

    if mode in ("video", "all"):
        print("\n영상 클립")
        make_videos(cli, cfg, only)

    print("\n끝. output/ 폴더 확인하세요.\n")


if __name__ == "__main__":
    main()
