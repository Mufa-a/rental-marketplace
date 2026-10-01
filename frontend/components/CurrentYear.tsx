"use client";

import { useEffect, useState } from "react";

/** The year is computed in the browser so a long-lived static page never shows a stale year. */
export default function CurrentYear() {
  const [year, setYear] = useState<number>(new Date().getFullYear());
  useEffect(() => setYear(new Date().getFullYear()), []);
  return <span suppressHydrationWarning>{year}</span>;
}
