import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getStore } from "@/lib/store";
import { BRAND, appUrl } from "@/lib/brand";
import { DISCLAIMER } from "../../../../content/legal/disclaimer";

/**
 * 공개 공유 페이지. 성형 후 얼굴 + 인생샷만 보여준다. 원본 사진은 절대 노출하지 않는다.
 * OG 이미지는 공유 생성 시 미리 합성해 둔 public 버킷 파일이다.
 */

export const dynamic = "force-dynamic";

async function loadShare(id: string) {
  const store = await getStore();
  const share = await store.getShare(id);
  if (!share || new Date(share.expiresAt).getTime() < Date.now()) return null;
  return {
    share,
    after: store.publicUrl(share.afterPath),
    photos: share.photoPaths.map((p) => store.publicUrl(p)),
    og: store.publicUrl(share.ogPath),
  };
}

export async function generateMetadata({ params }: PageProps<"/s/[id]">): Promise<Metadata> {
  const { id } = await params;
  const data = await loadShare(id);
  if (!data) return { title: "만료된 링크" };
  const title = `성형 후 내 모습 미리 보기 · ${BRAND.name}`;
  const description = `${data.share.caption} — AI 시뮬레이션이며 실제 의료 결과가 아닙니다.`;
  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `${appUrl()}/s/${id}`,
      images: [{ url: data.og, width: 1200, height: 630, alt: title }],
      type: "website",
    },
    twitter: { card: "summary_large_image", title, description, images: [data.og] },
    robots: { index: false },
  };
}

export default async function SharePage({ params }: PageProps<"/s/[id]">) {
  const { id } = await params;
  const data = await loadShare(id);
  if (!data) notFound();

  return (
    <div className="mx-auto flex w-full max-w-md flex-1 flex-col px-4 pb-10">
      <header className="flex items-center justify-between py-4">
        <Link href="/" className="flex items-baseline gap-1.5">
          <span className="text-xl font-bold tracking-tight">{BRAND.name}</span>
          <span className="text-xs font-bold text-accent">{BRAND.nameEn}</span>
        </Link>
        <span className="rounded-full bg-accent-soft px-2.5 py-1 text-[11px] font-semibold">AI 시뮬레이션</span>
      </header>
      <main className="flex flex-col gap-5">
        <section>
          <h1 className="text-2xl font-bold tracking-tight">성형 후 내 모습, 미리 봤어요</h1>
          <p className="mt-1 text-sm text-muted">{data.share.caption}</p>
        </section>
        <div className="overflow-hidden rounded-2xl bg-surface" style={{ aspectRatio: "3 / 4" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={data.after} alt="성형 후 시뮬레이션 얼굴" className="h-full w-full object-cover" />
        </div>
        <div className="grid grid-cols-2 gap-2">
          {data.photos.map((u, i) => (
            <div key={u} className="overflow-hidden rounded-xl bg-surface" style={{ aspectRatio: "4 / 5" }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={u} alt={`AI 인생샷 ${i + 1}`} className="h-full w-full object-cover" />
            </div>
          ))}
        </div>
        <Link href="/" className="btn btn-accent">
          나도 해보기 · 무료
        </Link>
        <p className="text-xs leading-relaxed text-muted">{DISCLAIMER.share}</p>
      </main>
    </div>
  );
}
