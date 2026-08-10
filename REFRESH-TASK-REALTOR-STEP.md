# Refresh task — realtor.com enrichment step

Add this to the twice-weekly refresh task, between the Redfin scrape and the diff/write.
Everything below was verified live on 2026-08-10 against the 74 listings then in `data.json`.

---

## 0. Where this has to run

The lookup **must run inside a browser tab whose origin is `realtor.com`** (Claude-in-Chrome).

- `curl` from a server gets **429**.
- `fetch()` from any other origin is **CORS-blocked**.
- Navigate a tab to any realtor.com page first, then run the calls from that tab's context.

---

## 1. Location lookup — run for every listing, every refresh

One POST per address. Cheap, fast, and it did **not** degrade under load.

```
POST https://www.realtor.com/frontdoor/parser/v1/suggest-filters

headers:
  content-type:       application/json
  rdc-client-name:    RDC_WEB_SRP_HOME_SEARCH
  rdc-client-version: 3.x

body:
  {"search_input":{"search_term":"<addr>, <city>, WA <zip>"},
   "limit":3,"area_types":["address"]}
```

Both `rdc-*` headers are required — omitting them returns 400 `Client Information Headers
Validation Error`. The body key is `search_input.search_term`; `input`, `search_input.location`,
`search_input.query` and `search_input.text` all 400.

Read `data.location_candidates[0].geo` and write onto the listing:

| Field | From | Notes |
|---|---|---|
| `mpr` | `geo.mpr_id` | string. Property link is `https://www.realtor.com/realestateandhomes-detail/M<mpr>` |
| `lat` | `geo.lat` | number, 6dp |
| `lon` | `geo.lon` | number, 6dp |

Also read `geo.prop_status` (array) — **do not store it**, use it as a cross-check (step 3).

**Guards:**

- Accept a candidate only if `geo.area_type === "address"` and `geo.mpr_id` is present.
- Reject if `geo.postal_code !== listing.zip`. A ZIP mismatch means the parser matched a
  different property.
- On non-200, **retry up to 3 times with 1.5s / 3s / 4.5s backoff.** Transient 502s do happen —
  one occurred in a 74-address run and succeeded on the first retry.
- If an address still will not resolve, **carry forward the previous run's `mpr`/`lat`/`lon`**.
  Never blank a field that previously had a good value.
- Sleep ~320ms between addresses. A 74-address sweep takes about 2-3 minutes.

**Expected result:** 74/74 resolved, 74/74 ZIP-matched on the 2026-08-08 snapshot.

---

## 2. Price history — new listings only

**Do not sweep this over the whole table.** See the throttling warning below.

Run only for listings that are **new this run** (typically 5-11), plus a slow re-verification
pass on the first run of each calendar month.

Procedure per listing:

1. Navigate to `https://www.realtor.com/realestateandhomes-detail/M<mpr>`.
2. Expand the **"Property history"** accordion. The content is not in `__NEXT_DATA__`, is not in
   the `fetch()`-able HTML (that returns a ~19KB shell), and expanding fires **no XHR** — so
   there is no JSON endpoint to hit. A real navigation plus a click is the only route.
3. Parse `document.body.innerText` between `"Price history"` and `"Tax history"`. The format is
   regular: a date line, an optional `"N days after listed"` line, the event
   (`Listed` / `Price decreased` / `Listing removed` / `Sold`), the source, the price, `$/sqft`.
4. Walk **backwards from today** to the start of the *current* campaign — the earliest `Listed`
   event not separated from today by a `Sold`. Write:
   - `list0` — the asking price at that first `Listed` event
   - `list0Date` — its date (ISO)

### The guard that matters

realtor.com's history endpoint throttles, and **it fails silently**. After roughly 90 requests in
one session, pages that had rendered a full history minutes earlier began returning:

> No price history data is available for this property

...while the rest of the page rendered normally and the step-1 lookup kept returning 200.

That string is **not data**. It is indistinguishable from a genuinely history-less property, so:

