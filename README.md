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
- **"What changed"** — a changelog of new listings, price drops, and homes that went off-market, refreshed every run.
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

### Price-cut detection
Each refresh diffs the new scrape against the previous snapshot. A price decrease sets a `cut` amount and `cutDate`; the home is flagged for **30 days** (configurable via `PRICE_CUT_WINDOW_DAYS`) with a red badge, a red ▼ map marker, and an optional "price cuts first" sort.

## Automation

A scheduled task runs **Tuesday &amp; Saturday at 9 PM PT** and:

1. Re-scrapes the six Redfin sources (four school pages + two ZIP sweeps).
2. Looks up the current Freddie Mac 30-yr rate.
3. Diffs against the prior snapshot (new / price-changed / off-market) and updates the price-cut flags.
4. Rewrites **only** the page's `DATA` object (listings, market snapshot, changelog) and prepends a changelog entry.
5. Commits and pushes to GitHub; Pages rebuilds within ~a minute.

The automation is **strictly limited to the `DATA` object**. The school comparison table, ratings, test scores, layout, filters, map logic, and calculator are off-limits to it — school stats can only be changed by a deliberate, primary-source-verified manual edit.

## Tech

- A single, self-contained **`index.html`** — no build step, no backend.
- Libraries via CDN: **Leaflet** (map), **Grid.js** (table), **Chart.js** (price histogram).
- Hosted on **GitHub Pages**.

## Caveats

- This is **not** financial, investment, or real-estate advice.
- School attendance boundaries change — always confirm a specific address with the **district's boundary tool** before relying on its assigned school.
- Listing data is third-party (MLS Grid) and can lag the market; verify any listing directly before acting.
