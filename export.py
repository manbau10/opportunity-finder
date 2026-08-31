# -*- coding: utf-8 -*-
"""
Build the phone snapshot.

The dashboard at 127.0.0.1 only exists while the server is running on this PC.
This writes a single self-contained HTML file holding the current shortlist, so
it can be published and read anywhere, including on a phone with no PC involved.

It is a snapshot, not a live view, and says so on its face. Regenerate it with:

    python app.py --export
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os

from finder import store
from finder.config import BASE_DIR
from finder.profile import CANDIDATE

OUT_PATH = os.path.join(BASE_DIR, "data", "phone-snapshot.html")

MIN_SCORE = 45
MAX_ITEMS = 160


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def collect() -> tuple[list[dict], dict]:
    conn = store.connect()
    try:
        store.recompute_days_left(conn)
        rows = conn.execute(
            """SELECT * FROM opportunities
               WHERE score >= ? AND status != 'dismissed'
                 AND (days_left IS NULL OR days_left >= 0)
               ORDER BY score DESC, (days_left IS NULL), days_left ASC
               LIMIT ?""", (MIN_SCORE, MAX_ITEMS)).fetchall()
        items = [store.decode(r) for r in rows]
        last = store.last_refresh(conn)
    finally:
        conn.close()

    slim = []
    for it in items:
        slim.append({
            "t": it["title"],
            "o": it["org"] or "",
            "l": it["location"] or "",
            "c": it["country"] or "",
            "u": it["url"],
            "s": it["score"],
            "r": it["role_key"],
            "rl": it["role_label"] or "",
            "d": it["deadline"] or "",
            "dl": it["days_left"],
            "src": it["source"],
            "m": (it["matched_terms"] or [])[:6],
            "f": (it["flags"] or [])[:2],
            "p": (it["positives"] or [])[:1],
            "new": (it["first_seen"] or "")[:10] == dt.date.today().isoformat(),
        })

    stats = {
        "total": len(slim),
        "strong": sum(1 for i in slim if i["s"] >= 70),
        "new": sum(1 for i in slim if i["new"]),
        "closing": sum(1 for i in slim if i["dl"] is not None and 0 <= i["dl"] <= 7),
        "collected": (last or {}).get("finished") or "",
    }
    return slim, stats


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
CSS = """
:root {
  --paper:      #f4f6f3;
  --card:       #ffffff;
  --sunk:       #eaeee9;
  --line:       #dde3dd;
  --line-firm:  #c6cfc6;
  --ink:        #121614;
  --ink-2:      #4e574f;
  --ink-3:      #7e877f;
  --accent:     #1b5e4f;
  --accent-ink: #ffffff;
  --accent-bg:  #e4ede9;
  --amber:      #a25e14;
  --amber-bg:   #f8eddc;
  --crimson:    #963232;
  --crimson-bg: #f8e7e4;
  --shadow:     0 1px 2px rgba(16,26,20,.06), 0 6px 16px rgba(16,26,20,.05);
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper:      #10130f;
    --card:       #191d19;
    --sunk:       #212721;
    --line:       #2c332d;
    --line-firm:  #3d453e;
    --ink:        #e9ece7;
    --ink-2:      #aab2ab;
    --ink-3:      #7d857e;
    --accent:     #6dc0a5;
    --accent-ink: #0d1f19;
    --accent-bg:  #1a2f28;
    --amber:      #dda662;
    --amber-bg:   #2f2416;
    --crimson:    #e0897f;
    --crimson-bg: #301d1c;
    --shadow:     0 1px 2px rgba(0,0,0,.4), 0 6px 18px rgba(0,0,0,.3);
  }
}

:root[data-theme="dark"] {
  --paper:      #10130f;
  --card:       #191d19;
  --sunk:       #212721;
  --line:       #2c332d;
  --line-firm:  #3d453e;
  --ink:        #e9ece7;
  --ink-2:      #aab2ab;
  --ink-3:      #7d857e;
  --accent:     #6dc0a5;
  --accent-ink: #0d1f19;
  --accent-bg:  #1a2f28;
  --amber:      #dda662;
  --amber-bg:   #2f2416;
  --crimson:    #e0897f;
  --crimson-bg: #301d1c;
  --shadow:     0 1px 2px rgba(0,0,0,.4), 0 6px 18px rgba(0,0,0,.3);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font: 15px/1.5 "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  -webkit-text-size-adjust: 100%;
}

