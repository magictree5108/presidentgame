import Link from "next/link";
import { BRAND } from "@/lib/brand";

export default function NotFound() {
  return (
    <div className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="text-4xl">⏳</p>
      <h1 className="text-xl font-bold">만료됐거나 삭제된 링크예요</h1>
      <p className="text-sm text-muted">{BRAND.name}의 공유 링크는 7일 뒤 자동으로 사라져요.</p>
      <Link href="/" className="btn btn-primary">
        나도 해보기
      </Link>
    </div>
  );
}
