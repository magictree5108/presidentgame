import Link from "next/link";
import { BRAND } from "@/lib/brand";
import { DISCLAIMER } from "../../content/legal/disclaimer";

/** 모바일 우선 공통 레이아웃. 상단 브랜드, 하단 고지. */
export function Shell({ children, step, showDisclaimer = true }: { children: React.ReactNode; step?: string; showDisclaimer?: boolean }) {
  return (
    <div className="mx-auto flex w-full max-w-md flex-1 flex-col px-4 pb-10">
      <header className="flex items-center justify-between py-4">
        <Link href="/" className="flex items-baseline gap-1.5">
          <span className="text-xl font-bold tracking-tight">{BRAND.name}</span>
          <span className="text-xs font-bold text-accent">{BRAND.nameEn}</span>
        </Link>
        {step ? <span className="text-xs text-muted">{step}</span> : null}
      </header>
      <main className="flex flex-1 flex-col gap-5">{children}</main>
      {showDisclaimer ? (
        <footer className="mt-8 border-t border-line pt-4 text-xs leading-relaxed text-muted">{DISCLAIMER.short}</footer>
      ) : null}
    </div>
  );
}
