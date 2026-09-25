import type { Metadata } from "next";
import { Shell } from "@/components/Shell";
import { BRAND } from "@/lib/brand";
import { POLICY } from "@/lib/config";
import { FACE_CONSENT } from "../../../content/legal/face-consent";
import { AGE_GATE } from "../../../content/legal/age-gate";
import { DISCLAIMER } from "../../../content/legal/disclaimer";

export const metadata: Metadata = { title: "사진 처리 안내" };

/** 사진·데이터 처리 안내. 문구는 content/legal/ 에서 온다. 법률 검토 후 확정할 것. */
export default function PrivacyPage() {
  return (
    <Shell>
      <h1 className="text-2xl font-bold tracking-tight">사진은 이렇게 처리돼요</h1>
      <section className="card flex flex-col gap-2 text-sm leading-relaxed">
        <h2 className="font-semibold">얼굴 사진</h2>
        <ul className="list-disc space-y-1 pl-5 text-muted">
          {FACE_CONSENT.details.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
      </section>
      <section className="card flex flex-col gap-2 text-sm leading-relaxed">
        <h2 className="font-semibold">보관 기간</h2>
        <ul className="list-disc space-y-1 pl-5 text-muted">
          <li>원본 사진: 업로드 후 {POLICY.originalRetentionHours}시간</li>
          <li>생성 이미지·공유 카드·공유 링크: {POLICY.generatedRetentionHours / 24}일</li>
          <li>언제든 결과 화면의 「내 데이터 즉시 삭제」로 바로 지울 수 있어요.</li>
        </ul>
      </section>
      <section className="card flex flex-col gap-2 text-sm leading-relaxed">
        <h2 className="font-semibold">투표</h2>
        <p className="text-muted">공유 링크의 투표는 익명이에요. 투표한 브라우저를 구분하기 위한 무작위 쿠키만 저장하고, 투표 기록은 공유 링크가 삭제될 때 함께 삭제돼요.</p>
      </section>
      <section className="card flex flex-col gap-2 text-sm leading-relaxed">
        <h2 className="font-semibold">이용 연령</h2>
        <p className="text-muted">{AGE_GATE.helper}</p>
      </section>
      <section className="card flex flex-col gap-2 text-sm leading-relaxed">
        <h2 className="font-semibold">시뮬레이션 고지</h2>
        <p className="text-muted">{DISCLAIMER.long}</p>
        <p className="text-muted">{BRAND.name}는 특정 병원, 의사, 시술, 가격 정보를 제공하거나 추천하지 않아요.</p>
      </section>
    </Shell>
  );
}
