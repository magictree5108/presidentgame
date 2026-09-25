"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";

/** 내 데이터 즉시 삭제. 확인 후 원본·생성물·공유 카드를 모두 지우고 처음으로 보낸다. */
export function DeleteDataButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const onClick = async () => {
    if (!confirm("원본 사진, 생성 이미지, 공유 링크가 모두 즉시 삭제돼요. 계속할까요?")) return;
    setBusy(true);
    await fetch("/api/delete", { method: "POST" });
    setBusy(false);
    router.push("/?deleted=1");
  };
  return (
    <button onClick={onClick} disabled={busy} className="py-2 text-xs text-muted underline underline-offset-2">
      {busy ? "삭제 중…" : "내 데이터 즉시 삭제"}
    </button>
  );
}
