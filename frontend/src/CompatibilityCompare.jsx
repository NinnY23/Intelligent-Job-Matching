import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  getEmployerCompatibilityWeights,
  listCompatibilityMetricExtractions,
  postCompatibilityMatch,
} from "./api";
import CompareWeightsPanel, {
  buildEmptyWeightRows,
  COMPARE_METRIC_DEFS,
  sumAppliedPercents,
  weightRowFromEmployer,
} from "./CompareWeightsPanel";
import { formatSkill, formatTest, formatLanguage } from "./metricsDisplay";
import CompatibilitySummary from "./CompatibilitySummary";
import "./CompatibilityCompare.css";

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

const METRIC_ROWS = [
  { key: "job_role", label: "Job role" },
  { key: "money", label: "Pay / compensation" },
  { key: "duration", label: "Duration" },
  { key: "gpax", label: "GPA" },
  { key: "education", label: "Education level" },
  { key: "languages", label: "Languages" },
  { key: "standardized_tests", label: "Standardized tests" },
];

function extractionLabel(row) {
  const role = row.jobRole || "—";
  const date = row.created_at || "";
  return `#${row.id} — ${role} — ${date}`;
}

function matchSkillEntry(extraction, slug) {
  if (!extraction?.skills?.length) return null;
  const sn = String(slug).toLowerCase();
  return extraction.skills.find((s) => {
    const name = (s.name || "").trim().toLowerCase();
    const unders = name.replace(/[^a-z0-9#.+]+/g, "_").replace(/^_+|_+$/g, "");
    return unders === sn || name.replace(/\s+/g, "") === sn.replace(/_/g, "");
  });
}

function skillLineForSlug(extraction, slug) {
  if (slug == null || slug === "") return null;
  const m = matchSkillEntry(extraction, slug);
  return m ? formatSkill(m) : String(slug).replace(/_/g, " ");
}

function pctOfCategory(result, dimKey) {
  const wk = WEIGHT_KEY[dimKey];
  const frac = result.weights_effective_fraction?.[wk] ?? 0;
  const earned = result.dimensions_percent_of_total?.[dimKey] ?? 0;
  const maxPts = frac * 100;
  if (maxPts <= 0) return null;
  return Math.round((earned / maxPts) * 1000) / 10;
}

function score01(result, dimKey) {
  const v = result.dimension_scores_0_1?.[dimKey];
  if (v == null || Number.isNaN(Number(v))) return null;
  return Math.round(Number(v) * 1000) / 10;
}

function renderResumeMetric(resume, key) {
  if (!resume) return "—";
  switch (key) {
    case "skills":
      return (
        <ul>
          {(resume.skills || []).map((s, i) => (
            <li key={`rs-${i}`}>{formatSkill(s)}</li>
          ))}
          {!(resume.skills || []).length && "—"}
        </ul>
      );
    case "job_role":
      return resume.jobRole || "—";
    case "money":
      return resume.moneyEstimate || "—";
    case "duration":
      return resume.duration || "—";
    case "gpax":
      return resume.gpax || "—";
    case "education":
      return resume.educationLevel || "—";
    case "languages":
      return (
        <ul>
          {(resume.languages || []).map((l, i) => (
            <li key={`rl-${i}`}>{formatLanguage(l)}</li>
          ))}
          {!(resume.languages || []).length && "—"}
        </ul>
      );
    case "standardized_tests":
      return (
        <ul>
          {(resume.standardizedTests || []).map((t, i) => (
            <li key={`rt-${i}`}>{formatTest(t)}</li>
          ))}
          {!(resume.standardizedTests || []).length && "—"}
        </ul>
      );
    default:
      return "—";
  }
}

function renderJobMetric(job, key) {
  if (!job) return "—";
  return renderResumeMetric(job, key);
}

export default function CompatibilityCompare() {
  const [list, setList] = useState([]);
  const [loadError, setLoadError] = useState("");
  const [resumeId, setResumeId] = useState("");
  const [jobId, setJobId] = useState("");
  const [result, setResult] = useState(null);
  const [compareError, setCompareError] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [weightRows, setWeightRows] = useState(buildEmptyWeightRows);
  const [weightsHint, setWeightsHint] = useState("");

  const load = useCallback(async () => {
    setLoadError("");
    setLoadingList(true);
    try {
      const data = await listCompatibilityMetricExtractions();
      setList(data.extractions || []);
    } catch (e) {
      setList([]);
      setLoadError(e.message || "Failed to load extractions");
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const w = await getEmployerCompatibilityWeights();
        if (cancelled) return;
        setWeightRows(weightRowFromEmployer(w));
        setWeightsHint("");
      } catch {
        if (!cancelled) {
          setWeightsHint("Using default 0% weights until employer weights load (check login).");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const resumes = useMemo(
    () => list.filter((r) => r.source_type === "resume"),
    [list]
  );
  const jobs = useMemo(
    () => list.filter((r) => r.source_type === "job_description"),
    [list]
  );

  const resumeRow = useMemo(
    () => resumes.find((r) => String(r.id) === String(resumeId)),
    [resumes, resumeId]
  );
  const jobRow = useMemo(
    () => jobs.find((r) => String(r.id) === String(jobId)),
    [jobs, jobId]
  );

  const appliedWeightSum = useMemo(() => sumAppliedPercents(weightRows), [weightRows]);

  const jobIsInternPreview = useMemo(() => {
    const t = String(jobRow?.employmentType || "").toLowerCase();
    return t === "intern" || t === "internship";
  }, [jobRow]);

  const handleWeightPercent = (key, value) => {
    setWeightRows((prev) => ({
      ...prev,
      [key]: { ...prev[key], percent: value },
    }));
  };

  const handleWeightApply = (key, apply) => {
    setWeightRows((prev) => ({
      ...prev,
      [key]: { ...prev[key], apply },
    }));
  };

  const handleCompare = async () => {
    setCompareError("");
    setResult(null);
    if (!resumeId || !jobId) {
      setCompareError("Select both a resume extraction and a job description extraction.");
      return;
    }
    if (appliedWeightSum > 100) {
      setCompareError(
        "Applied metric weights sum to over 100%. Lower some values or turn off Apply so the total is at most 100%."
      );
      return;
    }
    const anyApplied = COMPARE_METRIC_DEFS.some((d) => weightRows[d.key]?.apply);
    if (!anyApplied) {
      setCompareError("Turn on Apply for at least one metric.");
      return;
    }
    setComparing(true);
    try {
      const compare_weights = {
        metrics: COMPARE_METRIC_DEFS.map((d) => ({
          key: d.key,
          percent: parseInt(weightRows[d.key]?.percent, 10) || 0,
          apply: Boolean(weightRows[d.key]?.apply),
        })),
      };
      const data = await postCompatibilityMatch(
        Number(resumeId),
        Number(jobId),
        compare_weights
      );
      setResult(data);
    } catch (e) {
      setCompareError(e.message || "Compare failed");
    } finally {
      setComparing(false);
    }
  };

  const skillCategoryPct = result ? pctOfCategory(result, "skills") : null;
  const skillScore01 = result ? score01(result, "skills") : null;

  return (
    <div className="compare-page">
      <h2>Compare saved extractions</h2>
      <p style={{ fontSize: "clamp(0.85rem, 1.5vw, 0.95rem)", color: "#4a5568" }}>
        Choose a resume and a job description from your saved compatibility metric rows. The center
        column shows how much of each metric budget was achieved (side-by-side with extracted values).
      </p>

      {loadError && <div className="compare-error">{loadError}</div>}

      <div className="compare-controls">
        <label>
          Resume extraction (left)
          <select
            value={resumeId}
            onChange={(e) => setResumeId(e.target.value)}
            disabled={loadingList}
          >
            <option value="">— Select —</option>
            {resumes.map((r) => (
              <option key={r.id} value={r.id}>
                {extractionLabel(r)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Job description extraction (right)
          <select
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            disabled={loadingList}
          >
            <option value="">— Select —</option>
            {jobs.map((r) => (
              <option key={r.id} value={r.id}>
                {extractionLabel(r)}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="compare-run-btn"
          onClick={handleCompare}
          disabled={comparing || loadingList || appliedWeightSum > 100}
        >
          {comparing ? "Comparing…" : "Compare"}
        </button>
      </div>

      {weightsHint && (
        <p className="compare-weights__hint" style={{ color: "#718096", fontSize: "clamp(0.8rem, 1.4vw, 0.9rem)" }}>
          {weightsHint}
        </p>
      )}

      <CompareWeightsPanel
        weightRows={weightRows}
        onPercentChange={handleWeightPercent}
        onApplyChange={handleWeightApply}
        appliedSum={appliedWeightSum}
        jobIsInternPreview={jobIsInternPreview}
      />

      {compareError && <div className="compare-error">{compareError}</div>}

      {result && (
        <>
          <div className="compare-total">
            Overall compatibility: {result.compatibility_percent}%
            {result.job_is_intern && (
              <span style={{ fontWeight: 500, fontSize: "0.85em", marginLeft: "0.5rem" }}>
                (intern — pay metric excluded from weights)
              </span>
            )}
          </div>

          <CompatibilitySummary result={result} />

          {(result.compare_weight_adjustments || []).length > 0 && (
            <div className="compare-adjustments" role="status">
              <strong>Weight adjustments for this run:</strong>
              <ul>
                {(result.compare_weight_adjustments || []).map((line, i) => (
                  <li key={`adj-${i}`}>{line}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="compare-grid">
            <div className="compare-header-cell">Resume</div>
            <div className="compare-header-cell compare-header-cell--center">
              % of metric max
            </div>
            <div className="compare-header-cell compare-header-cell--jd">
              Job description
            </div>

            <div className="compare-section-title">Skills</div>

            <div className="compare-cell">
              {renderResumeMetric(resumeRow, "skills")}
            </div>
            <div className="compare-cell compare-cell--center">
              <span className="compare-pct-main">
                {skillCategoryPct != null ? `${skillCategoryPct}%` : "—"}
              </span>
              <span className="compare-pct-sub">
                of skill category budget
                {skillScore01 != null && ` · score ${skillScore01}% of ideal match`}
              </span>
            </div>
            <div className="compare-cell compare-cell--jd">
              {renderJobMetric(jobRow, "skills")}
            </div>

            {(result.skill_details || []).length > 0 && (
              <div className="compare-section-title">Each JD skill (vs full resume list above)</div>
            )}
            {(result.skill_details || []).map((sd, idx) => {
              const share = sd.weight_share || 0;
              const pctReq =
                share > 0
                  ? Math.round((sd.weighted_contribution / share) * 1000) / 10
                  : null;
              return (
                <React.Fragment key={`sd-${sd.job_skill_slug}-${idx}`}>
                  <div className="compare-cell">
                    {sd.resume_match_skill_slug ? (
                      <strong>{skillLineForSlug(resumeRow, sd.resume_match_skill_slug)}</strong>
                    ) : (
                      <span style={{ color: "#718096", fontSize: "clamp(0.75rem, 1.3vw, 0.85rem)" }}>
                        No resume skill in graph (no path / no overlap)
                      </span>
                    )}
                  </div>
                  <div className="compare-cell compare-cell--center">
                    <span className="compare-pct-main">
                      {pctReq != null ? `${pctReq}%` : "—"}
                    </span>
                    <span className="compare-pct-sub">of max for this JD skill</span>
                    <div className="compare-skill-meta">
                      {sd.graph_hops_to_nearest_resume_skill != null
                        ? `${sd.graph_hops_to_nearest_resume_skill} hop(s) in graph`
                        : "no graph path"}
                      {sd.prolog_strict_covers ? " · covers" : ""}
                    </div>
                    {sd.meta_interpreter_proof && (
                      <div className="compare-skill-meta" title="mi_solve/2 proof from skill_meta.pl">
                        <strong>mi_solve</strong>: {sd.meta_interpreter_proof.kind}
                        {Array.isArray(sd.meta_interpreter_proof.detail)
                          ? ` → ${sd.meta_interpreter_proof.detail.join(" → ")}`
                          : ` → ${sd.meta_interpreter_proof.detail}`}
                      </div>
                    )}
                  </div>
                  <div className="compare-cell compare-cell--jd">
                    <strong>{skillLineForSlug(jobRow, sd.job_skill_slug) ?? "—"}</strong>
                    <div className="compare-skill-meta">
                      weight {Math.round(share * 1000) / 10}% of skill bucket
                    </div>
                  </div>
                </React.Fragment>
              );
            })}

            {METRIC_ROWS.map(({ key, label }) => {
              const cat = pctOfCategory(result, key);
              const s01 = score01(result, key);
              const isMoney = key === "money";
              const skipMoney = isMoney && result.job_is_intern;
              return (
                <React.Fragment key={key}>
                  <div className="compare-section-title">{label}</div>
                  <div className="compare-cell">{renderResumeMetric(resumeRow, key)}</div>
                  <div className="compare-cell compare-cell--center">
                    {skipMoney ? (
                      <>
                        <span className="compare-pct-main">—</span>
                        <span className="compare-pct-sub">not scored (intern)</span>
                      </>
                    ) : (
                      <>
                        <span className="compare-pct-main">
                          {cat != null ? `${cat}%` : "—"}
                        </span>
                        <span className="compare-pct-sub">
                          of {label.toLowerCase()} budget
                          {s01 != null && ` · raw match ${s01}%`}
                        </span>
                      </>
                    )}
                  </div>
                  <div className="compare-cell compare-cell--jd">
                    {renderJobMetric(jobRow, key)}
                  </div>
                </React.Fragment>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
