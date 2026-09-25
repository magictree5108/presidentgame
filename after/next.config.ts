import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // satori 는 harfbuzzjs 의 wasm 을 파일로 읽는다. 번들링하면 경로가 깨지므로 런타임에 node_modules 에서 로드한다.
  serverExternalPackages: ["satori", "sharp"],
  // 서버에서 텍스트를 그릴 때 쓰는 한글 폰트를 서버리스 번들에 포함시킨다.
  outputFileTracingIncludes: {
    "/api/**": ["./src/assets/fonts/*", "./node_modules/harfbuzzjs/**", "./node_modules/yoga-layout/**"],
  },
  images: {
    // 생성 이미지는 Supabase 공개 버킷 또는 로컬 라우트에서 온다. next/image 최적화는 쓰지 않고 <img> 를 쓴다.
    unoptimized: true,
  },
};

export default nextConfig;
