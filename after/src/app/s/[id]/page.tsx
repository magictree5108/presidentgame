import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getStore } from "@/lib/store";
import { BRAND, appUrl } from "@/lib/brand";
import { voteChoices, voteQuestion } from "@/lib/vote";
import { VotePanel } from "@/components/VotePanel";
import { DISCLAIMER } from "../../../../content/legal/disclaimer";

/**
 * 공개 공유 페이지. 성형 후 얼굴(비교 모드면 약·중·강 3장) + 인생샷 + 친구 투표.
 * 원본 사진은 절대 노출하지 않는다. OG 이미지는 공유 생성 시 미리 합성해 둔 public 파일이다.
 */

export const dynamic = "force-dynamic";

async function loadShare(id: string) {
  const store = await getStore();
  const share = await store.getShare(id);
  if (!share || new Date(share.expiresAt).getTime() < Date.now()) return null;
  const variants = share.variantPaths.length ? share.variantPaths : [share.afterPath];
  return {
    share,
    after: store.publicUrl(share.afterPath),
    variants: variants.map((p) => store.publicUrl(p)),
    photos: share.photoPaths.map((p) => store.publicUrl(p)),
    og: store.publicUrl(share.ogPath),
    question: voteQuestion(share.variantLabels.length),
    choices: voteChoices(share.variantLabels),
  };
}

export async function generateMetadata({ params }: PageProps<"/s/[id]">): Promise<Metadata> {
  const { id } = await params;
  const data = await loadShare(id);
  if (!data) return { title: "만료된 링크" };
  const title = `${data.question} · ${BRAND.name}`;
  const description = `${data.share.caption} — 친구 투표에 한 표! AI 시뮬레이션이며 실제 의료 결과가 아닙니다.`;
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
  const store = await getStore();
  store.logEvent({ sessionId: null, name: "share_view", props: { shareId: id } }).catch(() => {});
  const isCompare = data.variants.length >= 2;

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
          <h1 className="text-2xl font-bold tracking-tight">{data.question}</h1>
          <p className="mt-1 text-sm text-muted">{data.share.caption}</p>
        </section>

        {isCompare ? (
          <div className="grid grid-cols-3 gap-2">
            {data.variants.map((u, i) => (
              <figure key={u} className="overflow-hidden rounded-xl bg-surface">
                <div style={{ aspectRatio: "3 / 4" }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={u} alt={`${data.share.variantLabels[i]} 강도 시뮬레이션`} className="h-full w-full object-cover" />
                </div>
                <figcaption className={`py-1.5 text-center text-sm font-semibold ${i === data.share.chosenIndex ? "bg-ink text-white" : ""}`}>
                  {data.share.variantLabels[i]}
                  {i === data.share.chosenIndex ? " · 본인 픽" : ""}
                </figcaption>
              </figure>
            ))}
          </div>
        ) : (
          <div className="overflow-hidden rounded-2xl bg-surface" style={{ aspectRatio: "3 / 4" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={data.after} alt="성형 후 시뮬레이션 얼굴" className="h-full w-full object-cover" />
          </div>
        )}

        <VotePanel shareId={id} question={data.question} choices={data.choices} />

        <section>
          <h2 className="mb-2 text-sm font-semibold text-muted">{isCompare ? `${data.share.variantLabels[data.share.chosenIndex]} 강도로 찍은 인생샷` : "이 얼굴로 찍은 인생샷"}</h2>
          <div className="grid grid-cols-2 gap-2">
            {data.photos.map((u, i) => (
              <div key={u} className="overflow-hidden rounded-xl bg-surface" style={{ aspectRatio: "4 / 5" }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={u} alt={`AI 인생샷 ${i + 1}`} className="h-full w-full object-cover" />
              </div>
            ))}
          </div>
        </section>

        <Link href="/?ref=share" className="btn btn-accent">
          나도 해보기 · 무료
        </Link>
        <p className="text-xs leading-relaxed text-muted">{DISCLAIMER.share}</p>
        <Link href="/privacy" className="text-xs text-muted underline underline-offset-2">
          사진은 어떻게 처리되나요?
        </Link>
      </main>
    </div>
  );
}
