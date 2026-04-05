// src/CreateJobPost.jsx
import React, { useState } from "react";
import "./CreateJobPost.css";

export default function CreateJobPost({ onPostCreated, onBack }) {
  const [formData, setFormData] = useState({
    position: "",
    company: "",
    location: "",
    salaryMin: "",
    salaryMax: "",
    description: "",
    skills: "",
    type: "Full-time",
    openings: "1",
    deadline: "",
  });

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    // Validation
    if (
      !formData.position ||
      !formData.company ||
      !formData.location ||
      !formData.description
    ) {
      setError("Please fill in all required fields");
      return;
    }

    if (
      formData.salaryMin &&
      formData.salaryMax &&
      parseInt(formData.salaryMin) > parseInt(formData.salaryMax)
    ) {
      setError("Minimum salary cannot be greater than maximum salary");
      return;
    }

    setLoading(true);

    try {
      const token = localStorage.getItem("token");
      const response = await fetch("http://localhost:5000/api/job-posts", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const contentType = response.headers.get("content-type");
        let errorMessage = "Failed to create job post";

        if (contentType && contentType.includes("application/json")) {
          const data = await response.json();
          errorMessage = data.message || errorMessage;
        } else {
          errorMessage = `Server error: ${response.status}`;
        }

        throw new Error(errorMessage);
      }

      const data = await response.json();
      setSuccess("Job post created successfully!");

      // Reset form
      setFormData({
        position: "",
        company: "",
        location: "",
        salaryMin: "",
        salaryMax: "",
        description: "",
        skills: "",
        type: "Full-time",
        openings: "1",
        deadline: "",
      });

      // Callback to parent
      if (onPostCreated) {
        setTimeout(() => onPostCreated(data), 1500);
      }
    } catch (err) {
      setError(err.message || "Failed to create job post. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="create-job-container">
      <div className="create-job-header">
        <button className="back-btn" onClick={onBack}>
          ← Back
        </button>
        <h1>Post a New Job</h1>
      </div>

      <div className="create-job-content">
        <form onSubmit={handleSubmit} className="job-form">
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="position">Job Title *</label>
              <input
                id="position"
                type="text"
                name="position"
                value={formData.position}
                onChange={handleInputChange}
                placeholder="e.g., Senior Developer"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="company">Company Name *</label>
              <input
                id="company"
                type="text"
                name="company"
                value={formData.company}
                onChange={handleInputChange}
                placeholder="e.g., Tech Corp"
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="location">Location *</label>
              <input
                id="location"
                type="text"
                name="location"
                value={formData.location}
                onChange={handleInputChange}
                placeholder="e.g., San Francisco, CA"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="type">Job Type *</label>
              <select
                id="type"
                name="type"
                value={formData.type}
                onChange={handleInputChange}
              >
                <option value="Full-time">Full-time</option>
                <option value="Part-time">Part-time</option>
                <option value="Contract">Contract</option>
                <option value="Temporary">Temporary</option>
                <option value="Internship">Internship</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="salaryMin">Minimum Salary ($)</label>
              <input
                id="salaryMin"
                type="number"
                name="salaryMin"
                value={formData.salaryMin}
                onChange={handleInputChange}
                placeholder="e.g., 80000"
              />
            </div>

            <div className="form-group">
              <label htmlFor="salaryMax">Maximum Salary ($)</label>
              <input
                id="salaryMax"
                type="number"
                name="salaryMax"
                value={formData.salaryMax}
                onChange={handleInputChange}
                placeholder="e.g., 150000"
              />
            </div>

            <div className="form-group">
              <label htmlFor="openings">Number of Openings</label>
              <input
                id="openings"
                type="number"
                name="openings"
                value={formData.openings}
                onChange={handleInputChange}
                min="1"
              />
            </div>
          </div>

          <div className="form-group full-width">
            <label htmlFor="description">Job Description *</label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              placeholder="Describe the job responsibilities, requirements, and benefits..."
              rows="8"
              required
            />
          </div>

          <div className="form-group full-width">
            <label htmlFor="skills">Required Skills (comma-separated)</label>
            <input
              id="skills"
              type="text"
              name="skills"
              value={formData.skills}
              onChange={handleInputChange}
              placeholder="e.g., React, Node.js, JavaScript"
            />
          </div>

          <div className="form-group full-width">
            <label htmlFor="deadline">Application Deadline</label>
            <input
              id="deadline"
              type="date"
              name="deadline"
              value={formData.deadline}
              onChange={handleInputChange}
            />
          </div>

          {error && <div className="error-message">{error}</div>}
          {success && <div className="success-message">{success}</div>}

          <div className="form-actions">
            <button type="submit" disabled={loading} className="submit-btn">
              {loading ? "Posting..." : "Post Job"}
            </button>
            <button type="button" onClick={onBack} className="cancel-btn">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
