import React from "react";

const WEIGHT_KEY = {
  skills: "skill_pct",
  job_role: "job_pct",
  money: "money_pct",
  duration: "duration_pct",
  gpax: "gpax_pct",
  education: "education_pct",
  languages: "language_pct",
  standardized_tests: "standardized_test_pct",
};

const SUMMARY_ROWS = [
  { key: "skills", label: "Skills" },
  { key: "job_role", label: "Job role" },
  { key: "money", label: "Pay / compensation" },
  { key: "duration", label: "Duration" },
  { key: "gpax", label: "GPA" },
  { key: "education", label: "Education level" },
  { key: "languages", label: "Languages" },
  { key: "standardized_tests", label: "Standardized tests" },
];

function round1(n) {
  const x = Number(n);
  if (Number.isNaN(x)) return null;
  return Math.round(x * 10) / 10;
}

/**
 * Allocated = employer weight as % of the overall 100 compatibility points.
 * Credited = actual points earned toward that total from this dimension.
 */
export default function CompatibilitySummary({ result }) {
  if (!result) return null;

  const wf = result.weights_effective_fraction || {};
  const dimPct = result.dimensions_percent_of_total || {};
  const dim01 = result.dimension_scores_0_1 || {};
  const applyMap = result.compare_metric_apply || {};

  const visibleRows = SUMMARY_ROWS.filter(
    ({ key }) => applyMap[key] !== false
  );

  return (
    <section className="compare-summary" aria-label="Compatibility breakdown by metric">
      <h3 className="compare-summary__title">Score breakdown by metric</h3>
      <p className="compare-summary__intro">
        <strong>Allocated</strong> is how much of the overall 100% each metric is configured to
        represent (after your compare weights and any vacuous redistributions).{" "}
        <strong>Credited</strong> is how many percentage points you actually earned toward the
        total from that metric. <strong>Match strength</strong> is the raw 0–100 match before
        applying the weight. Metrics you left unapplied on the compare page are omitted here.
      </p>

      <div className="compare-summary__table-wrap">
        <table className="compare-summary__table">
          <thead>
            <tr>
              <th scope="col">Metric</th>
              <th scope="col" className="compare-summary__num">
                Allocated
                <span className="compare-summary__th-sub">% of total</span>
              </th>
              <th scope="col" className="compare-summary__num">
                Credited
                <span className="compare-summary__th-sub">toward total</span>
              </th>
              <th scope="col" className="compare-summary__num">
                % of budget
                <span className="compare-summary__th-sub">used</span>
              </th>
              <th scope="col" className="compare-summary__num">
                Match strength
                <span className="compare-summary__th-sub">0–100</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map(({ key, label }) => {
              const wk = WEIGHT_KEY[key];
              const allocatedFrac = wf[wk] ?? 0;
              const allocatedPct = round1(allocatedFrac * 100);
              const credited = round1(dimPct[key] ?? 0);
              const raw01 = dim01[key];
              const rawPct =
                raw01 != null && !Number.isNaN(Number(raw01))
                  ? round1(Number(raw01) * 100)
                  : null;

              const isMoney = key === "money";
              const skipIntern = isMoney && result.job_is_intern;

              let pctOfBudget = null;
              if (!skipIntern && allocatedFrac > 0 && credited != null) {
                pctOfBudget = round1((credited / (allocatedFrac * 100)) * 100);
              }

              const utilizationWidth =
                pctOfBudget != null ? Math.min(100, Math.max(0, pctOfBudget)) : 0;

              return (
                <tr key={key}>
                  <th scope="row" className="compare-summary__metric">
                    {label}
                    {skipIntern && (
                      <span className="compare-summary__badge">intern — not scored</span>
                    )}
                  </th>
                  <td className="compare-summary__num">
                    {skipIntern || allocatedPct === 0 ? (
                      <span className="compare-summary__dash">—</span>
                    ) : (
                      <>{allocatedPct}%</>
                    )}
                  </td>
                  <td className="compare-summary__num">
                    {skipIntern ? (
                      <span className="compare-summary__dash">—</span>
                    ) : (
                      <span className="compare-summary__credited">{credited}%</span>
                    )}
                  </td>
                  <td className="compare-summary__util">
                    {skipIntern || pctOfBudget == null ? (
                      <span className="compare-summary__dash">—</span>
                    ) : (
                      <div className="compare-summary__bar-wrap" title={`${pctOfBudget}% of allocated budget`}>
                        <div
                          className="compare-summary__bar"
                          style={{ width: `${utilizationWidth}%` }}
                        />
                        <span className="compare-summary__util-label">{pctOfBudget}%</span>
                      </div>
                    )}
                  </td>
                  <td className="compare-summary__num">
                    {skipIntern ? (
                      <span className="compare-summary__dash">—</span>
                    ) : rawPct != null ? (
                      <>{rawPct}%</>
                    ) : (
                      <span className="compare-summary__dash">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="compare-summary__foot">
              <th scope="row">Total</th>
              <td className="compare-summary__num">
                {round1(
                  visibleRows.reduce(
                    (s, { key }) => s + (wf[WEIGHT_KEY[key]] ?? 0) * 100,
                    0
                  )
                )}
                %
              </td>
              <td className="compare-summary__num compare-summary__credited-strong">
                {round1(result.compatibility_percent)}%
              </td>
              <td colSpan={2} className="compare-summary__foot-note">
                Overall compatibility (capped at 100%)
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
