import type { CreditKind } from "@/lib/config";

/**
 * 데이터 저장소 인터페이스.
 * 기본 구현은 Supabase(supabase.ts). 키 없이 로컬에서 돌릴 때는 파일 기반 구현(local.ts)을 쓴다.
 * 서버 코드는 이 인터페이스만 본다.
 */

export type Bucket = "private" | "public";

export type Session = {
  id: string;
  createdAt: string;
  ageConfirmedAt: string | null;
  consentAt: string | null;
  faceCredits: number;
  photoCredits: number;
  currentUploadId: string | null;
  currentFaceGenerationId: string | null;
  currentPhotoGenerationId: string | null;
  /** 마지막 시술 선택값 (prompts/surgery.ts SurgerySelection) */
  selection: unknown | null;
};

export type UploadKind = "front" | "side";

export type Upload = {
  id: string;
  sessionId: string;
  kind: UploadKind;
  path: string; // private 버킷 내 경로
  width: number;
  height: number;
  createdAt: string;
  expiresAt: string;
};

export type GenerationKind = "face" | "photo";
export type GenerationStatus = "queued" | "running" | "processing" | "done" | "failed";

export type Generation = {
  id: string;
  sessionId: string;
  kind: GenerationKind;
  providerId: string;
  externalJobId: string | null;
  status: GenerationStatus;
  prompt: string;
  /** 선택값(place/mood 또는 selection) */
  params: Record<string, unknown>;
  inputUploadIds: string[];
  inputGenerationId: string | null;
  /** 워터마크가 구워진 결과 이미지 경로 (public 버킷) */
  outputPaths: string[];
  error: string | null;
  createdAt: string;
  updatedAt: string;
  expiresAt: string;
};

export type Share = {
  id: string; // 짧은 슬러그
  sessionId: string;
  faceGenerationId: string;
  photoGenerationId: string;
  afterPath: string; // public (선택된 강도)
  /** 비교 모드일 때 약·중·강 3장 (public). 투표 화면에 쓴다. 단일 모드면 afterPath 하나. */
  variantPaths: string[];
  variantLabels: string[];
  chosenIndex: number;
  photoPaths: string[]; // public
  ogPath: string; // public
  storyPaths: string[]; // private (원본이 포함된 슬라이드가 있으므로)
  caption: string;
  createdAt: string;
  expiresAt: string;
};

/** 공유 페이지 투표 */
export type VoteTally = Record<string, number>;

/** 퍼널 이벤트 */
export type EventRow = { sessionId: string | null; name: string; props: Record<string, unknown>; createdAt: string };

export type RateLimitResult = { allowed: boolean; retryAfterSeconds: number };

export type CleanupReport = {
  uploads: number;
  generations: number;
  shares: number;
  blobs: number;
};

export interface Store {
  // 세션
  getSession(id: string): Promise<Session | null>;
  createSession(id: string, init: { ageConfirmedAt: string; consentAt: string; faceCredits: number; photoCredits: number }): Promise<Session>;
  updateSession(id: string, patch: Partial<Omit<Session, "id" | "createdAt">>): Promise<Session>;

  // 크레딧 (원자적)
  consumeCredits(sessionId: string, kind: CreditKind, amount: number): Promise<boolean>;
  refundCredits(sessionId: string, kind: CreditKind, amount: number): Promise<void>;

  // 분당 제한 (원자적)
  checkRateLimit(sessionId: string, key: string, limit: number, windowSeconds: number): Promise<RateLimitResult>;

  // 업로드
  createUpload(u: Omit<Upload, "id" | "createdAt">): Promise<Upload>;
  getUpload(id: string): Promise<Upload | null>;
  listUploads(sessionId: string): Promise<Upload[]>;
  deleteUploads(ids: string[]): Promise<void>;

  // 생성
  createGeneration(g: Omit<Generation, "id" | "createdAt" | "updatedAt">): Promise<Generation>;
  getGeneration(id: string): Promise<Generation | null>;
  updateGeneration(id: string, patch: Partial<Omit<Generation, "id" | "createdAt">>): Promise<Generation>;
  listGenerations(sessionId: string): Promise<Generation[]>;

  // 공유
  createShare(s: Omit<Share, "createdAt">): Promise<Share>;
  getShare(id: string): Promise<Share | null>;
  listShares(sessionId: string): Promise<Share[]>;

  // 투표 (voterKey 당 공유 1개에 1표, 다시 누르면 변경)
  castVote(shareId: string, voterKey: string, choice: string): Promise<void>;
  getVote(shareId: string, voterKey: string): Promise<string | null>;
  getVoteTally(shareId: string): Promise<VoteTally>;

  // 퍼널 이벤트 (분석용, 실패해도 흐름을 막지 않는다)
  logEvent(e: Omit<EventRow, "createdAt">): Promise<void>;

  // 대기 리스트
  addToWaitlist(email: string, sessionId: string | null): Promise<void>;

  // 삭제
  deleteSessionData(sessionId: string): Promise<CleanupReport>;
  cleanupExpired(now: Date): Promise<CleanupReport>;

  // 블롭
  putBlob(bucket: Bucket, path: string, data: Buffer, contentType: string): Promise<void>;
  getBlob(bucket: Bucket, path: string): Promise<Buffer | null>;
  deleteBlobs(bucket: Bucket, paths: string[]): Promise<void>;
  /** 외부 모델과 브라우저가 잠시 접근할 수 있는 서명 URL (private 버킷) */
  signedUrl(bucket: Bucket, path: string, expiresSeconds: number): Promise<string>;
  /** public 버킷의 영구 URL */
  publicUrl(path: string): string;
}
