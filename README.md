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

- **Market snapshot** — median sale price + YoY for each core ZIP, current 30-yr mortgage rate, average local 4BD rent.
- **"What changed"** — a paginated, append-only changelog of new listings, price drops, and homes that went off-market. Every entry back to the first run is kept; each one also carries **that run's read**, expandable inline.
- **"The read"** — a short written interpretation of the current data (inventory, momentum, financing, entry price, implication), rewritten from scratch every refresh and grounded in that run's numbers. Past reads are never overwritten — they are archived alongside the changelog entry that produced them, so you can page back and see what the data looked like *and* what it was taken to mean.
- **School comparison** — the four target elementaries side by side (rating, math/reading scores, boundary, commute).
- **Filters** — a budget range (min/max + presets) and a school-catchment toggle group that drive the map and table together.
- **Map** — every listing geocoded and color-coded by school catchment; a **red ▼ triangle** marks a recent price cut and a **red ring** marks a toured reference home.
- **Buy-vs-rent calculator** — interactive sliders for price, down payment, rate, rent, appreciation, and horizon; shows monthly cost, equity build-up, net cost to buy vs rent, and the breakeven year.
- **Listings table** — sortable/searchable, with one-click Zillow / Redfin / Google Maps links and price-cut badges.

## Data sources

| Data | Source |
|------|--------|
| For-sale listings | **Redfin** (NWMLS / MLS Grid) — ZIP sweeps (98052, 98008) and per-school attendance pages |
| Listing cross-reference | **Zillow** (per-address links) |
| School ratings &amp; test scores | **GreatSchools** profiles (Washington OSPI assessment data) |
| Mortgage rate | **Freddie Mac** PMMS (30-yr fixed) |
| Map geocoding | **OpenStreetMap** Nominatim (client-side, cached in the browser) |

## Methodology

### Listing selection
- **Scope:** 4-bedroom-or-more single-family houses, priced up to **$2M**, in two core ZIPs (**Redmond 98052**, **Bellevue 98008**) plus four target school catchments (**98006 / 98005** for the Bellevue schools).
- **School-zoned sets** (Audubon, Somerset, Woodridge, Newport Heights) come from **Redfin's school-attendance pages**, which list homes actually *served by* that school — so each is tagged with a verified catchment.
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

The default 3% is a long-run convention. Both tracked ZIP medians are currently **negative** year-over-year (Redmond 98052 −3.9%, Bellevue 98008 −5.2%), so the near-term data does not support 3% — move the slider before drawing conclusions.

Neither adjustment changes the qualitative conclusion at present rates: buying is justified by school access and stability over a long horizon, not by cost.

### Price-cut detection
Each refresh diffs the new scrape against the previous snapshot. A price decrease sets a `cut` amount and `cutDate`; the home is flagged for **30 days** (configurable via `PRICE_CUT_WINDOW_DAYS`) with a red badge, a red ▼ map marker, and an optional "price cuts first" sort.

## Automation

A scheduled task runs **Tuesday &amp; Saturday at 9 PM PT** and:

1. Re-scrapes the six Redfin sources (four school pages + two ZIP sweeps).
2. Re-checks **reference home C** by hand, since it sits outside every scrape and would otherwise go stale silently.
3. Looks up the current Freddie Mac 30-yr rate.
4. Diffs against the prior snapshot (new / price-changed / off-market) and updates the price-cut flags.
5. Overwrites `data.json` with the new snapshot.
6. **Appends** one entry to `archive.json` containing that run's changes and a freshly written read. Existing entries are never edited or pruned.
7. Validates both files parse and the counts agree, then commits and pushes; Pages rebuilds within ~a minute.

The automation touches **only the two JSON files**. `index.html` — and with it the school comparison table, ratings, test scores, layout, filters, map logic and calculator — is outside its reach entirely. School stats can only be changed by a deliberate, primary-source-verified manual edit.

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

Two reasons for the split:

1. **The guardrail becomes structural.** School ratings and test scores have been corrupted before by automated "fixes" pulled from search snippets. Now they live in a file the refresh task has no reason to open, so the rule is enforced by the layout instead of by instructions.
2. **The archive grows without bloating first paint.** At two refreshes a week the changelog and reads accumulate roughly 350 KB/year. Keeping them in a separate file means the snapshot the page needs immediately stays small and bounded.

`archive.json` pairs each date's changes with the read written from them, so history is one list, not two that can drift apart.

## Caveats

- This is **not** financial, investment, or real-estate advice.
- School attendance boundaries change — always confirm a specific address with the **district's boundary tool** before relying on its assigned school.
- Listing data is third-party (MLS Grid) and can lag the market; verify any listing directly before acting.
