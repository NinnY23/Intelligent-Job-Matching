import React, { useState, useEffect } from "react";
import {
  extractJobDescriptionPreview,
  saveJobDescriptionExtraction,
  listJobDescriptions,
  listCompatibilityMetricExtractions,
} from "./api";
import { formatSkill, formatTest, formatLanguage, testsFromExtraction } from "./metricsDisplay";
import "./JobDescriptionExtractionDemo.css";

export default function JobDescriptionExtractionDemo() {
  const [file, setFile] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [savedRows, setSavedRows] = useState(null);
  const [compatRows, setCompatRows] = useState(null);

  const loadSaved = async () => {
    try {
      const [data, compat] = await Promise.all([
        listJobDescriptions(),
        listCompatibilityMetricExtractions(),
      ]);
      setSavedRows(data.job_descriptions || []);
      setCompatRows(compat.extractions || []);
    } catch (e) {
      setSavedRows([]);
      setCompatRows([]);
    }
  };

  const handleExtract = async (e) => {
    e.preventDefault();
    setError("");
    setPreview(null);
    setSaveMessage("");
    if (!file) {
      setError("Please select a PDF job description.");
      return;
    }
    setExtracting(true);
    try {
      const result = await extractJobDescriptionPreview(file);
      setPreview(result);
    } catch (err) {
      setError(err.message || "Extraction failed.");
    } finally {
      setExtracting(false);
    }
  };

  const handleSave = async () => {
    if (!preview?.extraction) return;
    setSaving(true);
    setSaveMessage("");
    try {
      await saveJobDescriptionExtraction({
        extraction: preview.extraction,
        model: preview.model,
      });
      setSaveMessage("Saved to SQLite.");
      await loadSaved();
    } catch (err) {
      setSaveMessage(err.message || "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    loadSaved();
  }, []);

  const ext = preview?.extraction;
  const isIntern = ext ? String(ext.employmentType || "").toLowerCase() === "intern" : false;
  const tests = ext ? testsFromExtraction(ext) : [];

  return (
    <div className="job-desc-demo-container">
      <h2 className="job-desc-demo-title">Job description PDF (manager)</h2>
      <p className="job-desc-demo-subtitle">
        Upload a PDF to extract the same nine compatibility metrics as resumes (skills with level, role,
        pay, duration, GPA, education, tests, languages, intern vs job). Pay is hidden for internships.
        Extra JD fields (location, certifications, etc.) appear below when the model returns them.
      </p>

      <form onSubmit={handleExtract} className="job-desc-demo-form">
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <button type="submit" className="submit-btn" disabled={extracting}>
          {extracting ? "Extracting..." : "Extract from PDF"}
        </button>
      </form>

      {error && <div className="error-message">{error}</div>}

      {ext && (
        <div className="job-desc-preview">
          <div className="profile-item">
            <span className="label">Model:</span>
            <span className="value">
              {preview.provider} / {preview.model}
            </span>
          </div>

          <section>
            <h3>1. Skills (compatibility level)</h3>
            <ul>
              {(ext.skills || []).map((s, i) => (
                <li key={`s-${i}`}>{formatSkill(s)}</li>
              ))}
            </ul>
          </section>

          <section>
            <h3>2. Job role</h3>
            <p>{ext.jobRole || ext.jobTitle || "—"}</p>
          </section>

          {!isIntern && (
            <section>
              <h3>3. Estimated pay</h3>
              <p>{ext.moneyEstimate || "—"}</p>
            </section>
          )}

          <section>
            <h3>{isIntern ? "3" : "4"}. Duration</h3>
            <p>{ext.duration || "—"}</p>
          </section>

          <section>
            <h3>{isIntern ? "4" : "5"}. GPA</h3>
            <p>{ext.gpax != null && ext.gpax !== "" ? String(ext.gpax) : "—"}</p>
          </section>

          <section>
            <h3>{isIntern ? "5" : "6"}. Highest education (summary)</h3>
            <p>{ext.educationLevel || "—"}</p>
          </section>

          <section>
            <h3>{isIntern ? "6" : "7"}. Standardized tests</h3>
            <ul>
              {tests.map((item, i) => (
                <li key={`t-${i}`}>{formatTest(item)}</li>
              ))}
            </ul>
          </section>

          <section>
            <h3>{isIntern ? "7" : "8"}. Languages</h3>
            <ul>
              {(ext.languages || []).map((item, i) => (
                <li key={`l-${i}`}>{formatLanguage(item)}</li>
              ))}
            </ul>
          </section>

          <section>
            <h3>{isIntern ? "8" : "9"}. Intern vs job</h3>
            <p>{ext.employmentType || "—"}</p>
          </section>

          <div className="preview-grid">
            <div>
              <strong>Location</strong>
              <p>{ext.location || "—"}</p>
            </div>
            <div>
              <strong>Experience (min / max years)</strong>
              <p>
                {ext.yearsExperienceMin || "—"} / {ext.yearsExperienceMax || "—"}
              </p>
            </div>
          </div>
          <section>
            <h3>Education requirements (JD text)</h3>
            <ul>
              {(ext.educationRequirements || []).map((s, i) => (
                <li key={`e-${i}`}>{s}</li>
              ))}
            </ul>
          </section>
          <section>
            <h3>Certifications</h3>
            <ul>
              {(ext.certifications || []).map((s, i) => (
                <li key={`c-${i}`}>{s}</li>
              ))}
            </ul>
          </section>
          <section>
            <h3>Other considerations</h3>
            <ul>
              {(ext.otherConsiderations || []).map((s, i) => (
                <li key={`o-${i}`}>{s}</li>
              ))}
            </ul>
          </section>
          <div className="job-desc-actions">
            <button type="button" className="submit-btn" disabled={saving} onClick={handleSave}>
              {saving ? "Saving..." : "Save to database"}
            </button>
            {saveMessage && <span className="save-hint">{saveMessage}</span>}
          </div>
          <details className="raw-json">
            <summary>Raw JSON</summary>
            <pre>{JSON.stringify(preview, null, 2)}</pre>
          </details>
        </div>
      )}

      {compatRows && compatRows.filter((r) => r.source_type === "job_description").length > 0 && (
        <div className="saved-list">
          <h3>
            Saved compatibility extractions — job description (
            {compatRows.filter((r) => r.source_type === "job_description").length})
          </h3>
          <ul>
            {compatRows
              .filter((r) => r.source_type === "job_description")
              .map((row) => (
                <li key={row.id}>
                  #{row.id} — {row.jobRole || "—"} — {row.employmentType || "—"} — {row.created_at}
                </li>
              ))}
          </ul>
        </div>
      )}

      {savedRows && savedRows.length > 0 && (
        <div className="saved-list">
          <h3>Legacy job description rows ({savedRows.length})</h3>
          <ul>
            {savedRows.map((row) => (
              <li key={row.id}>
                #{row.id} — {row.jobTitle || "Untitled"} — {row.created_at}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
