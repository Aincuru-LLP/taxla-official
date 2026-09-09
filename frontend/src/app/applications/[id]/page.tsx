"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function ApplicationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;

  useEffect(() => {
    if (id) {
      router.replace(`/applications/${id}/overview`);
    }
  }, [id, router]);

  return (
    <div className="p-12 text-center text-sm text-slate-400">
      Loading application overview…
    </div>
  );
}
