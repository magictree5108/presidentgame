import type { EditRequest, ImageEditProvider, JobResult, JobStatus } from "./types";

/**
 * 목 프로바이더. API 키 없이 전체 플로우를 돌려 보기 위한 것.
 * 실제 모델 대신 첫 번째 입력 이미지를 그대로 돌려준다.
 * 눈으로 "생성이 됐다"는 것을 구분할 수 있도록 결과 URL 에 mock 파라미터를 붙인다.
 * 이미지 파이프라인(다운로드 → 워터마크 → 저장)은 실제와 동일하게 지나간다.
 *
 * 처리 시간을 흉내 내려고 MOCK_DELAY_MS(기본 4000ms) 동안 queued → running → done 으로 바뀐다.
 */
type MockJob = { req: EditRequest; createdAt: number };
const jobs = new Map<string, MockJob>();

export class MockProvider implements ImageEditProvider {
  readonly id: string;
  private delay = Number(process.env.MOCK_DELAY_MS ?? 4000);

  constructor(label: string) {
    this.id = `mock:${label}`;
  }

  async submit(req: EditRequest): Promise<{ jobId: string }> {
    const jobId = `mock_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    jobs.set(jobId, { req, createdAt: Date.now() });
    return { jobId };
  }

  async status(jobId: string): Promise<JobStatus> {
    const job = jobs.get(jobId);
    if (!job) return { state: "failed", error: "mock job not found" };
    const elapsed = Date.now() - job.createdAt;
    if (elapsed < this.delay / 2) return { state: "queued", queuePosition: 1 };
    if (elapsed < this.delay) return { state: "running" };
    return { state: "done" };
  }

  async result(jobId: string): Promise<JobResult> {
    const job = jobs.get(jobId);
    if (!job) throw new Error("mock job not found");
    const src = job.req.imageUrls[0];
    const images = Array.from({ length: job.req.numImages }, (_, i) => ({
      url: src + (src.includes("?") ? "&" : "?") + `mock=${i + 1}`,
    }));
    jobs.delete(jobId);
    return { images, seed: 0 };
  }
}