.wrap { max-width: 760px; margin: 0 auto; padding: 0 14px 72px; }

/* ------------------------------------------------------------- masthead */
.masthead { padding: 26px 0 16px; border-bottom: 1px solid var(--line-firm); }
.eyebrow {
  font: 500 11px/1 "IBM Plex Mono", ui-monospace, monospace;
  letter-spacing: .14em; text-transform: uppercase; color: var(--ink-3);
}
h1 {
  margin: 9px 0 6px;
  font: 600 clamp(27px, 7vw, 38px)/1.08 Newsreader, Georgia, serif;
  letter-spacing: -.02em; text-wrap: balance;
}
.standfirst { margin: 0; color: var(--ink-2); font-size: 14px; max-width: 54ch; }

.snapshot {
  margin-top: 14px; padding: 9px 12px; border-radius: 8px;
  background: var(--sunk); border: 1px solid var(--line);
  font: 400 12.5px/1.45 "IBM Plex Sans", sans-serif; color: var(--ink-2);
}
.snapshot b { color: var(--ink); font-weight: 600; }

/* ---------------------------------------------------------------- tally */
.tally {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 8px; margin: 16px 0 4px;
}
.tally div {
  background: var(--card); border: 1px solid var(--line);
  border-radius: 10px; padding: 10px 8px; text-align: center;
}
.tally .n {
  font: 600 22px/1 Newsreader, Georgia, serif;
  font-variant-numeric: tabular-nums;
}
.tally .k {
  font: 500 10px/1.25 "IBM Plex Mono", monospace; margin-top: 5px;
  letter-spacing: .06em; text-transform: uppercase; color: var(--ink-3);
}
.tally .hot .n { color: var(--accent); }
.tally .warm .n { color: var(--amber); }

/* --------------------------------------------------------------- filter */
.controls {
  position: sticky; top: 0; z-index: 5;
  background: var(--paper); padding: 12px 0 10px;
  border-bottom: 1px solid var(--line);
}
.segs { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 2px; }
.segs::-webkit-scrollbar { display: none; }
.segs button {
  flex: 0 0 auto; padding: 7px 13px; border-radius: 999px;
  border: 1px solid var(--line-firm); background: var(--card); color: var(--ink-2);
  font: 500 13px "IBM Plex Sans", sans-serif; cursor: pointer; white-space: nowrap;
}
.segs button[aria-pressed="true"] {
  background: var(--accent); border-color: var(--accent);
  color: var(--accent-ink); font-weight: 600;
}
.segs button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.showing {
  margin: 9px 2px 0; font: 400 12px "IBM Plex Mono", monospace; color: var(--ink-3);
}

/* ----------------------------------------------------------------- list */
.list { display: flex; flex-direction: column; gap: 9px; margin-top: 14px; }

.card {
  display: block; text-decoration: none; color: inherit;
  position: relative; overflow: hidden;
  background: var(--card); border: 1px solid var(--line);
  border-radius: 12px; padding: 13px 14px 13px 20px;
  box-shadow: var(--shadow);
}
.card:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
/* The rail encodes match strength as form, so it reads before the number. */
.card::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
  background: var(--line-firm);
}
.card.tier1::before { background: var(--accent); }
.card.tier2::before { background: var(--accent); opacity: .5; }

.head { display: flex; gap: 12px; align-items: baseline; }
.score {
  flex: 0 0 auto; font: 600 20px/1 Newsreader, Georgia, serif;
  font-variant-numeric: tabular-nums; color: var(--ink-3);
}
.tier1 .score { color: var(--accent); }
.tier2 .score { color: var(--ink-2); }
h2 {
  margin: 0; font: 600 15.5px/1.32 "IBM Plex Sans", sans-serif;
  letter-spacing: -.005em; text-wrap: balance;
}
.where { margin: 5px 0 0 32px; font-size: 13px; color: var(--ink-2); }
.where .sep { color: var(--ink-3); }

