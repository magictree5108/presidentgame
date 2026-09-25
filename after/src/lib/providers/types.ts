/**
 * 이미지 생성 프로바이더 인터페이스.
 *
 * 모든 모델 호출은 이 인터페이스를 통해서만 이루어진다.
 * 새 모델이나 다른 API 회사로 갈아타려면 이 인터페이스를 구현하는 파일 하나를 추가하고
 * src/lib/providers/index.ts 에서 골라 주면 된다.
 *
 * 비동기 큐 방식이다. submit 으로 작업을 넣고, status 로 상태를 확인하고, result 로 결과를 받는다.
 * Vercel 서버리스 함수의 실행 시간 제한을 피하기 위해 서버는 절대 결과가 나올 때까지 기다리지 않는다.
 */

export type EditRequest = {
  /** 최종 프롬프트 (prompts/ 폴더에서 만들어진 문자열) */
  prompt: string;
  /**
   * 레퍼런스 이미지 URL. 외부 모델이 접근할 수 있는 임시 서명 URL이어야 한다.
   * 첫 번째가 가장 중요한 기준 이미지다. 단일 이미지 모델은 첫 번째만 쓴다.
   */
  imageUrls: string[];
  /** 요청 장수. 모델이 한 번에 못 만들면 프로바이더가 알아서 나눠 호출한다. */
  numImages: number;
  /** 결과 비율 힌트. 모델이 지원하지 않으면 무시한다. */
  aspectRatio?: string;
  /** 재현용 시드 */
  seed?: number;
};

export type JobState = "queued" | "running" | "done" | "failed";

export type JobStatus = {
  state: JobState;
  /** 큐 대기 순번 (있으면) */
  queuePosition?: number;
  /** 실패 사유 */
  error?: string;
};

export type GeneratedImage = {
  url: string;
  width?: number;
  height?: number;
  contentType?: string;
};

export type JobResult = {
  images: GeneratedImage[];
  seed?: number;
};

export interface ImageEditProvider {
  /** 로그·DB 기록용 식별자 (예: "fal:fal-ai/flux-pro/kontext") */
  readonly id: string;
  /** 작업 제출. 외부 작업 ID를 돌려준다. 여러 개로 나눠 제출했으면 쉼표로 이어 붙인 문자열이다. */
  submit(req: EditRequest): Promise<{ jobId: string }>;
  status(jobId: string): Promise<JobStatus>;
  result(jobId: string): Promise<JobResult>;
}
