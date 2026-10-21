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

### Phase 4 Application workspace generation

- Research the employer, department, courses, research groups and role-specific
  requirements, retaining the page title, URL, excerpt and retrieval date.
- Download linked job descriptions, person specifications, candidate guidance
  and application forms, and save researched web pages as readable PDFs.
- Detect all requested documents and stated word limits before drafting, including
  diversity, outreach, teaching, research, leadership and criteria statements.
- Tailor a copy of an uploaded DOCX in place so its design and untouched content
  are preserved; always make the original CV available in the workspace.
- Ground drafts in the uploaded CV and collected sources. Do not invent
  publications, employment, metrics, qualifications or achievements.
- Produce polished editable Microsoft Word files, an evidence plan, source PDFs,
  a sources document, a job snapshot and a manifest. Save each output as soon as
  it is complete so the user can download it while later stages continue.

### Phase 5 Commercial readiness

- Add verified email, password reset, account deletion and export.
- Add subscription billing, quotas, metering and an administrator console.
- Move long refresh and application-generation work to a durable task queue.
- Add object storage, malware scanning, retention controls, backups, audit logs,
  privacy terms, data-processing documentation and operational monitoring.
- Confirm licensing and terms of service for every job and search source before
  charging customers.

## Security and privacy rules

- Passwords are hashed; provider keys are encrypted; CVs are private.
- Every user-owned query includes the authenticated user ID.
- Uploads are bounded and parsed in memory; filenames never become server paths.
- Application workspaces are generated on demand and available only to their owner.
- Secrets stay in environment variables and are never committed to GitHub.
- AI prompts instruct providers not to fabricate evidence and source links are
  included in every workspace for review.

## Definition of the first commercial MVP

The first MVP is complete when two test users can register, upload different
CVs for both tracks, receive different scores for the same posting, keep
separate saved/applied lists, configure an AI and search provider, generate a
staged application workspace with individual Word and PDF downloads, and cannot
read each other's profiles, keys or workspaces. The live deployment must preserve
these records across redeployments.

## Status of commercial readiness

Done: accounts, private per-CV matching, bring-your-own AI and search keys, staged
application workspaces, terms and privacy pages (templates), account data export and
permanent deletion, login and sign-up rate limiting, security headers, private
"add a job from any website", and licensed-API sources that switch on with keys
(Adzuna, Jooble, USAJOBS, Reed API).

Still required before charging customers:

1. **Source licensing.** Boards that refuse automated readers (HigherEdJobs, Indeed,
   LinkedIn, Seek, Bayt and others) are deliberately not scraped. The commercial route
   is each board's licensed feed or partner API (HigherEdJobs and Indeed offer partner
   programmes; Adzuna, Jooble, Reed and USAJOBS publish APIs). The free feeds used today
   (RSS, public JSON, public search pages) should each have their terms checked for
   commercial use, and attribution kept (the app always links to the original advert).
2. **Legal review** of the Terms and Privacy templates for the operator's jurisdiction
   (GDPR/UK GDPR if there are EU/UK users). Set OPERATOR_NAME and CONTACT_EMAIL.
3. **Email verification and password reset** (needs a mail provider).
4. **Billing and quotas** (for example Stripe) and an admin console.
5. **A durable job queue** for refreshes and document generation, instead of threads.
6. **Hosting capacity.** The free tiers (Render, Neon) are for a pilot: Neon limits monthly
   data transfer, and shared job data plus per-user matching grows with every account.
