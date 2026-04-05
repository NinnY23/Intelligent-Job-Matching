import React, { useState, useEffect } from 'react';
import {
  extractResumePreview,
  saveResumeExtraction,
  listResumes,
  listCompatibilityMetricExtractions,
} from './api';
import { formatSkill, formatTest, formatLanguage, testsFromExtraction } from './metricsDisplay';
import './ResumeExtractionDemo.css';

export default function ResumeExtractionDemo() {
  const [resumeFile, setResumeFile] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState('');
  const [extractionPreview, setExtractionPreview] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [savedRows, setSavedRows] = useState(null);
  const [compatRows, setCompatRows] = useState(null);

  const loadSaved = async () => {
    try {
      const [data, compat] = await Promise.all([
        listResumes(),
        listCompatibilityMetricExtractions(),
      ]);
      setSavedRows(data.resumes || []);
      setCompatRows(compat.extractions || []);
    } catch {
      setSavedRows([]);
      setCompatRows([]);
    }
  };

  useEffect(() => {
    loadSaved();
  }, []);

  const handleExtract = async (e) => {
    e.preventDefault();
    setExtractError('');
    setExtractionPreview(null);
    setSaveMessage('');

    if (!resumeFile) {
      setExtractError('Please select a PDF resume first.');
      return;
    }

    setExtracting(true);
    try {
      const result = await extractResumePreview(resumeFile);
      setExtractionPreview(result);
    } catch (err) {
      setExtractError(err.message || 'Failed to extract resume preview.');
    } finally {
      setExtracting(false);
    }
  };

  const handleSave = async () => {
    if (!extractionPreview?.extraction) return;
    setSaving(true);
    setSaveMessage('');
    try {
      await saveResumeExtraction({
        extraction: extractionPreview.extraction,
        model: extractionPreview.model,
      });
      setSaveMessage('Saved to SQLite.');
      await loadSaved();
    } catch (err) {
      setSaveMessage(err.message || 'Save failed.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="resume-demo-container">
      <h2 className="resume-demo-title">Resume Scan Demo (Preview)</h2>
      <p className="resume-demo-subtitle">
        Upload a PDF to extract compatibility metrics: skills (with level), job role, pay estimate,
        duration, GPA, education, standardized tests, languages, and intern vs full job — plus
        achievements. Pay is omitted when the role is an internship.
      </p>

      <form onSubmit={handleExtract} className="resume-demo-form">
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
        />
        <button type="submit" className="submit-btn" disabled={extracting}>
          {extracting ? 'Extracting...' : 'Run Scan'}
        </button>
      </form>

      {extractError && <div className="error-message">{extractError}</div>}

      {extractionPreview && (() => {
        const ext = extractionPreview.extraction || {};
        const isIntern = String(ext.employmentType || '').toLowerCase() === 'intern';
        const tests = testsFromExtraction(ext);
        return (
        <div className="resume-demo-preview">
          <div className="profile-item">
            <span className="label">Provider:</span>
            <span className="value">
              {extractionPreview.provider} ({extractionPreview.model})
            </span>
          </div>

          <div className="preview-section">
            <h3>1. Skills (compatibility level)</h3>
            <ul>
              {(ext.skills || []).map((item, index) => (
                <li key={`skill-${index}`}>{formatSkill(item)}</li>
              ))}
            </ul>
          </div>

          <div className="preview-section">
            <h3>2. Job role</h3>
            <p>{ext.jobRole || ext.jobTitle || '—'}</p>
          </div>

          {!isIntern && (
            <div className="preview-section">
              <h3>3. Estimated pay</h3>
              <p>{ext.moneyEstimate || '—'}</p>
            </div>
          )}

          <div className="preview-section">
            <h3>{isIntern ? '3' : '4'}. Duration</h3>
            <p>{ext.duration || '—'}</p>
          </div>

          <div className="preview-section">
            <h3>{isIntern ? '4' : '5'}. GPA</h3>
            <p>{ext.gpax != null && ext.gpax !== '' ? String(ext.gpax) : '—'}</p>
          </div>

          <div className="preview-section">
            <h3>{isIntern ? '5' : '6'}. Highest education</h3>
            <p>{ext.educationLevel || '—'}</p>
          </div>

          <div className="preview-section">
            <h3>{isIntern ? '6' : '7'}. Standardized tests</h3>
            <ul>
              {tests.map((item, index) => (
                <li key={`score-${index}`}>{formatTest(item)}</li>
              ))}
            </ul>
          </div>

          <div className="preview-section">
            <h3>{isIntern ? '7' : '8'}. Languages</h3>
            <ul>
              {(ext.languages || []).map((item, index) => (
                <li key={`lang-${index}`}>{formatLanguage(item)}</li>
              ))}
            </ul>
          </div>

          <div className="preview-section">
            <h3>{isIntern ? '8' : '9'}. Intern vs job</h3>
            <p>{ext.employmentType || '—'}</p>
          </div>

          <div className="preview-section">
            <h3>Achievements</h3>
            <ul>
              {(ext.achievements || []).map((item, index) => (
                <li key={`achievement-${index}`}>{typeof item === 'string' ? item : JSON.stringify(item)}</li>
              ))}
            </ul>
          </div>

          <div className="resume-demo-actions">
            <button type="button" className="submit-btn" disabled={saving} onClick={handleSave}>
              {saving ? 'Saving...' : 'Save to database'}
            </button>
            {saveMessage && <span className="save-hint">{saveMessage}</span>}
          </div>

          <details className="raw-json">
            <summary>Raw JSON</summary>
            <pre>{JSON.stringify(extractionPreview, null, 2)}</pre>
          </details>
        </div>
        );
      })()}

      {compatRows && compatRows.filter((r) => r.source_type === 'resume').length > 0 && (
        <div className="saved-list">
          <h3>
            Saved compatibility extractions — resume (
            {compatRows.filter((r) => r.source_type === 'resume').length})
          </h3>
          <ul>
            {compatRows
              .filter((r) => r.source_type === 'resume')
              .map((row) => (
                <li key={row.id}>
                  #{row.id} — {row.jobRole || '—'} — {row.employmentType || '—'} — {row.created_at}
                </li>
              ))}
          </ul>
        </div>
      )}

      {savedRows && savedRows.length > 0 && (
        <div className="saved-list">
          <h3>Legacy resume rows ({savedRows.length})</h3>
          <ul>
            {savedRows.map((row) => (
              <li key={row.id}>
                #{row.id} — {row.created_at}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

