# Putting Opportunity Finder online

The goal: one link, like `https://opportunity-finder.onrender.com`, that works
on your phone, on someone else's phone, on any PC — and always shows current
postings, whether or not your laptop is on.

The code is ready. What is left are the account steps, which only you can do
because they need your email and your signups. Budget about 30–45 minutes.

You will create three free accounts: **GitHub** (stores the code), **Neon**
(the database), and **Render** (runs the app).

---

## Before you start

The code is already committed to a local git repository in this folder. Nothing
here contains a password, and your CV file is deliberately excluded from the
repository.

---

## Step 1 — GitHub: put the code somewhere Render can read it

1. Sign up at **https://github.com/signup** if you do not already have an account.
2. Go to **https://github.com/new** and create a repository:
   - Name: `opportunity-finder`
   - Visibility: **Private**. Render can still deploy from a private repository,
     and there is no reason for this to be public.
   - Do **not** tick "Add a README" — the folder already has one.
3. GitHub then shows a page with commands. Ignore them and run these instead,
   from this folder in Git Bash or PowerShell, replacing `YOUR-USERNAME`:

```bash
git remote add origin https://github.com/YOUR-USERNAME/opportunity-finder.git
```

Then push it:

```bash
git branch -M main && git push -u origin main
```

If it asks for a password, use a **personal access token**, not your account
password — GitHub stopped accepting passwords here. Create one at
https://github.com/settings/tokens with the `repo` scope ticked.

---

## Step 2 — Neon: create the database

Render's free tier wipes its own disk on every restart, so the postings, and
your saved and applied marks, need to live in a real database.

1. Sign up at **https://neon.tech** (the free tier needs no card).
2. Create a project — any name, for example `opportunity-finder`. Pick the
   region closest to you.
3. On the project dashboard find **Connection string** and copy it. It looks
   like:

   `postgresql://neondb_owner:SOMETHING@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`

**Treat that string as a password.** Do not paste it into a chat, an email, or
the repository. It goes in exactly one place: Render, in step 4.

---

## Step 3 — Check the database works, before deploying

Worth two minutes: it catches a bad connection string now rather than after a
failed deploy. In PowerShell, in this folder, paste your string in place of the
placeholder:

```powershell
$env:DATABASE_URL = "postgresql://...paste yours here..."; python check_database.py
```

You want to see `12 passed, 0 failed`. The script creates the tables, writes a
test posting, reads it back through every query the live site uses, then deletes
it. It never prints your connection string, so its output is safe to share if
something fails.

---

## Step 4 — Render: run the app

1. Sign up at **https://render.com** and choose "Sign in with GitHub" so it can
   see your repository.
2. Click **New → Blueprint**.
3. Pick your `opportunity-finder` repository. Render reads `render.yaml` from
   the repo and fills in the settings itself.
4. It will ask for the value of **DATABASE_URL**, because the blueprint
   deliberately leaves it blank. Paste the Neon connection string here.
5. Click **Apply** / **Create**.

The first build takes about five minutes. When it finishes, Render shows your
URL at the top of the service page. That link is the answer to the original
question: open it on any device, any time.

---

## What happens on that first visit

The database starts empty, so the first time you open the link the app begins
collecting in the background. The page loads straight away but looks bare;
give it five to ten minutes and reload, and the postings will be there.

From then on, GitHub Actions wakes the hosted app and runs a full collection at
07:00 Hong Kong time every day. Every visit also checks how old the data is. If
it is more than ten hours old, a fresh collection starts in the background
while you read what is already there. The scheduled run does not depend on your
laptop being switched on.

---

## Two things to expect from the free tier

**The first visit of the day is slow.** Render suspends free services after
about fifteen minutes without traffic, so the next request has to wake it —
usually 30 to 60 seconds of blank screen or a spinner. After that it is quick
until it goes idle again. Nothing is broken; that is the free tier working as
designed.

**The scheduled collection takes several minutes.** The GitHub workflow waits
for it to finish, so Render remains awake for the whole run. You can also start
the same process with the app's Refresh button at any time.

---

## Afterwards

**Changing anything.** Edit the files here, then:

```bash
git add -A && git commit -m "describe the change" && git push
```

Render redeploys on its own within a minute or two. This is how you retune the
scoring in `finder/profile.py` or add search phrases in `finder/config.py`.

**Your laptop still works.** `Start Opportunity Finder.bat` runs the local copy
against the local SQLite file, unaffected by any of the above. The scheduled
07:00 task keeps doing that too. The local copy and the hosted copy hold
separate data — saving a job on one does not save it on the other.

**Cost.** Everything above is free tier. Render will offer to upgrade to remove
the sleeping delay; you do not need it.

**If the deploy fails.** The Render service page has a **Logs** tab, and the
error is almost always in the last twenty lines. Paste those back to me.
