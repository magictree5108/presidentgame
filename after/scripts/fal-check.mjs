#!/usr/bin/env node
/**
 * fal.ai 키·모델 ID 확인 스크립트. 키를 받은 뒤 가장 먼저 실행한다.
 *   FAL_KEY=... node scripts/fal-check.mjs [이미지경로]
 * 1) 두 모델 엔드포인트에 아주 작은 요청을 큐로 제출하고 완료까지 기다린다.
 * 2) 응답 스키마(images[].url)가 프로바이더 어댑터(src/lib/providers/fal.ts)와 맞는지 확인한다.
 * 이미지 경로를 주지 않으면 scripts/test-face.jpg 를 쓴다(없으면 make-test-face.mjs 로 만든다).
 * 비용: Kontext 1장(~$0.04) + Nano Banana Pro 1장(~$0.15).
 */
import { createFalClient } from "@fal-ai/client";
import { readFile } from "node:fs/promises";

const key = process.env.FAL_KEY;
if (!key) {
  console.error("FAL_KEY 환경변수가 없습니다.");
  process.exit(1);
}
const fal = createFalClient({ credentials: key });
const faceModel = process.env.FACE_MODEL_ID || "fal-ai/flux-pro/kontext";
const photoModel = process.env.PHOTO_MODEL_ID || "fal-ai/nano-banana-pro/edit";
const imgPath = process.argv[2] || "scripts/test-face.jpg";

const file = new Blob([await readFile(imgPath)], { type: "image/jpeg" });
console.log("업로드 중:", imgPath);
const url = await fal.storage.upload(file);
console.log("fal storage URL:", url);

async function run(model, input) {
  console.log(`\n== ${model}`);
  const t0 = Date.now();
  const { request_id } = await fal.queue.submit(model, { input });
  console.log("request_id:", request_id);
  for (;;) {
    const st = await fal.queue.status(model, { requestId: request_id, logs: false });
    process.stdout.write(`  ${st.status}${"queue_position" in st ? ` (#${st.queue_position})` : ""}\r`);
    if (st.status === "COMPLETED") break;
    await new Promise((r) => setTimeout(r, 2000));
  }
  const { data } = await fal.queue.result(model, { requestId: request_id });
  const imgs = data?.images ?? [];
  console.log(`\n  ${((Date.now() - t0) / 1000).toFixed(1)}s, images: ${imgs.length}`);
  for (const im of imgs) console.log("   ", im.url, im.width && im.height ? `${im.width}x${im.height}` : "");
  if (!imgs.length || !imgs[0].url) throw new Error("images[].url 이 없습니다. 어댑터를 확인하세요.");
  return data;
}

await run(faceModel, {
  prompt: "Keep this exact same person, same identity, expression, hair, background and lighting. Edits: slightly refine the nose bridge. Keep everything else unchanged.",
  image_url: url,
  num_images: 1,
  guidance_scale: 3.5,
  output_format: "jpeg",
  safety_tolerance: "3",
});

await run(photoModel, {
  prompt: "TOP PRIORITY: preserve the exact facial identity of the person in the first reference image. Scene: a minimalist cafe in Seoul, candid photo, medium shot. Photorealistic.",
  image_urls: [url],
  num_images: 1,
  aspect_ratio: "4:5",
  output_format: "jpeg",
  resolution: "1K",
  limit_generations: false,
});

console.log("\n두 모델 모두 정상. .env.local 에 FAL_KEY 를 넣고 npm run dev 로 실제 플로우를 확인하세요.");