.chips { display: flex; flex-wrap: wrap; gap: 5px; margin: 9px 0 0 32px; }
.chip {
  font: 500 11.5px "IBM Plex Sans", sans-serif; padding: 3px 8px;
  border-radius: 6px; background: var(--sunk); color: var(--ink-2);
  border: 1px solid var(--line);
}
.chip.role { background: var(--accent-bg); color: var(--accent); border-color: transparent; }
.chip.new  { background: var(--accent); color: var(--accent-ink); border-color: transparent; font-weight: 600; }
.chip.good { background: var(--accent-bg); color: var(--accent); border-color: transparent; }
.chip.warn { background: transparent; color: var(--ink-3); border-style: dashed; }
.chip.due  { background: var(--amber-bg); color: var(--amber); border-color: transparent; font-weight: 600; }
.chip.due.calm { background: var(--sunk); color: var(--ink-2); border-color: var(--line); font-weight: 500; }
.chip.due.urgent { background: var(--crimson-bg); color: var(--crimson); border-color: transparent; }
.chip .mono { font-family: "IBM Plex Mono", monospace; font-variant-numeric: tabular-nums; }

.terms {
  margin: 9px 0 0 32px; font-size: 12px; color: var(--ink-3); line-height: 1.45;
}
.terms b { color: var(--ink-2); font-weight: 500; }

.empty {
  text-align: center; padding: 48px 16px; color: var(--ink-3);
  border: 1px dashed var(--line-firm); border-radius: 12px; margin-top: 14px;
}

footer {
  margin-top: 30px; padding-top: 16px; border-top: 1px solid var(--line);
  font-size: 12.5px; color: var(--ink-3); line-height: 1.6;
}
footer code {
  font: 12px "IBM Plex Mono", monospace; background: var(--sunk);
  padding: 1px 5px; border-radius: 4px; color: var(--ink-2);
}

@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
"""

JS = """
var DATA = __DATA__;
var mode = 'all';

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
  });
}

function dueChip(it) {
  if (it.dl === null || it.dl === undefined) {
    return it.d
      ? '<span class="chip due calm">closes <span class="mono">' + esc(it.d) + '</span></span>'
      : '<span class="chip due calm">no deadline given</span>';
  }
  if (it.dl === 0) return '<span class="chip due urgent">closes today</span>';
  if (it.dl <= 7)  return '<span class="chip due urgent"><span class="mono">' + it.dl + '</span> day' + (it.dl === 1 ? '' : 's') + ' left</span>';
  if (it.dl <= 21) return '<span class="chip due"><span class="mono">' + it.dl + '</span> days left</span>';
  return '<span class="chip due calm"><span class="mono">' + it.dl + '</span> days left</span>';
}

function match(it) {
  if (mode === 'all') return true;
  if (mode === 'closing') return it.dl !== null && it.dl !== undefined && it.dl <= 21;
  if (mode === 'new') return it.new;
  if (mode === 'faculty') return it.r === 'assistant' || it.r === 'associate' || it.r === 'chair';
  return it.r === mode;
}

function render() {
  var rows = DATA.filter(match);
  if (mode === 'closing') {
    rows.sort(function (a, b) { return a.dl - b.dl; });
  }

  document.getElementById('showing').textContent =
    rows.length + (rows.length === 1 ? ' opportunity' : ' opportunities');

  if (!rows.length) {
    document.getElementById('list').innerHTML =
      '<div class="empty">Nothing in this group in the current snapshot.</div>';
    return;
  }

  document.getElementById('list').innerHTML = rows.map(function (it) {
    var tier = it.s >= 70 ? 'tier1' : (it.s >= 55 ? 'tier2' : '');
    var where = esc(it.o);
    if (it.l) where += '<span class="sep"> &middot; </span>' + esc(it.l);

    var chips = '';
    if (it.new) chips += '<span class="chip new">NEW</span>';
    if (it.rl)  chips += '<span class="chip role">' + esc(it.rl) + '</span>';
    chips += dueChip(it);
    chips += '<span class="chip">' + esc(it.src) + '</span>';
    (it.p || []).forEach(function (p) { chips += '<span class="chip good">' + esc(p) + '</span>'; });
    (it.f || []).forEach(function (f) { chips += '<span class="chip warn">' + esc(f) + '</span>'; });

    return '<a class="card ' + tier + '" href="' + esc(it.u) + '" target="_blank" rel="noopener">' +
      '<div class="head"><span class="score">' + it.s + '</span><h2>' + esc(it.t) + '</h2></div>' +
      '<div class="where">' + where + '</div>' +
      '<div class="chips">' + chips + '</div>' +
      ((it.m && it.m.length)
        ? '<div class="terms"><b>Matches your work on:</b> ' + esc(it.m.join(', ')) + '</div>'
        : '') +
      '</a>';
  }).join('');
}

