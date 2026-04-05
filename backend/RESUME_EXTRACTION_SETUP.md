# Extraction & SQLite Setup

## Environment Variables

Set these before running the backend:

- `GEMINI_API_KEY`: Required API key for Gemini.
- `GEMINI_MODEL`: Optional model name. Defaults to `gemini-2.5-flash-image` in code (override if your account lists different models).
- `SQLITE_DB_PATH`: Optional path to the SQLite file. Defaults to `backend/app.db`.

## Install Dependencies

From `backend`:

- `pip install -r requirements.txt`

## Resume PDF — extract preview

- `POST /api/resume/extract-preview`
- Auth: `Authorization: Bearer <token>`
- Content type: `multipart/form-data`
- File field name: `resume`
- PDF only, max upload 10 MB (Flask limit)

### Save extracted resume (SQLite)

- `POST /api/resumes` — JSON body:

```json
{
  "extraction": {
    "skills": ["Python"],
    "achievements": [],
    "standardTestScores": []
  },
  "model": "gemini-2.5-flash-image"
}
```

- `GET /api/resumes` — list rows for the authenticated user.

Table `resumes`: `id`, `user_email`, `skills_json`, `achievements_json`, `standard_test_scores_json`, `created_at`, `gemini_model`.

## Job description PDF (manager) — extract preview

- `POST /api/job-description/extract-preview`
- Auth: `Authorization: Bearer <token>` (user must exist in the in-memory `users_db` from signup/login)
- File field name: `job_description`
- PDF only

Response `extraction` schema:

- `jobTitle`, `location`, `yearsExperienceMin`, `yearsExperienceMax` (strings)
- `skills`, `educationRequirements`, `certifications`, `otherConsiderations` (arrays of strings)

### Save extracted job description (SQLite)

- `POST /api/job-descriptions` — JSON body:

```json
{
  "extraction": {
    "jobTitle": "Senior Engineer",
    "location": "Remote",
    "yearsExperienceMin": "5",
    "yearsExperienceMax": "",
    "skills": ["Python", "SQL"],
    "educationRequirements": ["BS Computer Science"],
    "certifications": [],
    "otherConsiderations": ["Occasional travel"]
  },
  "model": "gemini-2.5-flash-image"
}
```

- `GET /api/job-descriptions` — list rows for the authenticated employer email.

Table `job_descriptions`: `id`, `employer_email`, `job_title`, `location`, `years_experience_min`, `years_experience_max`, `skills_json`, `education_requirements_json`, `certifications_json`, `other_considerations_json`, `created_at`, `gemini_model`.

## Example curl (resume extract)

```bash
curl -X POST "http://localhost:5000/api/resume/extract-preview" \
  -H "Authorization: Bearer token_user_123" \
  -F "resume=@/path/to/resume.pdf;type=application/pdf"
```

## Notes

- Arrays are stored as JSON text columns in SQLite.
- Raw PDF bytes are not stored; only extracted structured fields are persisted when you call the save endpoints or use the UI “Save to database” buttons.

## Prolog skill meta (PySwip)

Skill hierarchy (`skills`, `skill_aliases`) and normalized matching are documented in [PROLOG_SETUP.md](PROLOG_SETUP.md). Endpoints: `POST /api/skills/seed`, `GET /api/skills/graph`, `POST /api/match/prolog-preview`.
