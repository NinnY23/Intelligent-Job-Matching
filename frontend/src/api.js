// src/api.js
const API_BASE = "http://localhost:5000";

/** Local dev account created automatically when the DB has no users (see backend db.ensure_default_dev_user). */
export const DEV_BOOTSTRAP_EMAIL = "dev@localhost";
export const DEV_BOOTSTRAP_PASSWORD = "dev";

export async function loginUser(email, password) {
  const res = await fetch(`${API_BASE}/api/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Login failed");
  }

  return res.json();
}

/**
 * Development only: log in as the seeded dev user so a stale token after DB reset can recover without manual steps.
 */
export async function tryDevBootstrapLogin() {
  if (process.env.NODE_ENV !== "development") {
    return null;
  }
  try {
    const data = await loginUser(DEV_BOOTSTRAP_EMAIL, DEV_BOOTSTRAP_PASSWORD);
    if (data.token && data.user) {
      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));
      return data;
    }
  } catch {
    /* dev user may be missing if using a fresh custom DB */
  }
  return null;
}

export async function fetchJobs() {
  const token = localStorage.getItem("token");
  const res = await fetch("/api/jobs", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return res.json();
}

export async function logoutUser() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}

export async function getProfile() {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/profile`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to fetch profile");
  }

  return res.json();
}

export async function updateProfile(profileData) {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/profile`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(profileData),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to update profile");
  }

  return res.json();
}

export async function extractResumePreview(file) {
  const token = localStorage.getItem("token");
  const formData = new FormData();
  formData.append("resume", file);

  const res = await fetch(`${API_BASE}/api/resume/extract-preview`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!res.ok) {
    const contentType = res.headers.get("content-type");
    let message = "Failed to extract resume preview";

    if (contentType && contentType.includes("application/json")) {
      const data = await res.json();
      message = data.message || message;
    } else {
      message = `Server error: ${res.status}`;
    }

    throw new Error(message);
  }

  return res.json();
}

export async function extractJobDescriptionPreview(file) {
  const token = localStorage.getItem("token");
  const formData = new FormData();
  formData.append("job_description", file);

  const res = await fetch(`${API_BASE}/api/job-description/extract-preview`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!res.ok) {
    const contentType = res.headers.get("content-type");
    let message = "Failed to extract job description";
    if (contentType && contentType.includes("application/json")) {
      const data = await res.json();
      message = data.message || message;
    } else {
      message = `Server error: ${res.status}`;
    }
    throw new Error(message);
  }

  return res.json();
}

export async function saveResumeExtraction(payload) {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/resumes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to save resume");
  }
  return res.json();
}

export async function listResumes() {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/resumes`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to list resumes");
  }
  return res.json();
}

export async function listCompatibilityMetricExtractions() {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/compatibility-metric-extractions`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to list compatibility extractions");
  }
  return res.json();
}

export async function getEmployerCompatibilityWeights() {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/employer/compatibility-weights`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to load compatibility weights");
  }
  return res.json();
}

export async function postCompatibilityMatch(
  resumeExtractionId,
  jobExtractionId,
  compareWeights = null
) {
  const token = localStorage.getItem("token");
  const body = {
    resume_extraction_id: resumeExtractionId,
    job_extraction_id: jobExtractionId,
  };
  if (compareWeights && compareWeights.metrics?.length) {
    body.compare_weights = compareWeights;
  }
  const res = await fetch(`${API_BASE}/api/match/compatibility`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Compatibility match failed");
  }
  return res.json();
}

export async function saveJobDescriptionExtraction(payload) {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/job-descriptions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to save job description");
  }
  return res.json();
}

export async function listJobDescriptions() {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/job-descriptions`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to list job descriptions");
  }
  return res.json();
}

export async function getSkillsGraph() {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/skills/graph`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to load skills");
  }
  return res.json();
}

export async function createSkill(payload) {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/skills`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to create skill");
  }
  return res.json();
}

export async function updateSkill(slug, payload) {
  const token = localStorage.getItem("token");
  const res = await fetch(
    `${API_BASE}/api/skills/${encodeURIComponent(slug)}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    }
  );
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to update skill");
  }
  return res.json();
}

/** relation: "parent" (target is parent of skill) or "child" (target is child of skill). */
export async function addSkillHierarchyLink(skillSlug, { relation, target_slug }) {
  const token = localStorage.getItem("token");
  const res = await fetch(
    `${API_BASE}/api/skills/${encodeURIComponent(skillSlug)}/hierarchy`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ relation, target_slug }),
    }
  );
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to add hierarchy link");
  }
  return res.json();
}

export async function removeSkillHierarchyLink(skillSlug, relation, targetSlug) {
  const token = localStorage.getItem("token");
  const url = new URL(
    `${API_BASE}/api/skills/${encodeURIComponent(skillSlug)}/hierarchy`
  );
  url.searchParams.set("relation", relation);
  url.searchParams.set("target_slug", targetSlug);
  const res = await fetch(url.toString(), {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to remove hierarchy link");
  }
  return res.json();
}

export async function deleteSkill(slug) {
  const token = localStorage.getItem("token");
  const res = await fetch(
    `${API_BASE}/api/skills/${encodeURIComponent(slug)}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to delete skill");
  }
  return res.json();
}

export async function createSkillAlias(payload) {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/skills/aliases`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to create alias");
  }
  return res.json();
}

export async function deleteSkillAlias(aliasId) {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/skills/aliases/${aliasId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to delete alias");
  }
  return res.json();
}

export async function seedSkills() {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/api/skills/seed`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || "Failed to seed skills");
  }
  return res.json();
}
