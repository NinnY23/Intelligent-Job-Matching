// src/Profile.jsx
import React, { useState } from 'react';
import './Profile.css';
import { extractResumePreview } from './api';

export default function Profile({ user, onUpdateProfile, onBack }) {
  const [formData, setFormData] = useState({
    name: user?.name || '',
    email: user?.email || '',
    phone: user?.phone || '',
    location: user?.location || '',
    bio: user?.bio || '',
    skills: user?.skills || '',
    profilePicture: user?.profilePicture || '',
  });

  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [resumeFile, setResumeFile] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState('');
  const [extractionPreview, setExtractionPreview] = useState(null);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch('http://localhost:5000/api/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || 'Failed to update profile');
      }

      const updatedUser = await response.json();
      localStorage.setItem('user', JSON.stringify(updatedUser.user));
      onUpdateProfile(updatedUser.user);
      setSuccess('Profile updated successfully!');
      setIsEditing(false);
    } catch (err) {
      setError(err.message || 'Failed to update profile. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleResumeExtract = async (e) => {
    e.preventDefault();
    setExtractError('');
    setExtractionPreview(null);

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

  return (
    <div className="profile-container">
      <div className="profile-header">
        <button className="back-btn" onClick={onBack}>← Back</button>
        <h1>My Profile</h1>
        {!isEditing && (
          <button className="edit-btn" onClick={() => setIsEditing(true)}>
            Edit Profile
          </button>
        )}
      </div>

      <div className="profile-content">
        {isEditing ? (
          <form onSubmit={handleSubmit} className="profile-form">
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="name">Full Name:</label>
                <input
                  id="name"
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  placeholder="Enter your full name"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="email">Email:</label>
                <input
                  id="email"
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  placeholder="Enter your email"
                  disabled
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="phone">Phone:</label>
                <input
                  id="phone"
                  type="tel"
                  name="phone"
                  value={formData.phone}
                  onChange={handleInputChange}
                  placeholder="Enter your phone number"
                />
              </div>

              <div className="form-group">
                <label htmlFor="location">Location:</label>
                <input
                  id="location"
                  type="text"
                  name="location"
                  value={formData.location}
                  onChange={handleInputChange}
                  placeholder="Enter your location"
                />
              </div>
            </div>

            <div className="form-group full-width">
              <label htmlFor="bio">Bio:</label>
              <textarea
                id="bio"
                name="bio"
                value={formData.bio}
                onChange={handleInputChange}
                placeholder="Tell us about yourself"
                rows="4"
              />
            </div>

            <div className="form-group full-width">
              <label htmlFor="skills">Skills (comma-separated):</label>
              <input
                id="skills"
                type="text"
                name="skills"
                value={formData.skills}
                onChange={handleInputChange}
                placeholder="e.g., JavaScript, React, Python"
              />
            </div>

            {error && <div className="error-message">{error}</div>}
            {success && <div className="success-message">{success}</div>}

            <div className="form-actions">
              <button type="submit" disabled={loading} className="save-btn">
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
              <button
                type="button"
                onClick={() => setIsEditing(false)}
                className="cancel-btn"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div className="profile-view">
            <div className="profile-item">
              <span className="label">Name:</span>
              <span className="value">{formData.name || 'Not set'}</span>
            </div>

            <div className="profile-item">
              <span className="label">Email:</span>
              <span className="value">{formData.email}</span>
            </div>

            <div className="profile-item">
              <span className="label">Phone:</span>
              <span className="value">{formData.phone || 'Not set'}</span>
            </div>

            <div className="profile-item">
              <span className="label">Location:</span>
              <span className="value">{formData.location || 'Not set'}</span>
            </div>

            <div className="profile-item">
              <span className="label">Bio:</span>
              <span className="value">{formData.bio || 'Not set'}</span>
            </div>

            <div className="profile-item">
              <span className="label">Skills:</span>
              <span className="value">{formData.skills || 'Not set'}</span>
            </div>
          </div>
        )}
      </div>

      <div className="profile-content resume-extraction">
        <h2>Resume Vision Extraction (Preview)</h2>
        <p className="resume-hint">
          Upload a PDF to preview extracted skills, achievements, and standard test scores.
        </p>

        <form onSubmit={handleResumeExtract} className="resume-form">
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
          />
          <button type="submit" className="save-btn" disabled={extracting}>
            {extracting ? 'Extracting...' : 'Extract Preview'}
          </button>
        </form>

        {extractError && <div className="error-message">{extractError}</div>}

        {extractionPreview && (
          <div className="extraction-preview">
            <div className="profile-item">
              <span className="label">Provider:</span>
              <span className="value">
                {extractionPreview.provider} ({extractionPreview.model})
              </span>
            </div>

            <div className="preview-section">
              <h3>Skills</h3>
              <ul>
                {(extractionPreview.extraction?.skills || []).map((item, index) => (
                  <li key={`skill-${index}`}>{item}</li>
                ))}
              </ul>
            </div>

            <div className="preview-section">
              <h3>Achievements</h3>
              <ul>
                {(extractionPreview.extraction?.achievements || []).map((item, index) => (
                  <li key={`achievement-${index}`}>{item}</li>
                ))}
              </ul>
            </div>

            <div className="preview-section">
              <h3>Standard Test Scores</h3>
              <ul>
                {(extractionPreview.extraction?.standardTestScores || []).map((item, index) => (
                  <li key={`score-${index}`}>
                    {item.testName || 'Unknown Test'} | Score: {item.score || 'N/A'} | Grade: {item.grade || 'N/A'} | Source: {item.sourceText || 'N/A'}
                  </li>
                ))}
              </ul>
            </div>

            <details>
              <summary>Raw JSON</summary>
              <pre>{JSON.stringify(extractionPreview, null, 2)}</pre>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}
