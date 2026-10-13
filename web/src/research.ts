export type ResearchStatus = "retained" | "rejected" | "diagnostic" | "parked";
export interface ResearchCase {
  id: string;
  date: string;
  family: string;
  status: ResearchStatus;
  methodLabel: string;
  title: string;
  question: string;
  method: string;
  evidence: string;
  decision: string;
  lesson: string;
  sources: { title: string; path: string }[];
}
export interface Chronicle {
  name: string;
  shortName: string;
  strategy: string;
  asof: string;
  cases: ResearchCase[];
}
export const statusLabel: Record<ResearchStatus, string> = {
  retained: "保留",
  rejected: "淘汰",
  diagnostic: "研究保留",
  parked: "暂缓",
};
export function matchCase(c: ResearchCase, query: string) {
  const text = [
    c.id,
    c.title,
    c.family,
    c.methodLabel,
    c.question,
    c.method,
    c.evidence,
    c.decision,
    c.lesson,
  ]
    .join(" ")
    .toLowerCase();
  return query
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .every((term) => text.includes(term));
}
