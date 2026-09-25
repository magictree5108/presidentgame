// 스모크 테스트용 가짜 얼굴 이미지 생성 (실제 얼굴 아님. 브라우저 얼굴 감지는 통과하지 않는다. API 직접 호출 테스트 전용)
import sharp from "sharp";
const svg = `<svg width="900" height="1200"><rect width="900" height="1200" fill="#f3d9c6"/><ellipse cx="450" cy="560" rx="260" ry="340" fill="#e8b89a"/><circle cx="350" cy="500" r="30" fill="#222"/><circle cx="550" cy="500" r="30" fill="#222"/><path d="M380 720 Q450 780 520 720" stroke="#a0524d" stroke-width="14" fill="none"/><text x="450" y="1120" font-size="60" text-anchor="middle" fill="#333">TEST</text></svg>`;
const out = process.argv[2] ?? "scripts/test-face.jpg";
await sharp(Buffer.from(svg)).jpeg().toFile(out);
console.log("wrote", out);
