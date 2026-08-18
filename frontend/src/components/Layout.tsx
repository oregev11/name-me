import type { ReactNode } from "react";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <main dir="rtl">
      <h1>שם לי 👶</h1>
      <p className="subtitle">
        הקלידו שם או שניים שאהבתם, וקבלו שמות עבריים דומים בעזרת למידת מכונה.
      </p>
      {children}
    </main>
  );
}
