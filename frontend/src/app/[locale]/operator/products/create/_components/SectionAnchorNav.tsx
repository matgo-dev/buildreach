"use client";

import { useEffect, useState, type RefObject } from "react";
import { useTranslations } from "next-intl";

interface Props {
  sectionRefs: {
    basic: RefObject<HTMLDivElement | null>;
    sku: RefObject<HTMLDivElement | null>;
    images: RefObject<HTMLDivElement | null>;
  };
}

const SECTIONS = ["basic", "sku", "images"] as const;

export function SectionAnchorNav({ sectionRefs }: Props) {
  const t = useTranslations("productCreate");
  const [active, setActive] = useState<string>("basic");

  const labels: Record<string, string> = {
    basic: `① ${t("anchor_basic")}`,
    sku: `② ${t("anchor_sku")}`,
    images: `③ ${t("anchor_images")}`,
  };

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const id = entry.target.id.replace("section-", "");
            setActive(id);
          }
        }
      },
      { rootMargin: "-80px 0px -60% 0px" }
    );

    for (const key of SECTIONS) {
      const el = sectionRefs[key].current;
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [sectionRefs]);

  const scrollTo = (key: string) => {
    sectionRefs[key as keyof typeof sectionRefs].current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="sticky top-0 z-20 flex flex-wrap gap-1.5 border-b-2 border-slate-200 bg-white px-5 py-3">
      {SECTIONS.map((key) => (
        <button
          key={key}
          type="button"
          onClick={() => scrollTo(key)}
          className={`rounded px-3.5 py-1 text-[13px] font-medium transition-colors ${
            active === key
              ? "bg-blue-800 text-white"
              : "bg-slate-100 text-slate-500 hover:bg-slate-200"
          }`}
        >
          {labels[key]}
        </button>
      ))}
    </div>
  );
}
