# Opportunity Finder

Opportunity Finder is now a multi-user, CV-personalized product. Every account
has separate Academic and Industry profiles, private scores and application
tracking, encrypted bring-your-own AI/search settings, and downloadable Word
application packs with a research-source audit trail.

A daily dashboard of academic posts — faculty, fellowships and postdocs — gathered
from four job boards plus a curated fellowship register, and scored against
Ridwan A. Taiwo's CV.

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
5. Open a job and choose **Create Word application pack**. The ZIP contains
   editable drafts, the job snapshot, the research sources and a manifest.

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
| **Dashed tags** | Warnings: adjunct contract, wrong discipline, deadline passed, outside your target countries. |

Click any card for the full breakdown: the four sub-scores, all overlapping
topics, the deadline, and the advert text.

**Save** keeps a post in your shortlist, **Applied** records that you sent
something, **Hide** removes it from the main list. Use the *Your list* filter to
come back to them.

---

## Where the postings come from

| Source | Coverage | Method |
|---|---|---|
| **Times Higher Education unijobs** | UK, Australia, New Zealand, and global | Keyword RSS, one query per search phrase |
| **Chronicle of Higher Education** | United States and Canada | Keyword RSS |
| **jobs.ac.uk** | United Kingdom, plus European and international posts | Search-results pages |
| **EURAXESS** | European Commission portal | Its 10 newest postings, filtered locally |
| **Fellowship register** | All target regions | A curated list kept in the code |

For the best-scoring postings the app then opens the advert itself to read the
closing date, country, and full description, and re-scores with that extra
detail. Adverts it has already read are never re-opened, so the first refresh is
the slow one.

### Two honest limitations

**EURAXESS gives us only its 10 newest postings per day.** Its search box and
its pager both run in JavaScript — over plain HTTP, `?page=2` returns the same
first page — so there is no way to walk its full listing without a headless
browser. Running the refresh *daily* is what makes this source useful: ten new
European postings a day accumulate, but a gap of a week is a week of European
posts missed. The other three boards do carry European posts, so the gap is
narrower than it sounds.

**Named fellowships are not on job boards at all.** MSCA, DECRA, Banting,
Leverhulme, UKRI Future Leaders and the rest are announced on funder websites,
each with its own format. Rather than scrape two dozen funder sites unreliably,
`finder/sources/fellowships.py` holds a curated register of the major recurring
schemes you are eligible for, with the official link for each.

Those entries deliberately show **no deadline**. Rounds move every year, and a
confidently wrong date would be worse than none — each entry instead states the
month the call usually runs and links to the page that has the real date. Treat
them as a standing checklist, not as live vacancies. They score on eligibility
rather than on keyword overlap, since most are open to all disciplines.

Coverage is good but not exhaustive: no job board indexes every university, and
many departments advertise only on their own pages. Treat this as a high-yield
first pass, not the whole market.

---

## How the match score is built

    score = 55% subject fit + 25% post-type fit + 12% location fit + 8% timing

**Subject fit** compares the advert against a four-tier keyword model taken
straight from your publication record:

- **Tier A** — your own niche: water pipe failure, water distribution networks,
  leak detection, infrastructure asset management, construction management,
  modular integrated construction, predictive maintenance.
- **Tier B** — adjacent fields you publish and teach in: civil engineering,
  project management, BIM, digital twins, pavements, geotechnics, circular
  economy, wastewater and sewer networks, resilience, construction safety.
- **Tier C** — your methods: machine learning, explainable AI, LLMs, generative
  AI, computer vision, optimisation. These count for less on their own, because
  an AI post in another discipline is not your field.
- **Tier D** — weak context words.

Each tier saturates, so an advert that repeats one keyword cannot outscore a
genuinely on-topic one.

**Post-type fit** reflects your stage — PhD Feb 2025, first postdoc, 50 journal
articles, h-index 21:

| Post | Fit |
|---|---|
| Assistant Professor / Lecturer / tenure-track | 1.00 |
| Fellowship | 0.95 |
| Postdoc / Research Fellow | 0.88 |
| Associate Professor / Senior Lecturer | 0.80 |
| Chair / Full Professor / Head of School | 0.38 |
| PhD position | 0.05 |

That figure is then adjusted for contract quality: adjunct, part-time,
sessional and community-college teaching cover are discounted; permanent and
tenure-track posts get a small lift.

**Location fit** is 1.00 for the countries you named (USA, UK, Canada,
Australia, New Zealand, and Europe), 0.55 for elsewhere — Gulf, East Asia,
Singapore, Hong Kong still appear, ranked lower. Postings whose country cannot
be identified sit in between rather than being dropped.

**Timing** rewards recent postings and penalises deadlines that have passed or
are within three days.

Two suppressors run last: a title from a clearly different discipline (nursing,
literature, molecular biology…) cuts the score to roughly a fifth, and an
advert with almost no subject overlap is halved.

---

## Tuning it

Everything the scorer knows lives in **`finder/profile.py`** — edit it and the
next refresh re-scores everything:

- `TIER_A` … `TIER_D` — topic terms and their weights
- `ROLE_PATTERNS` — post types and how well each fits you
- `ROLE_DOWNGRADES` / `ROLE_UPGRADES` — contract-quality adjustments
- `TARGET_COUNTRIES` / `SECONDARY_COUNTRIES` — geography
- `WEIGHTS` — the four top-level percentages
- `CURATED_TOPIC_FLOOR` — how high the curated fellowships sit in the list

To add a fellowship scheme, append an entry to `SCHEMES` in
`finder/sources/fellowships.py`.

Search phrases sent to the job boards are in **`finder/config.py`**
(`SEARCH_QUERIES`). Add a phrase there to widen the net; add a term to
`CRAWL_KEEP_TERMS` to keep more of the EURAXESS crawl.

To re-score everything you have already collected without re-fetching:

```bash
python rescore.py
```

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
export.py                    builds the standalone phone snapshot
check_database.py            proves a database works before deploying
finder/db.py                 SQLite locally, Postgres when DATABASE_URL is set
render.yaml, Procfile        hosting configuration
rescore.py                   re-score stored postings after editing the profile
finder/profile.py            the CV model - topics, roles, countries, weights
finder/config.py             search phrases, crawl limits, source switches
finder/scoring.py            the matching engine
finder/pipeline.py           fetch -> score -> enrich -> store
finder/enrich.py             reads adverts for deadlines and locations
finder/store.py              SQLite persistence
finder/sources/              one adapter per job board
finder/sources/fellowships.py  the curated fellowship register
templates/, static/          the dashboard
data/opportunities.db        your collected postings, saves and applications
```

Your saves, applications and hidden items live in `data/opportunities.db`.
Back that file up and your history travels with you.

---

## If something breaks

- **Browser shows nothing** — check the console window for a Python error.
- **A source returns zero** — the refresh log names it (`!! <source> failed`).
  Job boards change their markup; the other three keep working, and the
  adapter for the broken one is a single file under `finder/sources/`.
- **Missing packages** — `pip install -r requirements.txt`.
- **Port already in use** — `python app.py --port 57001`.