- Treat *"No price history data is available"* as a **retryable error**, never as a result.
- **Never overwrite an existing `list0` with an empty result.** Leave the old value in place.
- If a new listing's history cannot be read, leave `list0` **absent**. The page guards every use,
  so the row just shows no decline badge. An absent field is correct; a wrong one is not.
- Log every listing whose history could not be read, and surface the count in the run summary.
  Silent truncation is the failure mode this project has already been bitten by twice.

---

## 2b. Elementary catchment — resolve from coordinates

Once `lat`/`lon` exist, resolve the assigned elementary offline. No scraping, no rate limit.

Boundary source (Bellevue School District, 2024-25, public):

```
https://services1.arcgis.com/DjfAyvUwdiY6gnFC/arcgis/rest/services/BSD_School_Locator/FeatureServer/1/query
  ?where=1%3D1&outFields=*&outSR=4326&f=geojson
```

14 polygons, `BSD_Name` is the school. Cache the GeoJSON in the repo and refetch it once a
school year — attendance areas change at most annually, and pinning it means the refresh does
not depend on a live service.

Per listing, point-in-polygon (shapely) and write:

| Field | Value |
|---|---|
| `elem` | school name, minus the trailing " Elementary" |
| `elemSrc` | `bsd-2024-25`, or `redfin-attendance` for the four target sets outside BSD |
| `elemFlag` | `district-mismatch` when a polygon matches but `sd` is not `BSD` |

**Guards:**

- Exactly one containing polygon, or treat as unresolved. Do not take the nearest.
- If a listing already carries a Redfin-verified target tag and the polygon **disagrees**, do
  not silently pick one — flag it. On the 2026-08-10 data all 19 agreed, so a disagreement is
  a signal that something upstream changed.
- Leave `elem` absent for anything unresolved. The page draws those hollow and labels them
  "Not verified". An absent field is correct; a guessed one is not.
- Lake Washington School District has no machine-readable boundaries, so all Redmond 98052
  homes stay unresolved. To close that gap, expand the Redfin school-attendance sweep in step 1
  of the refresh to more LWSD elementaries — that is the same mechanism already used for Audubon.

---

## 3. Free validation — use it

`geo.prop_status` gives an independent read on whether a home is still on the market. Before
writing the changelog:

- If the diff says a home **went off-market** but realtor still reports `for_sale`, flag it for
  review rather than asserting it.
- If a home is still in the snapshot but realtor reports only `off_market` / `recently_sold`,
  flag that too.

The 2026-08-01 run shipped a changelog claiming 7 homes went off-market when only 6 had. This
check would have caught it.

---

## 4. Pre-push invariants

Add to the existing validation:

- `len([x for x in listings if x.get("mpr")])` is reported in the run summary, and a drop of more
  than 5 from the previous run **fails the run** rather than pushing.
- Every `lat` is within `47.5 – 47.78` and every `lon` within `-122.25 – -122.05`. Anything
  outside that box is a mis-parse, not a house in Bellevue or Redmond.
- No listing has `list0 <= price` (that would render a nonsensical "decline").
- `data.json` parses and the listing count matches the changelog's claim.

---

## 5. What the page does with these fields

`index.html` reads them defensively — it needs no changes when a field is missing:

- `mpr` → the **R** chip and the map popup link. Absent: no chip.
- `lat`/`lon` → map pin placement. Absent: falls back to in-browser Nominatim geocoding.
- `list0`/`list0Date` → the grey `↓ … total` badge in the Price column. Absent: no badge.
- `elem`/`elemSrc` → pin colour, the School column, and the catchment filter. Absent: the pin is
  drawn hollow and labelled "Not verified · &lt;zip&gt;".
- `elemFlag` → a ⚑ in the map popup. Absent: nothing shown.

Note the ordering dependency: if the refresh task is **not** updated, the next run replaces
`data.json` without these fields and the page silently reverts to Zillow/Maps chips and
browser-side geocoding. Nothing breaks, but the improvement disappears.
