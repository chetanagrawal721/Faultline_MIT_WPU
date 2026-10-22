const SITE_REASON = /^bind:\S+?:\d+:\d+: (.+)$/;

/** The same reason given for many call sites is one line with a count ("12 call sites: the entry was skipped ..."); other reasons stay as they are. */
export function groupReasons(reasons: string[]): string[] {
  const counts = new Map<string, number>();
  const others: string[] = [];
  for (const r of reasons) {
    const m = SITE_REASON.exec(r);
    if (m) counts.set(m[1], (counts.get(m[1]) ?? 0) + 1);
    else others.push(r);
  }
  return [...[...counts.entries()].map(([why, n]) => `${n} call site${n === 1 ? "" : "s"}: ${why}`), ...others];
}

/** A headline that lists one reason per call site reads as one sentence with counts. */
export function summarise(text: string): string {
  const m = /^(.*?): (bind:.*)$/s.exec(text);
  if (!m) return text;
  const parts = m[2].split(/;\s*/).map((x) => x.replace(/\.$/, "")).filter(Boolean);
  const grouped = groupReasons(parts);
  return grouped.length ? `${m[1]}: ${grouped.join("; ")}.` : text;
}
