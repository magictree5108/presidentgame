"use client";
/**
 * 클라이언트 얼굴 감지 (MediaPipe Face Detector, BlazeFace short-range).
 * 업로드 전에 얼굴이 0명이거나 2명 이상이면 거부한다.
 * wasm 은 jsDelivr CDN 에서, 모델 파일은 /public 에서 로드한다.
 */
import type { FaceDetector } from "@mediapipe/tasks-vision";

const MEDIAPIPE_VERSION = "1.0.1"; // package.json 의 @mediapipe/tasks-vision 버전과 맞춘다
const WASM_BASE = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}/wasm`;
const MODEL_PATH = "/mediapipe/blaze_face_short_range.tflite";

let detectorPromise: Promise<FaceDetector> | null = null;

async function getDetector(): Promise<FaceDetector> {
  if (!detectorPromise) {
    detectorPromise = (async () => {
      const { FaceDetector, FilesetResolver } = await import("@mediapipe/tasks-vision");
      const fileset = await FilesetResolver.forVisionTasks(WASM_BASE);
      return FaceDetector.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_PATH },
        runningMode: "IMAGE",
        minDetectionConfidence: 0.5,
      });
    })().catch((e) => {
      detectorPromise = null;
      throw e;
    });
  }
  return detectorPromise;
}

/** 파일을 640px 이하 캔버스로 줄여서 감지한다. 얼굴 수를 돌려준다. */
export async function countFaces(file: File): Promise<number> {
  const detector = await getDetector();
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, 640 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const result = detector.detect(canvas);
  return result.detections.length;
}

export type FaceCheck = { ok: true } | { ok: false; reason: string };

export async function checkFace(file: File): Promise<FaceCheck> {
  try {
    const n = await countFaces(file);
    if (n === 0) return { ok: false, reason: "얼굴을 찾지 못했어요. 밝은 곳에서 정면을 보고 다시 찍어 주세요." };
    if (n > 1) return { ok: false, reason: "여러 명이 있어요. 본인 한 명만 나온 사진을 올려 주세요." };
    return { ok: true };
  } catch (e) {
    console.error(e);
    return { ok: false, reason: "얼굴 감지기를 불러오지 못했어요. 네트워크를 확인하고 새로고침해 주세요." };
  }
}
