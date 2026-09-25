import { createFalClient, type FalClient } from "@fal-ai/client";
import type { EditRequest, ImageEditProvider, JobResult, JobStatus, GeneratedImage } from "./types";

/**
 * fal.ai 큐 API 프로바이더.
 *
 * 모델마다 입력 스키마가 조금씩 다르다. MODEL_ADAPTERS 에 모델 ID별로
 * "EditRequest → fal input" 변환과 "한 번에 몇 장까지 가능한지"를 적어 둔다.
 * 표에 없는 모델 ID는 기본 어댑터(image_urls 배열 + num_images)로 시도한다.
 */

type FalInput = Record<string, unknown>;

type ModelAdapter = {
  /** 한 번의 요청으로 만들 수 있는 최대 장수 */
  maxImagesPerCall: number;
  /** 요청 변환 */
  toInput: (req: EditRequest, numImages: number) => FalInput;
};

const kontextAdapter: ModelAdapter = {
  // Kontext pro 는 num_images 를 지원하지만 편집 일관성을 위해 1장씩 호출한다.
  maxImagesPerCall: 1,
  toInput: (req, numImages) => ({
    prompt: req.prompt,
    image_url: req.imageUrls[0],
    num_images: numImages,
    guidance_scale: Number(process.env.FACE_GUIDANCE_SCALE ?? 3.5),
    output_format: "jpeg",
    // 얼굴 편집이 과하게 차단되지 않도록 기본값(2)보다 한 단계 완화. 1(엄격)~6(느슨)
    safety_tolerance: process.env.FACE_SAFETY_TOLERANCE ?? "3",
    ...(req.seed !== undefined ? { seed: req.seed } : {}),
  }),
};

const nanoBananaAdapter: ModelAdapter = {
  maxImagesPerCall: 4,
  toInput: (req, numImages) => ({
    prompt: req.prompt,
    image_urls: req.imageUrls,
    num_images: numImages,
    aspect_ratio: req.aspectRatio ?? "4:5",
    output_format: "jpeg",
    resolution: process.env.PHOTO_RESOLUTION ?? "1K",
    // limit_generations=true 면 한 라운드에 1장으로 제한되므로 끈다.
    limit_generations: false,
    ...(req.seed !== undefined ? { seed: req.seed } : {}),
  }),
};

const defaultAdapter: ModelAdapter = {
  maxImagesPerCall: 4,
  toInput: (req, numImages) => ({
    prompt: req.prompt,
    image_urls: req.imageUrls,
    image_url: req.imageUrls[0],
    num_images: numImages,
    ...(req.aspectRatio ? { aspect_ratio: req.aspectRatio } : {}),
    ...(req.seed !== undefined ? { seed: req.seed } : {}),
  }),
};

/** 모델 ID 접두어로 어댑터를 고른다. 새 모델을 붙일 때 여기에 한 줄 추가. */
const MODEL_ADAPTERS: Array<[prefix: string, adapter: ModelAdapter]> = [
  ["fal-ai/flux-pro/kontext", kontextAdapter],
  ["fal-ai/flux-kontext", kontextAdapter],
  ["fal-ai/nano-banana", nanoBananaAdapter],
  ["fal-ai/gemini", nanoBananaAdapter],
];

function pickAdapter(modelId: string): ModelAdapter {
  for (const [prefix, adapter] of MODEL_ADAPTERS) {
    if (modelId.startsWith(prefix)) return adapter;
  }
  return defaultAdapter;
}

let cachedClient: FalClient | null = null;
function client(): FalClient {
  if (!cachedClient) {
    const credentials = process.env.FAL_KEY;
    if (!credentials) throw new Error("FAL_KEY 환경변수가 없습니다.");
    cachedClient = createFalClient({ credentials });
  }
  return cachedClient;
}

const JOB_SEP = ",";

export class FalProvider implements ImageEditProvider {
  readonly id: string;
  private adapter: ModelAdapter;

  constructor(private modelId: string) {
    this.id = `fal:${modelId}`;
    this.adapter = pickAdapter(modelId);
  }

  async submit(req: EditRequest): Promise<{ jobId: string }> {
    const fal = client();
    const calls: number[] = [];
    let remaining = req.numImages;
    while (remaining > 0) {
      const n = Math.min(remaining, this.adapter.maxImagesPerCall);
      calls.push(n);
      remaining -= n;
    }
    const ids = await Promise.all(
      calls.map(async (n, i) => {
        const input = this.adapter.toInput(
          { ...req, seed: req.seed !== undefined ? req.seed + i : undefined },
          n,
        );
        const res = await fal.queue.submit(this.modelId, { input });
        return res.request_id;
      }),
    );
    return { jobId: ids.join(JOB_SEP) };
  }

  async status(jobId: string): Promise<JobStatus> {
    const fal = client();
    const ids = jobId.split(JOB_SEP);
    const statuses = await Promise.all(
      ids.map((requestId) => fal.queue.status(this.modelId, { requestId, logs: false })),
    );
    if (statuses.every((s) => s.status === "COMPLETED")) return { state: "done" };
    const queued = statuses.find((s) => s.status === "IN_QUEUE");
    if (statuses.some((s) => s.status === "IN_PROGRESS")) return { state: "running" };
    return {
      state: "queued",
      queuePosition: queued && "queue_position" in queued ? queued.queue_position : undefined,
    };
  }

  async result(jobId: string): Promise<JobResult> {
    const fal = client();
    const ids = jobId.split(JOB_SEP);
    const results = await Promise.all(
      ids.map((requestId) => fal.queue.result(this.modelId, { requestId })),
    );
    const images: GeneratedImage[] = [];
    let seed: number | undefined;
    for (const r of results) {
      const data = r.data as {
        images?: Array<{ url: string; width?: number; height?: number; content_type?: string }>;
        seed?: number;
      };
      for (const img of data.images ?? []) {
        images.push({ url: img.url, width: img.width, height: img.height, contentType: img.content_type });
      }
      if (seed === undefined && typeof data.seed === "number") seed = data.seed;
    }
    if (images.length === 0) throw new Error("모델이 이미지를 돌려주지 않았습니다.");
    return { images, seed };
  }
}
