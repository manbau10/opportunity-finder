# Opportunity Finder Commercial Product Plan

## Product outcome

Opportunity Finder will become a multi-user application in which each person
has an account, separate academic and industry CV profiles, private match
scores and application tracking, and downloadable Word application packs.

## Delivery phases

### Phase 1 Product foundation

- Add secure registration, sign-in, sign-out, password hashing and session
  protection.
- Store all user-owned records by user ID and prevent cross-account access.
- Accept PDF, DOCX and text CVs with file-size and type validation.
- Maintain independent academic and industry profiles for every user.
- Extract a structured, editable profile from each CV and calculate private
  match scores without changing the shared job records.
- Split the dashboard into Academic jobs and Industry jobs.

### Phase 2 Opportunity coverage

- Preserve the existing academic collectors and add industry-source adapters.
- Mark every opportunity with a career track and keep refreshes idempotent.
- Recalculate a user's matches after a CV upload and after new opportunities
  arrive.
- Keep saved, applied and hidden status private to the user and career track.

### Phase 3 Bring your own AI and search

- Store API credentials encrypted at rest and never return them to the browser.
- Support OpenAI, Anthropic, Google Gemini, OpenRouter, Groq, Mistral and any
  OpenAI-compatible endpoint, including local Ollama and LM Studio endpoints.
- Support Tavily, Brave Search and Serper research APIs, plus a key-free search
  fallback.
- Test a provider configuration before saving it and show actionable errors.

### Phase 4 Application pack generation

- Research the employer, department, courses, research groups and role-specific
  requirements, retaining the page title, URL, excerpt and retrieval date.
- Generate a tailored cover letter and the documents appropriate to the track:
  academic statement package for academic roles and selection-criteria or
  supporting-statement package for industry roles.
- Ground drafts in the uploaded CV and collected sources. Do not invent
  publications, employment, metrics, qualifications or achievements.
- Produce editable Microsoft Word files, a sources document, a job snapshot
  and a manifest, then package them in a ZIP download.

### Phase 5 Commercial readiness

- Add verified email, password reset, account deletion and export.
- Add subscription billing, quotas, metering and an administrator console.
- Move long refresh and pack-generation work to a durable task queue.
- Add object storage, malware scanning, retention controls, backups, audit logs,
  privacy terms, data-processing documentation and operational monitoring.
- Confirm licensing and terms of service for every job and search source before
  charging customers.

## Security and privacy rules

- Passwords are hashed; provider keys are encrypted; CVs are private.
- Every user-owned query includes the authenticated user ID.
- Uploads are bounded and parsed in memory; filenames never become server paths.
- Application packs are generated on demand and downloaded only by their owner.
- Secrets stay in environment variables and are never committed to GitHub.
- AI prompts instruct providers not to fabricate evidence and source links are
  included in every pack for review.

## Definition of the first commercial MVP

The first MVP is complete when two test users can register, upload different
CVs for both tracks, receive different scores for the same posting, keep
separate saved/applied lists, configure an AI and search provider, generate a
Word-based application ZIP, and cannot read each other's profiles, keys or
packs. The live deployment must preserve these records across redeployments.
