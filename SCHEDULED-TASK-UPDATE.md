# Scheduled task update — paste-ready

The refresh task is stored by the desktop app, so a cloud session can't read or edit it. Open it
in the Claude desktop app (Settings → scheduled tasks → the Tue/Sat 9 PM refresh) and apply the
edits below.

I have **not** seen your current task prompt, only what the README documents about it. So this is
written as **additions and one replacement**, not a wholesale rewrite — pasting a full replacement
I authored blind would risk dropping details the README never captured.

---

## Edit 1 — replace the validation step

Find the step that currently says something like *"Validates both files parse and the counts
agree, then commits and pushes."* Replace it with:

> Run `python3 tools/validate_snapshot.py --data data.json --archive archive.json --prev <the
> previous run's data.json>`. If it exits non-zero, **stop — do not commit and do not push**.
> Report every problem it printed in the run summary. Parsing is not the same as agreeing: this
> script checks the changelog's own numbers against the snapshot it describes, which is the
> defect that shipped on 2026-08-01.

`--prev` is optional. If you don't keep the previous snapshot, drop the flag — the listing
arithmetic check is skipped and everything else still runs.

---

## Edit 2 — add three steps before the diff

Insert these after the Freddie Mac rate lookup and before the diff/price-cut step.

### 2a. Resolve realtor.com ids and coordinates — every listing, every run

> For each listing, look up its realtor.com property record. This must run **inside a browser tab
> already on a realtor.com page** — the endpoint returns 429 to plain HTTP clients and is
> CORS-blocked from any other origin.
>
> `POST https://www.realtor.com/frontdoor/parser/v1/suggest-filters`
> headers: `content-type: application/json`, `rdc-client-name: RDC_WEB_SRP_HOME_SEARCH`,
> `rdc-client-version: 3.x` — both `rdc-*` headers are required or it 400s.
> body: `{"search_input":{"search_term":"<addr>, <city>, WA <zip>"},"limit":3,"area_types":["address"]}`
>
> From `data.location_candidates[0].geo` write `mpr` = `mpr_id`, `lat`, `lon`. Accept only when
> `area_type` is `"address"` and `postal_code` matches the listing's ZIP.
>
> Retry non-200 up to 3 times with 1.5s / 3s / 4.5s backoff — transient 502s happen and clear on
> the first retry. Sleep ~320ms between addresses. If an address still won't resolve, **carry
> forward the previous run's values**; never blank a field that had a good value. Expect ~2-3
> minutes for a full sweep and near-100% resolution.

### 2b. Fetch price history — new listings only

> For listings that are **new this run only** (typically 5-11, never the whole table), open
> `https://www.realtor.com/realestateandhomes-detail/M<mpr>`, expand the **Property history**
> accordion, and parse the text between "Price history" and "Tax history". Walk back to the start
> of the current campaign — the earliest `Listed` event not separated from today by a `Sold` — and
> write `list0` (that asking price) and `list0Date`.
>
> **The critical guard.** This endpoint throttles and fails *silently*: after roughly 90 requests
> it starts returning "No price history data is available for this property" for pages that
> rendered fine minutes earlier. That string is **not data** — treat it as a retryable error.
> Never write an empty history over a good one. If a new listing's history can't be read, leave
> `list0` absent entirely and log it; the page guards every use, so the row just shows no badge.
> Report the count of unread histories in the run summary. Do not bulk-sweep the whole table.

### 2c. Resolve elementary catchments — offline, no network

> Run `python3 tools/enrich_catchments.py`. It reads `data.json` and the cached
> `bsd-elementary-2024-25.geojson`, and writes `elem` / `elemSrc` / `elemFlag` per listing by
> point-in-polygon. Standard library only — nothing to install.
>
> If it exits non-zero, **stop and report**. It fails deliberately when a hand-verified catchment
> tag disagrees with the district boundary, when a listing lost a catchment it previously had, or
> when coordinates are missing — each of those means something upstream changed and a human
> should look, not that the run should continue.
>
> Refresh `bsd-elementary-2024-25.geojson` once a school year (attendance areas change at most
> annually) from:
> `https://services1.arcgis.com/DjfAyvUwdiY6gnFC/arcgis/rest/services/BSD_School_Locator/FeatureServer/1/query?where=1%3D1&outFields=BSD_Name,OSPI_Name,School_Grades_Serviced&outSR=4326&f=geojson`

---

## Edit 3 — the push step

This is the part you asked for. Replace the commit/push step with:

> Do all git work in a **fresh clone under `/tmp`**, never in the mounted project folder — its
> git is wedged and FUSE writes fail.
>
> 1. `git clone` the repo to a temp directory.
> 2. Copy in the files this run produced: `data.json`, `archive.json`.
> 3. **Also copy these presentation files if they differ from the clone** — they are hand-authored
>    between runs and would otherwise never reach GitHub:
>    `index.html`, `README.md`, `bsd-elementary-2024-25.geojson`, `tools/enrich_catchments.py`,
>    `tools/validate_snapshot.py`, `REFRESH-TASK-REALTOR-STEP.md`, `SCHEDULED-TASK-UPDATE.md`.
>
>    Copy that list by name, **not** a `*.md` glob. The project folder also accumulates scratch
>    files — handoff notes, working data like `cdom.json`, the superseded
>    `bellevue-redmond-dashboard.html` — and a glob would quietly start committing them.
> 4. Run `git status` and confirm only expected paths appear. `.gh-credentials` is gitignored and
>    must never show up; if it does, stop.
> 5. Run the validator (Edit 1). Only if it passes:
> 6. `git add -A`, commit, push.
>
> **The guardrail, stated precisely.** The task must never *author or edit* `index.html` — the
> school comparison table, ratings and test scores live there and have been corrupted before by
> automated "fixes". But it *should* commit changes that are already present in the working
> folder, because those are human edits and otherwise they never ship. Write, no. Carry, yes.

On the next run this will pick up the pending changes automatically: the realtor.com links, the
resolved catchments, the collapsed changelog, the new filters, the two scripts and the cached
boundary file.

---

## New files this depends on

All are in the project folder now and need to reach the repo on the next push:

| File | Purpose |
|---|---|
| `tools/enrich_catchments.py` | Point-in-polygon catchment resolution. Stdlib only. `--check` reports without writing. |
| `tools/validate_snapshot.py` | Pre-push invariants. Exit 1 = do not push. |
| `bsd-elementary-2024-25.geojson` | Cached district attendance areas, 14 polygons. |
| `REFRESH-TASK-REALTOR-STEP.md` | Longer-form reference for the realtor.com steps. |

Both scripts were tested against the live 2026-08-08 snapshot: the resolver reproduces a
shapely-based implementation exactly on all 74 listings (43 resolved, 31 unresolved, 3 district
mismatches, zero differences), and the validator passes clean data while catching injected
out-of-box coordinates, a nonsensical `list0`, a duplicate listing, a collapse in realtor-id
coverage, and a changelog/snapshot count mismatch — the 2026-08-01 defect — each with exit 1.