Array.prototype.forEach.call(document.querySelectorAll('.segs button'), function (btn) {
  btn.addEventListener('click', function () {
    Array.prototype.forEach.call(document.querySelectorAll('.segs button'), function (b) {
      b.setAttribute('aria-pressed', String(b === btn));
    });
    mode = btn.dataset.mode;
    render();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
});

render();
"""


def _fmt_when(iso: str) -> str:
    if not iso:
        return "unknown"
    try:
        d = dt.datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return d.strftime("%d %B %Y at %H:%M")


def build_html(items: list[dict], stats: dict) -> str:
    counts = {
        "all": len(items),
        "faculty": sum(1 for i in items if i["r"] in ("assistant", "associate", "chair")),
        "postdoc": sum(1 for i in items if i["r"] == "postdoc"),
        "fellowship": sum(1 for i in items if i["r"] == "fellowship"),
        "closing": sum(1 for i in items if i["dl"] is not None and i["dl"] <= 21),
        "new": stats["new"],
    }
    segs = [("all", "Everything"), ("new", "New today"), ("closing", "Closing soon"),
            ("faculty", "Faculty"), ("postdoc", "Postdocs"), ("fellowship", "Fellowships")]
    seg_html = "".join(
        '<button data-mode="%s" aria-pressed="%s">%s <span class="mono">%d</span></button>'
        % (key, "true" if key == "all" else "false", html.escape(label), counts.get(key, 0))
        for key, label in segs)

    return """<title>Taiwo Academic Watch</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&amp;family=IBM+Plex+Sans:wght@400;500;600&amp;family=Newsreader:opsz,wght@6..72,600&amp;display=swap" rel="stylesheet">
<style>%(css)s</style>

<div class="wrap">
  <header class="masthead">
    <div class="eyebrow">Academic opportunities &middot; matched to your CV</div>
    <h1>Faculty, fellowship and postdoc watch</h1>
    <p class="standfirst">Infrastructure engineering and management, construction
      engineering and management, project management, and water infrastructure &mdash;
      across the USA, UK, Canada, Australia, New&nbsp;Zealand and Europe.</p>
    <div class="snapshot">
      <b>Snapshot, not a live feed.</b> Collected %(when)s. The links and deadlines
      below were correct then; open the advert to confirm before you apply.
      Re-run the collector on your PC and republish this page to update it.
    </div>
  </header>

  <div class="tally">
    <div class="hot"><div class="n">%(new)d</div><div class="k">new today</div></div>
    <div class="hot"><div class="n">%(strong)d</div><div class="k">strong 70+</div></div>
    <div><div class="n">%(total)d</div><div class="k">open</div></div>
    <div class="warm"><div class="n">%(closing)d</div><div class="k">close &lt;7d</div></div>
  </div>

  <div class="controls">
    <div class="segs">%(segs)s</div>
    <div class="showing" id="showing"></div>
  </div>

  <main class="list" id="list"></main>

  <footer>
    Scored against %(name)s &mdash; %(phd)s; %(papers)d journal articles,
    h-index %(h)d. Weighting: 55%% subject fit, 25%% post type, 12%% location,
    8%% timing. Tap any card to open the original advert.<br><br>
    Generated by Opportunity Finder on your PC. To refresh:
    <code>python app.py --refresh</code> then <code>python app.py --export</code>.
  </footer>
</div>

<script>%(js)s</script>
""" % {
        "css": CSS,
        "js": JS.replace("__DATA__", json.dumps(items, ensure_ascii=False)),
        "segs": seg_html,
        "when": html.escape(_fmt_when(stats["collected"])),
        "new": stats["new"],
        "strong": stats["strong"],
        "total": stats["total"],
        "closing": stats["closing"],
        "name": html.escape(CANDIDATE["name"]),
        "phd": html.escape(CANDIDATE["phd"]),
        "papers": CANDIDATE["metrics"]["journal_articles"],
        "h": CANDIDATE["metrics"]["h_index"],
    }


def write_snapshot(path: str = OUT_PATH) -> str:
    items, stats = collect()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_html(items, stats))
    return path


if __name__ == "__main__":
    print("Wrote", write_snapshot())
