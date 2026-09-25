import { FalProvider } from "./fal";
import { MockProvider } from "./mock";
import type { ImageEditProvider } from "./types";

/**
 * 프로바이더 선택.
 *
 * 환경변수
 *   IMAGE_PROVIDER   = "fal" | "mock"   (기본: FAL_KEY 가 있으면 fal, 없으면 mock)
 *   FACE_MODEL_ID    = 성형 후 얼굴 모델 (기본 fal-ai/flux-pro/kontext)
 *   PHOTO_MODEL_ID   = 인생샷 모델      (기본 fal-ai/nano-banana-pro/edit)
 *
 * 모델을 바꾸려면 위 env 만 바꾸면 된다. 입력 스키마가 다른 모델이면 fal.ts 의 MODEL_ADAPTERS 에 한 줄 추가.
 * fal 이 아닌 회사로 바꾸려면 types.ts 의 ImageEditProvider 를 구현한 파일을 만들고 아래 switch 에 추가.
 */
export const DEFAULT_FACE_MODEL = "fal-ai/flux-pro/kontext";
export const DEFAULT_PHOTO_MODEL = "fal-ai/nano-banana-pro/edit";

export type ProviderKind = "face" | "photo";

function providerName(): "fal" | "mock" {
  const explicit = process.env.IMAGE_PROVIDER;
  if (explicit === "fal" || explicit === "mock") return explicit;
  return process.env.FAL_KEY ? "fal" : "mock";
}

export function getProvider(kind: ProviderKind): ImageEditProvider {
  const modelId =
    kind === "face"
      ? process.env.FACE_MODEL_ID || DEFAULT_FACE_MODEL
      : process.env.PHOTO_MODEL_ID || DEFAULT_PHOTO_MODEL;

  switch (providerName()) {
    case "fal":
      return new FalProvider(modelId);
    case "mock":
      return new MockProvider(kind);
  }
}

/** 어떤 프로바이더가 실제로 쓰이는지 로그·헬스체크용 */
export function providerInfo() {
  return {
    provider: providerName(),
    face: process.env.FACE_MODEL_ID || DEFAULT_FACE_MODEL,
    photo: process.env.PHOTO_MODEL_ID || DEFAULT_PHOTO_MODEL,
  };
}

export type { ImageEditProvider, EditRequest, JobStatus, JobResult } from "./types";
