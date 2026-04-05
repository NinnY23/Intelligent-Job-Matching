/** Helpers for compatibility-metric extraction preview (resume + JD). */

export function formatSkill(item) {
  if (item == null) return "";
  if (typeof item === "string") return item;
  if (typeof item !== "object") return String(item);
  const name = item.name || "";
  const level = item.compatibilityLevel || "";
  const ev = item.evidence;
  const base = [name, level].filter(Boolean).join(" — ");
  if (ev) return `${base}${base ? " · " : ""}${ev}`;
  return base || JSON.stringify(item);
}

export function formatTest(item) {
  if (item == null) return "";
  if (typeof item === "string") return item;
  if (typeof item !== "object") return String(item);
  const raw = item.rawScore != null && item.rawScore !== "" ? item.rawScore : item.score;
  const parts = [
    item.testName || item.name,
    raw != null && raw !== "" ? `score: ${raw}` : null,
    item.normalizedScore != null && item.normalizedScore !== ""
      ? `norm: ${item.normalizedScore}`
      : null,
    item.grade,
    item.sourceText,
  ].filter(Boolean);
  return parts.length ? parts.join(" | ") : JSON.stringify(item);
}

export function formatLanguage(item) {
  if (item == null) return "";
  if (typeof item === "string") return item;
  if (typeof item !== "object") return String(item);
  const parts = [
    item.language || item.name,
    item.level || item.proficiencyLevel,
    item.framework || item.certification,
  ].filter(Boolean);
  return parts.length ? parts.join(" — ") : JSON.stringify(item);
}

export function testsFromExtraction(ext) {
  if (!ext || typeof ext !== "object") return [];
  return ext.standardizedTests || ext.standardTestScores || [];
}
