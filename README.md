# Opportunity Finder

Opportunity Finder is now a multi-user, CV-personalized product. Every account
has separate Academic and Industry profiles, private scores and application
tracking, encrypted bring-your-own AI/search settings, and downloadable Word
application workspaces with staged progress and a research-source audit trail.

A daily dashboard of academic posts (faculty, fellowships, postdocs) from nine academic
sources and of industry jobs from boards in a dozen countries plus worldwide remote
boards, each scored privately against your own CV.

---

## Two ways to use it

**Online, from any device** — see [DEPLOY.md](DEPLOY.md). One link that works on
your phone, someone else's phone, or any PC. GitHub Actions refreshes it daily
at 07:00 Hong Kong time, whether or not your laptop is on.

**On this PC** — the rest of this file. Same app, running locally against a
SQLite file, with a 07:00 scheduled refresh.

## First use online

1. Create an account and sign in.
2. Open **CVs** and upload an academic CV, an industry CV, or both. PDF, DOCX,
   TXT and Markdown files up to 6 MB are accepted.
3. Use the **Academic jobs** and **Industry jobs** tabs. Match scores, saved
   jobs, applied jobs and hidden jobs belong only to the signed-in user.
4. Open **API settings** and add an AI provider. Search can use key-free
   DuckDuckGo or Tavily, Brave Search or Serper with the user's own key.
5. Open a job and choose **Create application workspace**. A dedicated page shows
   research, requirements analysis, CV tailoring, drafting and final checks as
   they happen. Every completed Word document, PDF and source file can be downloaded
   individually while the remaining work continues. Workspaces remain available
   under **My applications**.

For format-preserving CV tailoring, upload a DOCX CV. The application workspace edits
a copy in place, keeps all untouched sections and includes the original file.
PDF CVs are retained unchanged, but their visual design cannot be edited reliably
as a Word document; the workspace therefore includes a clearly labelled working copy.

Application material is analysed before drafting. Explicit word limits are passed
to the writer and documents such as diversity, outreach, teaching, research,
leadership and selection-criteria statements are generated only when requested or
appropriate to the advert. Every generated document still requires applicant review.

Supported AI interfaces include OpenAI, Anthropic, Google Gemini, OpenRouter,
Groq, Mistral, HTTPS OpenAI-compatible APIs and local Ollama/LM Studio when the
application itself is running on the same computer. Provider credentials are
encrypted before they are stored and are never returned to the browser.

See [COMMERCIALIZATION_PLAN.md](COMMERCIALIZATION_PLAN.md) for the implemented
MVP boundary and the remaining billing, email-verification, queue, storage,
licensing and compliance work required before accepting paying customers.

---

## Daily use on this PC

Double-click **`Start Opportunity Finder.bat`**.

The server starts, your browser opens at `http://127.0.0.1:57000/`, and if the
data is more than 10 hours old it refreshes in the background while you read.
Leave the black console window open while you use the app; closing it stops the
server.

Everything new since yesterday carries a green **NEW** badge and a green left
edge, so the daily read is: open the app, scan the NEW items at the top of the
list, save the ones worth a proper look.

---

## What each part of a card means

| Element | Meaning |
|---|---|
| **The ring, 0–100** | How well the post matches your CV. 70+ is a strong match, 55–69 worth a look, below 45 is usually noise. |
| **Post type tag** | Assistant Professor / Lecturer, Postdoc, Fellowship, Associate, Chair, PhD. |
| **Deadline tag** | Days left where the advert states a closing date. Amber under 14 days. |
| **"Matches your work on"** | The specific CV topics the advert shares with you — the reason it scored. |
| **Dashed tags** | Warnings: adjunct contract, PhD studentship, senior chair-level post, deadline passed. |

Click any card for the full breakdown: the four sub-scores, all overlapping
topics, the deadline, and the advert text.

**Save** keeps a post in your shortlist, **Applied** records that you sent
something, **Hide** removes it from the main list. Use the *Your list* filter to
come back to them.

---

## Where the postings come from

Every board is searched **at the same time**, using phrases taken from the CVs
uploaded to the app (a nursing CV searches nursing, a civil-engineering CV
searches civil engineering). A full refresh takes about two minutes. Open
**Job sources** in the app to see each board, its coverage and how many postings
it has returned.

**Academic boards**

| Source | Coverage |
|---|---|
| Times Higher Education unijobs | UK, Australia, New Zealand and worldwide |
| jobs.ac.uk | United Kingdom, plus Europe and international |
| Chronicle of Higher Education | United States and Canada |
| Inside Higher Ed Careers | United States |
| Science Careers (AAAS) | Sciences, worldwide |
| AcademicJobsOnline | United States and Canada |
| AcademicTransfer | Netherlands |
| EURAXESS | Europe (the newest ~600 postings, filtered to your subjects) |
| Fellowship register | Named schemes: MSCA, UKRI, Banting, DECRA, Leverhulme ... |

**Industry boards, by country**

| Country or region | Source |
|---|---|
| United Kingdom | Reed; NHS Jobs (nursing and midwifery, used when a nursing CV exists) |
| United States | GovernmentJobs (city, county, state and federal agencies) |
| Canada | Job Bank (Government of Canada) |
| Sweden | Platsbanken (Arbetsformedlingen) |
| Switzerland | jobs.ch |
| Germany / DACH | Arbeitnow |
| Nigeria, Ghana | Jobberman |
| Kenya | BrighterMonday |
| South Africa | Careers24 |
| Remote, worldwide | Himalayas, Remotive, Jobicy (by country), Working Nomads, Remote OK |
| 19 countries | Adzuna, switched on by setting `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` (free keys at developer.adzuna.com) |

