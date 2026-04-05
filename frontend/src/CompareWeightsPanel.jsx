import React from "react";

/** Keys must match backend INTERNAL_TO_FR_KEY / compare_weights.metrics[].key */
export const COMPARE_METRIC_DEFS = [
  { key: "skills", label: "Skills", pctKey: "skill_pct" },
  { key: "job_role", label: "Job role", pctKey: "job_pct" },
  { key: "money", label: "Pay / compensation", pctKey: "money_pct" },
  { key: "duration", label: "Duration", pctKey: "duration_pct" },
  { key: "gpax", label: "GPA", pctKey: "gpax_pct" },
  { key: "education", label: "Education level", pctKey: "education_pct" },
  { key: "languages", label: "Languages", pctKey: "language_pct" },
  { key: "standardized_tests", label: "Standardized tests", pctKey: "standardized_test_pct" },
];

/** @param {string} raw */
export function sanitizeIntPercentString(raw) {
  const digits = String(raw).replace(/\D/g, "");
  if (digits === "") return "";
  const n = Math.min(100, parseInt(digits, 10));
  return String(n);
}

export function buildEmptyWeightRows() {
  return Object.fromEntries(
    COMPARE_METRIC_DEFS.map((d) => [d.key, { percent: "0", apply: true }])
  );
}

/** @param {Record<string, unknown>} wrow from GET /api/employer/compatibility-weights */
export function weightRowFromEmployer(wrow) {
  return Object.fromEntries(
    COMPARE_METRIC_DEFS.map((d) => [
      d.key,
      {
        percent: String(Math.round(Number(wrow[d.pctKey] ?? 0))),
        apply: true,
      },
    ])
  );
}

/**
 * @param {Record<string, { percent: string, apply: boolean }>} weightRows
 */
export function sumAppliedPercents(weightRows) {
  let s = 0;
  for (const d of COMPARE_METRIC_DEFS) {
    const row = weightRows[d.key];
    if (!row?.apply) continue;
    const n = parseInt(row.percent, 10);
    if (!Number.isNaN(n)) s += n;
  }
  return s;
}

export default function CompareWeightsPanel({
  weightRows,
  onPercentChange,
  onApplyChange,
  appliedSum,
  jobIsInternPreview,
}) {
  const remainder = 100 - appliedSum;
  const skillsApplied = weightRows.skills?.apply !== false;

  return (
    <section className="compare-weights" aria-label="Compare weight controls">
      <h3 className="compare-weights__title">Metric weights for this comparison</h3>
      <p className="compare-weights__intro">
        Use whole-number percents. Applied metrics must sum to <strong>at most 100%</strong>. If the
        sum is <strong>under 100%</strong>, the remainder is added to <strong>Skills</strong> (if
        Skills is applied); otherwise it is split across other applied metrics. If the sum is{" "}
        <strong>over 100%</strong>, Compare is blocked. Uncheck <em>Apply</em> to drop a metric from
        this run (0% weight). Empty fields on <strong>both</strong> resume and JD for a metric
        remove that slice and redistribute it on the server.
      </p>
      {jobIsInternPreview && (
        <p className="compare-weights__intern">
          This job is an <strong>internship</strong>: pay is treated as vacuous and its weight is
          redistributed automatically.
        </p>
      )}
      <div className="compare-weights__sum">
        <span>
          Applied total: <strong>{appliedSum}%</strong>
        </span>
        {appliedSum < 100 && (
          <span className="compare-weights__sum-note">
            {skillsApplied
              ? ` → ${remainder}% will be added to Skills before scoring.`
              : ` → ${remainder}% will be split across other applied metrics.`}
          </span>
        )}
        {appliedSum > 100 && (
          <span className="compare-weights__sum-error">Must be ≤ 100% to compare.</span>
        )}
      </div>
      <div className="compare-weights__grid">
        {COMPARE_METRIC_DEFS.map((d) => {
          const row = weightRows[d.key] || { percent: "0", apply: true };
          return (
            <div key={d.key} className="compare-weights__row">
              <label className="compare-weights__apply">
                <input
                  type="checkbox"
                  checked={row.apply}
                  onChange={(e) => onApplyChange(d.key, e.target.checked)}
                />
                <span className="compare-weights__label">{d.label}</span>
              </label>
              <div className="compare-weights__pct-wrap">
                <input
                  type="text"
                  inputMode="numeric"
                  className="compare-weights__pct-input"
                  disabled={!row.apply}
                  value={row.apply ? row.percent : "0"}
                  onChange={(e) => onPercentChange(d.key, sanitizeIntPercentString(e.target.value))}
                  aria-label={`${d.label} percent`}
                />
                <span className="compare-weights__pct-suffix">%</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
