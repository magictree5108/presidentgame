import type { Generation } from "./types";

/** 생성 행에 딸린 private 버킷 경로(워터마크 없는 사본). 삭제·정리 시 함께 지운다. */
export function privateGenerationPaths(gen: Generation): string[] {
  const p = gen.params ?? {};
  return Array.isArray(p.cleanPaths) ? [...(p.cleanPaths as string[])] : [];
}