Add a Tavily, Brave or Serper key under **API settings** and industry searches also
look through employers' own application pages (Lever, Greenhouse, Ashby, Workable,
SmartRecruiters, Workday) country by country.

For adverts whose listing page shows no closing date, the app opens the advert itself to
read the deadline, location and full text, then re-scores. Adverts already read are never
re-opened, so each day's refresh is faster than the first.

### Checking that the sources still work

Job boards change their pages from time to time. This prints one line per board, OK,
EMPTY or FAIL, with the number of postings:

```bash
python check_sources.py
```

A board that fails is one small file under `finder/sources/` or in
`finder/industry_sources.py`; the others keep working.

### Honest limitations

- **Boards that block automated access are not used.** HigherEdJobs, Academic Positions,
  Indeed, Seek, Bayt, Jooble and similar sites sit behind bot protection, and the app does
  not try to defeat it. Where a country has no open board, add an Adzuna key or a search
  key.
- **Named fellowships are not on job boards.** `finder/sources/fellowships.py` holds a
  curated register with the official link for each scheme. Entries deliberately show no
  deadline: rounds move every year, and a confidently wrong date is worse than none.
- **Coverage is good, not complete.** Many departments advertise only on their own pages.
  Treat the results as a high-yield first pass over the market.

---

## How the match score is built

Each person's score is private and is computed from their own CV:

    score = 38% career-field fit + 34% subject fit + 13% post-type fit
            + 8% location fit + 7% timing

- **Career-field fit** classifies the advert's occupation from its title first and its text
  second. An advert whose title names a different occupation (a software engineer for a civil
  engineer, a sales role for a nurse) is capped at a low score, however many soft-skill words
  it shares with the CV.
- **Subject fit** compares the advert with the subjects found in the CV: multi-word phrases
  such as "water infrastructure", plus overlapping vocabulary.
- **Post-type fit** (academic CVs): assistant professor, lecturer and tenure-track posts fit
  best; fellowships and postdocs next; chairs and PhD studentships lower. Adjunct, vocational,
  part-time and temporary teaching cover are discounted. A PhD studentship is not discounted
  for someone who does not hold a doctorate.
- **Location fit** uses the countries listed under CVs > *Preferred countries*. Leave it
  blank to search worldwide.
- **Timing** rewards recent postings and penalises deadlines that have passed or are within
  three days. A closed post is capped at 25.

The same vacancy listed by several boards is shown once.

---

## Tuning it

- Subjects and job titles are read from each CV. Edit the target job titles and preferred
  countries on the **CVs** page and the matches are recalculated at once.
- `finder/vocab.py` is the list of subjects recognised in CVs. `finder/domains.py` holds the
  occupation patterns used by the career-field gate.
- `finder/config.py` holds limits (pages read, adverts opened) and switches to turn a source
  off.
- To add a fellowship scheme, append an entry to `SCHEMES` in `finder/sources/fellowships.py`.
- To add a job board, copy a small adapter (for example `finder/sources/ajo.py`, or a
  `fetch_*` function in `finder/industry_sources.py`) and register it.

---

## Running the refresh automatically each morning

`daily-refresh.bat` collects without opening the app. To have Windows run it at
07:00 every day, open PowerShell in this folder and run:

```powershell
Register-ScheduledTask -TaskName "Opportunity Finder daily refresh" -Action (New-ScheduledTaskAction -Execute "$PWD\daily-refresh.bat") -Trigger (New-ScheduledTaskTrigger -Daily -At 7am)
```

Then the app already has the day's postings whenever you open it. Output is
appended to `data\refresh.log`.

To remove it later:

```powershell
Unregister-ScheduledTask -TaskName "Opportunity Finder daily refresh" -Confirm:$false
```

---

## Files

```
app.py                       Flask server and JSON API
check_sources.py             live health check of every job board
check_database.py            proves a database works before deploying
finder/db.py                 SQLite locally, Postgres when DATABASE_URL is set
render.yaml, Procfile        hosting configuration
finder/queries.py            search phrases derived from the uploaded CVs
finder/pipeline.py           fetch (in parallel) -> score -> enrich -> store
finder/sources/              one adapter per academic job board
finder/industry_sources.py   industry boards by country
finder/matching.py           private per-CV matching engine
finder/profiles.py           CV reading: text, subjects, job titles
finder/research.py           advert, official site and source research for applications
finder/application_pack.py   staged application workspaces and Word/PDF output
finder/docgen.py             document builders, format-preserving CV tailoring
templates/, static/          the web pages
data/opportunities.db        your account, CVs, collected postings, saves, applications
data/secret.key              created on first run; signs logins and encrypts API keys
```

Back up the `data` folder and your history travels with you.

---

## If something breaks

- **Double-click does nothing, or says Python was not found** — install Python 3 from
  python.org and tick "Add python.exe to PATH". The start file installs the packages it needs
  on first run.
- **Browser shows nothing** — look at the black console window for the error message.
- **A board returns zero** — run `python check_sources.py`; the refresh log
  (`data/refresh.log`) also names it (`!! <source> failed`).
- **The scheduled refresh did nothing** — open `data/refresh.log`. An old version of this app
  crashed silently when a package was missing; `daily-refresh.bat` now installs it.
- **A workspace stopped at "working"** — if the server restarted mid-way, the workspace is
  marked as interrupted when the app next starts; press *Start a new attempt*.
- **Port already in use** — `python app.py --port 57001`.

## Tests

```bash
python -m pytest -q
```

runs about forty offline checks (parsers for every board, matching, account isolation,
application workspaces, CV format preservation). They use a throw-away database.
