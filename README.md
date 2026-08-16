# Bellevue &amp; Redmond — 4-Bed Buy-vs-Rent Tracker

A single-page dashboard that supports a **buy-vs-rent decision** for a 4-bedroom single-family home in **Bellevue / Redmond, WA**, with a focus on **strong elementary-school catchments**. It is updated automatically twice a week.

**Live site:** https://melon-claw.github.io/bellevue-redmond-housing/

---

## What this project is about

The search is anchored on a real decision. A toured home met essentially every requirement **except its assigned elementary school** (Ardmore, GreatSchools 4/10). Rather than compromise on schooling, this tracker widens the search to homes **zoned to strong elementary schools**, and quantifies the financial tradeoff between **buying** one of those homes and **renting** a comparable house.

It answers three questions at a glance:

1. **Which homes** (4BD, up to $2M) are currently for sale in the school zones we care about?
2. **How good is each school**, side by side?
3. **Does buying beat renting** at today's prices and rates — and after how many years?

## What's on the page

- **Market snapshot** — typical home value (Zillow ZHVI) + YoY for each core ZIP, current 30-yr mortgage rate, average local 4BD rent. Every tile prints its own **source and as-of date**, because the two ZIP series are not on the same vintage as each other and a reader comparing them needs to see that. ZHVI is a smoothed, mix-adjusted estimate of the whole housing stock — **not** a median sale price and not an MLS figure; the page said otherwise until issue #8.
- **Eastside context** — a collapsed table of all eight nearby ZIPs (98004/05/06/07/08/33/34/52) on that same single series, each with its own vintage. One ZIP's year-over-year move is uninterpretable alone; the band is what shows whether it is a real divergence or noise.
- **"What changed"** — a paginated, append-only changelog of new listings, price drops, and homes that went off-market. Every entry back to the first run is kept; each one also carries **that run's read**, expandable inline. **Collapsed by default** (issue #7): a first-time visitor was meeting five full changelog entries before reaching a single listing, so it now shows one summary row — latest refresh date and how many updates are on file — and opens on click. Any in-page link to it, and a direct `#changed` URL, expand it automatically.
- **"The read"** — a short written interpretation of the current data (inventory, momentum, time on market, financing, entry price, implication), rewritten from scratch every refresh and grounded in that run's numbers. Past reads are never overwritten — they are archived alongside the changelog entry that produced them, so you can page back and see what the data looked like *and* what it was taken to mean.
- **School comparison** — the four target elementaries side by side (rating, math/reading scores, boundary, commute).
- **Filters** — budget range (min/max + presets), catchment toggles, **city toggles**, **bed-count toggles**, **bath-count toggles**, a **square-footage range**, a recent-price-cut chip and a reset. All of them apply together (AND) and drive the map and table as one. The four categorical rows (school, city, beds, baths) build their buttons from the values present in the data, so a new city or an unusual bath count appears on its own at the next refresh without a code change.
- **Feedback** — the page links to this repo and to [the issue tracker](https://github.com/melon-claw/bellevue-redmond-housing/issues) from the header and from a call-to-action above the footnote, so a visitor who spots a stale price or a wrong catchment has somewhere to put it.
- **Email digest** — a subscribe box above the footnote. One issue on Saturday, and only when something actually changed; see [The email digest](#the-email-digest). It is a plain HTML form posting to Buttondown — no script, no CDN, nothing that can fail to load.
- **Map** — every listing placed from stored coordinates and coloured by its **verified elementary catchment**; a **▼ triangle outlined in red** marks a recent price cut *while keeping its catchment colour*, and a **red ring** marks a toured reference home. Homes whose catchment could not be verified are drawn **hollow**.
- **Buy-vs-rent calculator** — interactive sliders for price, down payment, rate, rent, appreciation, and horizon; shows monthly cost, equity build-up, net cost to buy vs rent, and the breakeven year.
- **Listings table** — sortable/searchable, with one-click realtor.com / Zillow / Google Maps links (plus Redfin where a direct link is on file), recent-cut and cumulative-decline badges, and a **Days** column carrying true cumulative days on market (see below).

### Days on market (added 2026-08-08)

The **Days** column is the MLS **Cumulative Days On Market (CDOM)**, read from each listing's Redfin MLS detail block — *not* the "days on Redfin" / "days on Zillow" counters shown on the listing cards.

The difference matters. CDOM **carries across relists**, so a home taken off the market and re-listed to reset its public counter still shows its full history. Reference home A read **108 days** cumulative while its on-market date was only 30 days old.

- Sortable — click **Days** to surface the longest-sitting listings, which are where a price cut is most likely to be entertained.
- Colour-coded: green under 45 days, amber 45–89, red 90+.
- Stored per listing as `cdom` plus `cdomDate` (the date the value was read) and **aged forward at render time**, so a carried-forward value stays correct between refreshes without being rewritten. Anything not re-verified within 45 days renders with a trailing `?`.
- Refetched only for **new and repriced** listings each run, with a full re-verification sweep on the first run of each calendar month.

**Availability limit:** CDOM is only published while a home is **Active or Pending**. Once a sale closes, Redfin reverts the MLS block to the prior sold record and the field disappears; a fully withdrawn listing has no MLS block at all. The one-time backfill therefore reached **97 of the 123 addresses ever tracked** — the 26 gaps are all closed or withdrawn homes and are expected to stay empty.

### Why the pending count is not a demand gauge

With CDOM available, the conventional "N homes went pending, so buyers are absorbing inventory" reading turns out to be misleading, and an earlier read on this page made exactly that mistake:

- **Stock vs flow.** Pending is a *stock* draining on a 30–45 day escrow clock, not a weekly flow. Counting new contracts against departures compares quantities moving on different timescales.
- **Right-censoring.** Median time-to-contract computed from homes that *found* buyers (44 days) is biased low, because listings still sitting — median 51 days and climbing, out to 313 — have not yet contributed their (larger) numbers.
- **The cleanest cut** is the 90-day cohort: of 21 tracked homes past three months on market, **17 are still active and 4 reached contract**.
- **What it does *not* show:** carried-over pendings sitting 14–27 days are an ordinary escrow, not evidence of deals collapsing.

## Data sources

| Data | Source |
|------|--------|
| For-sale listings | **Redfin** (NWMLS / MLS Grid) — ZIP sweeps (98052, 98008) and per-school attendance pages |
| Days on market | **Redfin** MLS detail block — `Cumulative Days On Market` (carries across relists) |
| Property links &amp; coordinates | **realtor.com** location parser — one lookup per address returns a stable property id, lat/lon, and for-sale status |
| Elementary catchment (Bellevue) | **Bellevue School District** published 2024-25 elementary attendance areas (ArcGIS feature service behind the district's school locator), resolved by point-in-polygon |
| Full price history | **realtor.com** property history — preserves withdraw-and-relist events that Redfin and Zillow drop |
| Listing cross-reference | **Zillow** (per-address links) |
| 4BD rent comps | **Zillow Rentals** — active 4BD single-family listings in 98008 / 98052 / 98006 |
| ZIP-level home values | **Zillow ZHVI** (all homes, smoothed &amp; seasonally adjusted) — per-ZIP pages, level and 1-yr change read off the *same* series at the *same* vintage. Vintages differ between ZIPs and each is stamped on its own tile. Not an MLS median. |
| School ratings &amp; test scores | **GreatSchools** profiles (Washington OSPI assessment data) |
| Mortgage rate | **Freddie Mac** PMMS (30-yr fixed) |
| Map geocoding | Coordinates ship with the snapshot (from the realtor.com lookup). **OpenStreetMap** Nominatim remains a client-side fallback for any listing without them. |

## Methodology

### Listing selection
- **Scope:** 4-bedroom-or-more single-family houses, priced up to **$2M**, in two core ZIPs (**Redmond 98052**, **Bellevue 98008**) plus four target school catchments (**98006 / 98005** for the Bellevue schools).
- **School-zoned sets** (Audubon, Somerset, Woodridge, Newport Heights) are *searched* via **Redfin's school-attendance pages**, which list homes actually *served by* that school. Since the BSD boundary file landed, the Bellevue members of those sets are *resolved* by point-in-polygon and the attendance page serves as the cross-check; only the Audubon home, being in Lake Washington district, still takes Redfin as its source. Woodridge currently matches no listings.
- **ZIP sweeps** (98052, 98008) are broader and are labeled as area buckets where the exact elementary varies; confirm the specific zone before relying on it.
- **De-duplication:** if a home appears in both a ZIP sweep and a school-zoned set, the more specific school tag wins.

### School data (verified from the primary source)
The four target elementaries are read **directly from each school's GreatSchools "Test Scores" section** — math and reading (ELA) proficiency from the **2024-25 Washington OSPI assessments**, plus the overall GreatSchools rating:

| Elementary (district) | Rating | Math | Reading |
|---|---|---|---|
| John J. Audubon — Redmond (LWSD) | 9/10 | 81% | 82% |
| Somerset — Bellevue (BSD) | 9/10 | 92% | 92% |
| Woodridge — Bellevue (BSD) | 9/10 | 81% | 82% |
| Newport Heights — Bellevue (BSD) | 9/10 | 76% | 74% |

For contrast, the original toured home is zoned to **Ardmore (4/10)**. These school figures are **static and human-verified**, and are deliberately **never touched by the automated refresh** (see Automation). They are sourced from the primary GreatSchools profile, not from search snippets or third-party aggregators.

### Buy-vs-rent model
The calculator compares the **net cost of owning** to the **net cost of renting** over a chosen horizon. Default assumptions (all adjustable on the page):

- Down payment **20%**, 30-yr fixed mortgage at the current rate
- Property tax **0.85%/yr**, insurance **$1,800/yr**, maintenance **1%/yr**, selling cost **6%**
- **4.5%** opportunity return if the down payment were invested instead
- Rent grows **4%/yr**; home appreciation is a slider (default 3%/yr)

It reports the Year-1 monthly outlay, how much of that builds equity (i.e. is not a true cost), the net cost to buy vs rent over the horizon, and the **breakeven year** at which buying overtakes renting.

#### Two asymmetries worth knowing before you read the breakeven

The model is deliberately simple, and simple in two directions that both flatter buying. Neither is a bug, but the breakeven year should be read with both in mind.

**1. The renter only invests the down payment, not the monthly difference.** The model credits the renter with 4.5%/yr on the down payment they didn't spend, but ignores the fact that renting is also *cheaper every month* — roughly $10,174 to own vs $4,772 to rent at $1.5M and 6.66%. A renter investing that monthly gap at the same 4.5% pushes the $1.5M breakeven from **~year 15 to ~year 25**. The published figure is therefore the buyer-favourable end of a range, not a midpoint.

**2. Breakeven is dominated by the appreciation slider, which is an assumption rather than an observation.** At $1.5M and 20% down:

| Appreciation | Breakeven |
|---|---|
| 3%/yr (default) | ~year 15 |
| 1%/yr | ~year 28 |
| 0%/yr | never within 30 years |

The default 3% is a long-run convention, not a forecast. Both tracked ZIPs are currently negative year-over-year, so the near-term data does not support 3% — move the slider before drawing conclusions.

**The specific YoY figures are deliberately not repeated here.** They used to be, and they drifted: this paragraph once said −3.9% / −5.2% while `data.json` held −3.3% / −10.1%, four different numbers for two ZIPs in one repo (issue #8). The caveat is now rendered under the appreciation slider by `renderApprNote()`, computed from the same `market[]` entries the tiles render, so it cannot disagree with them. Read the live figures off the page, not off this file.

Neither adjustment changes the qualitative conclusion at present rates: buying is justified by school access and stability over a long horizon, not by cost.

### Price-cut detection
Each refresh diffs the new scrape against the previous snapshot. A price decrease sets a `cut` amount and `cutDate`; the home is flagged for **30 days** (configurable via `PRICE_CUT_WINDOW_DAYS`) with a red badge, a red ▼ map marker, and an optional "price cuts first" sort.

### Catchment resolution (added 2026-08-10)

The map used to colour pins by `school`, which mixed two different kinds of thing: four verified elementary catchments and two ZIP sweeps. **54 of 74 pins were a ZIP bucket wearing a school's colours** (issue #5).

Now that every listing carries coordinates, each one is tested against the **Bellevue School District's published 2024-25 elementary attendance areas** (an open ArcGIS feature service behind the district's own school locator). Results:

- **40 of 74** listings are displayed with a verified elementary, up from 20. The resolver places 43, but 3 are suppressed as district mismatches (below).
- **All 19** homes that already carried a Redfin-derived target tag were confirmed exactly by the district's own polygons — zero disagreements. That is a genuine cross-validation of the attendance-page method, not just extra coverage.
- **4 homes previously shown as a generic "Bellevue 98008" pin are zoned to Ardmore** — the 4/10 school this entire search exists to avoid. They were invisible as such before.
- **3 homes with Redmond mailing addresses fall inside Bellevue School District attendance areas.** These carry an `elemFlag` in `data.json` and a ⚑ in the map popup. **Revised 2026-08-08:** they are no longer *displayed* with the BSD school name. Those addresses are in Lake Washington district, so a BSD polygon covering them is a boundary-file artefact, not an assignment — the site was asserting "Bennett" and "Sherwood Forest" for three homes that almost certainly attend neither. They now fall into **Not verified**, with the popup explaining the polygon hit. The flag and the resolved name stay in the data: suppressed for display, not discarded. `isVerified()` in `index.html` is the single predicate that enforces this.
- **1 Bellevue 98008 home** (4200 W Lake Sammamish Pkwy SE) falls outside every BSD attendance area, ~850 m from the nearest — too far to be an edge artefact. It is left unverified.

Pins are bucketed for display rather than given one colour per school, which would need 14 colours and imply ratings the project has not verified:

| Bucket | Meaning |
|---|---|
| Audubon / Somerset / Woodridge / Newport Heights | The four target catchments, each its own colour |
| Other catchment | Verified Bellevue elementary whose rating is **not** hand-verified here — treat as unrated |
| Weak school | Ardmore or Lake Hills only — the two low ratings checked against the primary source |
| Not verified | Drawn hollow. No boundary source covers it, or the only one that does belongs to the wrong district; the popup says which |

**Why Redmond is still unverified:** Lake Washington School District publishes attendance boundaries only as PDFs and routes address lookups through a third-party tool, so there is nothing to resolve against offline. Those 34 listings — 30 Redmond, 3 district mismatches, and one Bellevue waterfront address outside every BSD polygon — are shown as *not verified* rather than being given a colour that would imply more than is known. Expanding the refresh's Redfin school-attendance sweep to more LWSD schools is the path to closing the gap.

**The footnote renders its own numbers.** Every count in the catchment footnote — homes resolved, distinct areas, homes unverified, mismatches, and the sweep-vs-polygon cross-check verdict — is computed from `data.json` at page load by `renderCatchFootnote()`. The previous hand-written version drifted badly, still claiming the four target sets came from Redfin and that *every* Bellevue address resolved, long after neither was true. The cross-check line will state disagreement on its own if a future boundary file ever contradicts a sweep label; it never hard-codes "they agree".

### Property links and cumulative decline (added 2026-08-10)

Every listing carries `mpr`, an **address-level** realtor.com property id, resolved once per address during the refresh. Two things follow from it being address-level rather than listing-level:

- The link **survives a relist**. A Redfin or Zillow listing URL dies when a home is withdrawn and put back on; the realtor.com link keeps resolving, and still resolves after the home sells.
- The same lookup returns **coordinates** and a **for-sale status**, so the map no longer geocodes in the browser, and the run has an independent second opinion on whether a home has actually left the market.

The **R** chip and the map popup point there. The old **R** chip pointed at a constructed Redfin URL that fell back to a Google search whenever the refresh had not captured a real Redfin link — which was 73 of 74 listings. There is now **no constructed fallback anywhere**: a link is rendered only when a real URL is on file, because a link that silently goes somewhere else is worse than no link (issue #4).

#### Why cumulative decline is tracked separately from `cut`

`cut` is only the **most recent** price reduction. It systematically understates how far a seller has come down, because a home that is withdrawn and relisted at a lower number records no "cut" at all — the relist reads as a brand-new listing.

realtor.com keeps those events. 3028 173rd Ct NE is the worked example: it was listed at **$2,185,000** on 2026-05-28, relisted twice and cut once, and now asks **$1,880,000**. The snapshot recorded `cut: $100,000`. The actual decline is **$305,000, or 14%**.

So each listing may also carry `list0` (the asking price at the start of the current campaign) and `list0Date`. When present, the Price column shows a grey `↓ … total` badge alongside the red recent-cut badge. Both fields are optional and every use is guarded — rows without them simply show no badge.

**This history is read once per listing, when the home first appears — not on every refresh.** See the availability limit below.

**Availability limit:** realtor.com's history endpoint throttles. After roughly 90 requests in one session it begins returning *"No price history data is available for this property"* for pages that rendered a full history minutes earlier, while the rest of the page and the location lookup keep working normally. That message is **not data** — it is indistinguishable from a genuinely history-less property, so a bulk sweep would quietly write empty values across most of the table. The refresh therefore treats it as a retryable error, never writes an empty history over a good one, and only fetches history for newly-appearing listings (roughly 5–11 per run), with a slow re-verification sweep on the first run of each calendar month. This mirrors the CDOM policy above for the same reason.

## Automation

A scheduled task runs **Tuesday &amp; Saturday at 9 PM PT** and:

1. Re-scrapes the six Redfin sources (four school pages + two ZIP sweeps).
2. Re-checks **reference home C** by hand, since it sits outside every scrape and would otherwise go stale silently.
3. Looks up the current Freddie Mac 30-yr rate.
4. Resolves `mpr` / `lat` / `lon` for every listing via the realtor.com location lookup, retrying transient failures, and carries forward the previous value on any address that still will not resolve.
5. Fetches realtor.com price history for **newly-appearing listings only**, setting `list0` / `list0Date`, and refuses to overwrite an existing value with an empty result.
6. Diffs against the prior snapshot (new / price-changed / off-market) and updates the price-cut flags.
7. Overwrites `data.json` with the new snapshot.
8. **Appends** one entry to `archive.json` containing that run's changes and a freshly written read. Existing entries are never edited or pruned.
9. Runs `tools/validate_snapshot.py`. A non-zero exit **stops the run before the push** — see below.
10. Commits and pushes from a fresh clone; Pages rebuilds within ~a minute.
11. Runs `tools/send_newsletter.py --send`, which decides for itself whether this run warrants an email — see below.

### Pre-push validation

`tools/validate_snapshot.py` is the gate. Parsing is not the same as agreeing: the 2026-08-01 run pushed a changelog claiming seven homes went off-market when only six had, and claiming 71 tracked while the snapshot held 70. Both were internally checkable; neither was caught, because the run only validated that the files parsed.

It checks the changelog's own numbers against the snapshot it describes, that no address said to have left the market is still present, that coordinates fall inside the search area, that `list0` is genuinely above the current price, that no listing is duplicated, and that realtor-id coverage has not collapsed. Exit 1 means do not push.

`tools/enrich_catchments.py` applies the same philosophy to catchments: it fails the run when a hand-verified tag disagrees with the district boundary, when a listing loses a catchment it previously had, or when coordinates are missing — because each of those means something upstream changed.

### What the automation may and may not touch

The refresh **never authors or edits `index.html`** — the school comparison table, ratings and test scores live there and have been corrupted before by automated "fixes" pulled from search snippets. That rule is enforced by the repository layout, not by instructions.

It does, however, **carry** presentation changes that are already present in the working folder into its commit. Otherwise hand-authored edits would never reach GitHub. Write, no. Carry, yes.

The automation touches **only the two JSON files**. `index.html` — and with it the school comparison table, ratings, test scores, layout, filters, map logic and calculator — is outside its reach entirely. School stats can only be changed by a deliberate, primary-source-verified manual edit.

### The email digest

There is a **weekly email** carrying the same "what changed" list and the same read that appear on this page, with a link to each home. Subscribe from the box above the footnote, or read past issues in the [public archive](https://buttondown.com/bellevue-redmond-housing/archive/). It runs on [Buttondown](https://buttondown.com/), which was chosen over the obvious alternative because Substack has no write API — its developer API is read-only public metadata, so every issue would have to be pasted by hand, which is exactly the kind of step that stops happening after a month.

`tools/send_newsletter.py` renders the digest and posts it. Three things about it are deliberate:

- **One email a week, on Saturday.** The site refreshes twice a week; the list hears from it once. Tuesday's run still calls the script, and the script declines. At two sends a week this would be ~104 emails a year about the same 74 houses, which is how you earn unsubscribes rather than readers.
- **Only when something happened** — a new listing, a price cut, a home going pending or leaving the market, or a rate move of at least 0.10 points. A quiet Saturday sends **nothing at all**. Not a "no news this week" email: that is still an email.
- **Last in the run, after the push.** A bad commit can be reverted. A bad email cannot — it is in inboxes within seconds and there is no undo. So the email only happens on a run that already cleared the validator and reached GitHub. Validator red means no push, and no push means no send.

The gates read the **snapshot's own date** rather than the clock, so a run that starts at 9 PM Saturday and finishes after midnight still reports Saturday's run as Saturday's. The script also refuses outright when `data.json` and the newest `archive.json` entry are stamped with different dates, since the two files would then be describing different runs.

Property links in the email come from the stored realtor.com `mpr` id and from nothing else, on the same rule the page follows: a listing without one is rendered without a link rather than with a constructed one.

`--dry-run` prints the rendered Markdown and touches no network; without `--send` it creates a draft rather than sending. The API key lives in `.buttondown-credentials` at the repo root — mode 600, gitignored, never in the repo.

### Writing the read

The read is the easiest place for an automated run to introduce a false claim, so it is regenerated from scratch each time under explicit grounding rules: every figure must trace to that run's own data or to a re-run of the page's calculator model at the **live** rate, nothing carries over from the previous read, and the buy-vs-rent lean must match what the model actually returns rather than what the previous run concluded.

## Tech

- **`index.html`** — presentation only. Markup, styles, rendering, filters, map and calculator. Contains **no data**.
- Libraries via CDN: **Leaflet** (map), **Grid.js** (table), **Chart.js** (price histogram).
- No build step and no backend — the page fetches its two data files at load time.
- Hosted on **GitHub Pages**.

## Repository layout

The data layer is deliberately kept out of the presentation layer, split by **lifecycle** rather than by topic:

| File | Lifecycle | Contents |
|---|---|---|
| `index.html` | changes rarely, by hand | Presentation + the static school-comparison table. **The refresh task never opens this file.** |
| `data.json` | fully replaced every run | `updated`, `market`, `refs`, `refC`, `listings` — the current snapshot only |
| `archive.json` | append-only, never rewritten | `entries: [{ date, changes[], read? }]` — one entry per refresh, kept forever |
| `bsd-elementary-2024-25.geojson` | refreshed once a school year | Bellevue School District elementary attendance areas, 14 polygons |
| `tools/enrich_catchments.py` | changes rarely, by hand | Point-in-polygon catchment resolution. Standard library only |
| `tools/validate_snapshot.py` | changes rarely, by hand | Pre-push invariants. Exit 1 blocks the push |
| `tools/send_newsletter.py` | changes rarely, by hand | Renders the run as a Markdown digest and posts it to Buttondown. Standard library only. Runs last, after the push |

Two reasons for the split:

1. **The guardrail becomes structural.** School ratings and test scores have been corrupted before by automated "fixes" pulled from search snippets. Now they live in a file the refresh task has no reason to open, so the rule is enforced by the layout instead of by instructions.
2. **The archive grows without bloating first paint.** At two refreshes a week the changelog and reads accumulate roughly 350 KB/year. Keeping them in a separate file means the snapshot the page needs immediately stays small and bounded.

`archive.json` pairs each date's changes with the read written from them, so history is one list, not two that can drift apart.

## Caveats

- This is **not** financial, investment, or real-estate advice.
- School attendance boundaries change — always confirm a specific address with the **district's boundary tool** before relying on its assigned school.
- Listing data is third-party (MLS Grid) and can lag the market; verify any listing directly before acting.
