#!/usr/bin/env python3
"""
병맛 숏폼 광고 자동 생성 파이프라인
레퍼런스 이미지(나노바나나) -> Veo 3.1 클립 생성까지 한 번에

사용법:
    export GEMINI_API_KEY="your-key"
    python generate.py script                # 씬별 대사를 화자별로 출력 (수정은 scenes.json 의 dialogue)
    python generate.py refs                  # 레퍼런스 이미지만 생성
    python generate.py refs A_ajae --force   # 특정 레퍼런스만 다시 생성
    python generate.py frames                # 씬별 9:16 시작 장면 이미지 생성
    python generate.py frames 02 --force     # 특정 씬 시작 장면만 다시 생성
    python generate.py video --dry           # 호출 없이 프롬프트/예상 금액만 확인
    python generate.py video                 # 영상 생성 (금액 확인 후 진행)
    python generate.py concat                # 완성된 클립을 순서대로 이어 붙여 final.mp4
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
FRAME_DIR = Path("frames")
COST_LOG = Path("cost_log.json")
IMAGE_MODEL = "gemini-3-pro-image-preview"

KRW_PER_USD = 1400  # 가정 환율. 실제와 다를 수 있음
IMAGE_USD = 0.134  # 이미지 1장 추정 요금(USD, 2K 기준). 실제와 다를 수 있음
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


def render_line(d):
    """dialogue 항목 하나를 영상 프롬프트용 영어 문장으로 만든다."""
    manner = f" {d['manner']}" if d.get("manner") else ""
    lang = "" if d.get("animal") else " in Korean"
    dialect = " with Gyeongsang dialect" if d.get("dialect") else ""
    return f'{d["en"]}{manner}{lang}{dialect}: "{d["line"]}"'


def build_prompt(scene, cfg):
    prompt = scene["prompt"]
    for i, d in enumerate(scene.get("dialogue", []), 1):
        token = f"[[{i}]]"
        sentence = render_line(d)
        prompt = prompt.replace(token, sentence) if token in prompt else f"{prompt} {sentence}"
    return f"{prompt} {cfg['negative_suffix']}"


def print_script(cfg, only=None):
    """씬별 대사를 '인물: 대사' 형식으로 출력한다. 수정할 때는 이 형식 그대로 고치면 된다."""
    print("\n대사 (인물: 대사)")
    for i, s in enumerate(cfg["scenes"], 1):
        if only and only not in s["id"]:
            continue
        print(f"\n[씬{i}] {s['id']} ({s['duration']}초)")
        for d in s.get("dialogue", []):
            print(f"{d['speaker']}: {d['line']}")


def frame_matches(path, aspect):
    """시작 장면 이미지의 가로세로 비율이 설정과 같은지 확인한다. PIL 이 없으면 통과."""
    try:
        from PIL import Image
    except ImportError:
        return True
    w, h = Image.open(path).size
    aw, ah = (int(x) for x in aspect.split(":"))
    return abs(w / h - aw / ah) < 0.05


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


def make_frames(cli, cfg, only=None, force=False):
    """씬별 9:16 시작 장면 이미지를 만든다. 영상의 첫 프레임으로 쓰인다."""
    from google.genai import types

    FRAME_DIR.mkdir(exist_ok=True)
    for scene in cfg["scenes"]:
        if only and only not in scene["id"]:
            continue
        path = FRAME_DIR / f"{scene['id']}.png"
        if path.exists() and not force and frame_matches(path, cfg["aspect_ratio"]):
            print(f"  [건너뜀] {scene['id']}: 이미 있음 (다시 만들려면 --force)")
            continue

        parts = []
        for k in scene["refs"][:3]:
            p = Path(cfg["references"][k]["file"])
            if p.exists():
                parts.append(types.Part.from_bytes(data=p.read_bytes(), mime_type="image/png"))
            else:
                print(f"    경고: 레퍼런스 없음 {k}")
        parts.append(scene["frame_prompt"])

        print(f"  [생성중] {scene['id']} 시작 장면 (레퍼 {len(parts) - 1}장, 약 {won(IMAGE_USD)}) ...")
        resp = cli.models.generate_content(
            model=IMAGE_MODEL,
            contents=parts,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=cfg["aspect_ratio"]),
            ),
        )
        saved = False
        for part in resp.candidates[0].content.parts:
            if getattr(part, "inline_data", None):
                path.write_bytes(part.inline_data.data)
                saved = True
                break
        print(f"  [완료] {path}" if saved else f"  [실패] {scene['id']}")
        if saved:
            log_cost(f"frame_{scene['id']}", 0, IMAGE_USD)


def plan_videos(cfg, only, test, duration):
    """이번 실행에서 만들 씬 목록과 각 씬의 길이/출력 경로를 계산한다."""
    plan = []
    for scene in cfg["scenes"]:
        if only and only not in scene["id"]:
            continue
        secs = duration or (4 if test else scene["duration"])
        tag = "_lite" if "lite" in cfg["model"] else ""
        name = f"test_{scene['id']}_{secs}s{tag}" if test else scene["id"]
        out = OUT_DIR / f"{name}.mp4"
        frame = FRAME_DIR / f"{scene['id']}.png"
        plan.append({"scene": scene, "secs": secs, "out": out, "frame": frame})
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
        print(f"\n  [{s['id']}] {p['secs']}초, {won(p['secs'] * rate)}, 첫 프레임 {p['frame']}")
        if not p["frame"].exists():
            print("    경고: 시작 장면 이미지 없음. 먼저 frames 모드를 실행하세요")
        print(f"    프롬프트: {build_prompt(s, cfg)}")
    print(f"\n  이번 실행 합계: {total_secs}초, {won(total_secs * rate)} (환율 {KRW_PER_USD}원 가정)")
    return total_secs, total_secs * rate


def frames_needed(cfg, plan):
    return sum(
        1 for p in plan
        if not p["frame"].exists() or not frame_matches(p["frame"], cfg["aspect_ratio"])
    )


def check_budget(cfg, plan, video_usd, over_ok):
    """시작 장면 이미지(없는 것만)와 영상을 합친 예상 총액이 예산을 넘으면 중단한다."""
    n = frames_needed(cfg, plan)
    frame_usd = n * IMAGE_USD
    total = video_usd + frame_usd
    budget = cfg.get("budget_won")
    print(f"  시작 장면 {n}장 {won(frame_usd)} + 영상 {won(video_usd)} = 예상 총 {won(total)}", end="")
    print(f" / 예산 {budget:,}원" if budget else "")
    if budget and round(total * KRW_PER_USD) > budget and not over_ok:
        sys.exit("  예산을 넘습니다. 모델/길이를 조정하거나 --over-budget 으로 진행하세요.")


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

        if not p["frame"].exists():
            print(f"  [건너뜀] {scene['id']}: 시작 장면 없음 ({p['frame']})")
            continue
        if not frame_matches(p["frame"], cfg["aspect_ratio"]):
            print(f"  [건너뜀] {scene['id']}: 시작 장면 비율이 {cfg['aspect_ratio']} 가 아닙니다. frames --force 로 다시 만드세요")
            continue
        first_frame = types.Image(image_bytes=p["frame"].read_bytes(), mime_type="image/png")
        prompt = build_prompt(scene, cfg)
        print(f"  [생성중] {scene['id']} ({secs}초, 첫 프레임 방식) ...")

        try:
            op = cli.models.generate_videos(
                model=cfg["model"],
                prompt=prompt,
                image=first_frame,
                config=types.GenerateVideosConfig(
                    aspect_ratio=cfg["aspect_ratio"],
                    resolution=cfg["resolution"],
                    duration_seconds=secs,
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


def concat_clips(cfg):
    """씬 순서대로 편집 없이 이어 붙여 output/final.mp4 를 만든다. 시험 클립은 제외."""
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        print("  [건너뜀] ffmpeg 가 없어 이어 붙이기를 못 했습니다.")
        return
    clips = [OUT_DIR / f"{s['id']}.mp4" for s in cfg["scenes"]]
    missing = [c.name for c in clips if not c.exists()]
    if missing:
        print(f"  [건너뜀] 아직 없는 클립이 있어 이어 붙이지 않습니다: {missing}")
        return
    listing = OUT_DIR / "concat_list.txt"
    listing.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    final = OUT_DIR / "final.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
         str(final)],
        check=True,
    )
    listing.unlink()
    print(f"  [완료] {final} (씬 {len(clips)}개를 순서대로 연결)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="all", choices=["script", "refs", "frames", "video", "concat", "all"])
    ap.add_argument("target", nargs="?", help="refs: 레퍼런스 이름 / video: 씬 id 일부")
    ap.add_argument("--dry", action="store_true", help="API 호출 없이 계획과 금액만 출력")
    ap.add_argument("--test", action="store_true", help="4초 시험 클립")
    ap.add_argument("--duration", type=int, help="길이(초) 직접 지정")
    ap.add_argument("--force", action="store_true", help="이미 있는 레퍼런스도 다시 생성")
    ap.add_argument("--model", help="영상 모델 덮어쓰기. 예: veo-3.1-lite-generate-preview")
    ap.add_argument("--over-budget", action="store_true", help="scenes.json 의 budget_won 을 넘어도 진행")
    ap.add_argument("--yes", action="store_true", help="금액 확인 질문 생략")
    args = ap.parse_args()

    global IMAGE_MODEL, IMAGE_USD
    cfg = load_config()
    IMAGE_MODEL = cfg.get("image_model", IMAGE_MODEL)
    IMAGE_USD = cfg.get("image_usd", IMAGE_USD)
    if args.model:
        cfg["model"] = args.model
    print(f"\n[{cfg['project']}] 모델: {cfg['model']}")

    if args.mode == "script":
        print_script(cfg, args.target)
        return

    if args.mode in ("video", "all"):
        print_script(cfg, args.target if args.mode == "video" else None)

    if args.mode in ("refs", "all") and not args.dry:
        print("\n레퍼런스 이미지")
        make_refs(client(), cfg, args.target if args.mode == "refs" else None, args.force)

    if args.mode in ("frames", "all") and not args.dry:
        print("\n시작 장면 이미지")
        make_frames(client(), cfg, args.target if args.mode == "frames" else None, args.force)

    if args.mode in ("video", "all"):
        print("\n영상 클립")
        only = args.target if args.mode == "video" else None
        plan = plan_videos(cfg, only, args.test, args.duration)
        secs, usd = print_plan(cfg, plan)
        check_budget(cfg, plan, usd, args.over_budget)
        if args.dry or secs == 0:
            print("\n(사전 점검만 수행, API 호출 없음)\n" if args.dry else "")
            return
        if not args.yes:
            if input("  진행할까요? [y/N] ").strip().lower() != "y":
                sys.exit("취소했습니다.")
        make_videos(client(), cfg, plan)
        if not args.test and not only:
            print("\n이어 붙이기")
            concat_clips(cfg)

    if args.mode == "concat":
        print("\n이어 붙이기")
        concat_clips(cfg)

    print("\n끝. output/ 폴더 확인하세요.\n")


if __name__ == "__main__":
    main()
