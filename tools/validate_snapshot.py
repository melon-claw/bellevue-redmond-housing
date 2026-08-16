#!/usr/bin/env python3
"""Pre-push invariants for the Bellevue/Redmond tracker. Run this before `git push`, always.

Run:  python3 tools/validate_snapshot.py [--data data.json] [--archive archive.json]
      [--prev PREV_DATA_JSON]   # the previous run's snapshot, if you kept a copy

Exit 0 = safe to push. Exit 1 = do not push, and say why in the run summary.

Why this exists
---------------
The 2026-08-01 run pushed a changelog claiming seven homes went off-market when only six had,
and claiming 71 tracked when the snapshot held 70. Both were internally checkable and neither
was caught, because the run validated only that the files parsed. Parsing is not agreement.

Every check below is one that would have caught a real defect that shipped, or that guards a
field the page renders directly. Checks are ordered cheapest-first; all of them run so you get
the full picture in one pass rather than one failure at a time.
"""

import argparse
import json
import re
import sys

# The Bellevue/Redmond search box. Anything outside this is a geocoding mis-parse, not a house.
LAT_MIN, LAT_MAX = 47.45, 47.80
LON_MIN, LON_MAX = -122.30, -122.02

PROBLEMS = []
NOTES = []


def fail(msg):
    PROBLEMS.append(msg)


def note(msg):
    NOTES.append(msg)


def check_listings(listings):
    if not listings:
        fail("data.json has no listings at all")
        return

    seen_addr = {}
    for x in listings:
        addr = x.get("addr")
        if not addr:
            fail("a listing has no address")
            continue
        if addr in seen_addr:
            fail("duplicate listing: %s appears more than once" % addr)
        seen_addr[addr] = x

        for field in ("city", "zip", "price", "beds", "sqft"):
            if x.get(field) in (None, ""):
                fail("%s: missing %s" % (addr, field))

        if not isinstance(x.get("price"), (int, float)) or x["price"] <= 0:
            fail("%s: price is not a positive number" % addr)

        lat, lon = x.get("lat"), x.get("lon")
        if lat is None or lon is None:
            fail("%s: no coordinates — the map cannot place it and the catchment cannot resolve"
                 % addr)
        else:
            if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
                fail("%s: coordinates %s,%s fall outside the search area" % (addr, lat, lon))

        mpr = x.get("mpr")
        if mpr is not None and not re.fullmatch(r"\d+", str(mpr)):
            fail("%s: mpr %r is not a numeric property id" % (addr, mpr))

        # A "total decline" badge only makes sense if the campaign opened above today's ask.
        if "list0" in x:
            if not isinstance(x["list0"], (int, float)):
                fail("%s: list0 is not a number" % addr)
            elif x["list0"] <= x.get("price", 0):
                fail("%s: list0 %s is not above the current price %s — the decline badge would "
                     "render nonsense" % (addr, x["list0"], x.get("price")))

        if "cut" in x and x.get("cut", 0) < 0:
            fail("%s: negative cut amount" % addr)

        if x.get("elem") and not x.get("elemSrc"):
            fail("%s: has a catchment but no source recorded for it" % addr)

    n = len(listings)
    with_mpr = sum(1 for x in listings if x.get("mpr"))
    with_elem = sum(1 for x in listings if x.get("elem"))
    with_hist = sum(1 for x in listings if x.get("list0"))
    note("listings %d | realtor id %d | catchment %d | campaign-start price %d"
         % (n, with_mpr, with_elem, with_hist))

    # Coverage floors. These are not style points: if the realtor lookup silently starts failing,
    # the R chips vanish from the page and nobody notices for weeks.
    if with_mpr < n * 0.9:
        fail("only %d of %d listings have a realtor.com id (expected nearly all) — the lookup "
             "step probably failed" % (with_mpr, n))


def check_archive(archive, listings):
    entries = (archive or {}).get("entries") or []
    if not entries:
        fail("archive.json has no entries")
        return
    newest = entries[0]
    date = newest.get("date", "?")

    dates = [e.get("date") for e in entries if e.get("date")]
    if dates != sorted(dates, reverse=True):
        fail("archive entries are not in newest-first order")
    if len(set(dates)) != len(dates):
        fail("archive has two entries with the same date")

    # The Aug 1 defect: the changelog's own numbers disagreeing with the snapshot it describes.
    text = " ".join(newest.get("changes") or [])
    claimed = re.findall(r"[Tt]racking\s+(\d+)", text)
    for c in claimed:
        if int(c) != len(listings):
            fail("the %s changelog says 'tracking %s' but data.json holds %d listings"
                 % (date, c, len(listings)))

    # Any address the changelog says left the market must actually be gone.
    addrs = {x["addr"] for x in listings if x.get("addr")}
    for chunk in (newest.get("changes") or []):
        low = chunk.lower()
        if "off the market" in low or "left the market" in low or "delisted" in low:
            for a in addrs:
                if a in chunk:
                    fail("the %s changelog says %s left the market, but it is still in data.json"
                         % (date, a))
    note("newest archive entry %s with %d change note(s)" % (date, len(newest.get("changes") or [])))


def check_prev(prev, listings):
    """prev + new - gone == now. Skipped when no previous snapshot is supplied."""
    prev_addrs = {x["addr"] for x in (prev.get("listings") or []) if x.get("addr")}
    now_addrs = {x["addr"] for x in listings if x.get("addr")}
    added = now_addrs - prev_addrs
    gone = prev_addrs - now_addrs
    if len(prev_addrs) + len(added) - len(gone) != len(now_addrs):
        fail("listing arithmetic does not close: %d previous + %d new - %d gone != %d now"
             % (len(prev_addrs), len(added), len(gone), len(now_addrs)))
    note("vs previous snapshot: %d new, %d gone, %d carried over"
         % (len(added), len(gone), len(now_addrs & prev_addrs)))


def check_market(market):
    """Issue #8. The two ZIP tiles shipped as 'median sale price (King County MLS)' while carrying
    Zillow ZHVI values, and the level and the YoY came from different series/vintages, which is what
    manufactured a -10.1% for 98008 that no source reproduces.

    The decisive check is the round-number one. A median of transactions is a closing price, or the
    midpoint of two closing prices, so it inherits their $500/$2,500 granularity. $1,379,688 is not a
    number any list of sale prices produces -- it is model output. That single test would have caught
    this bug on the day it shipped, without anyone needing to re-derive the YoY.
    """
    if not market:
        fail("data.json has no market[] tiles at all")
        return

    seen_lbl = set()
    for row in market:
        lbl = (row.get("lbl") or "").strip()
        if not lbl:
            fail("a market[] tile has no label")
            continue
        if lbl in seen_lbl:
            fail("market tile %r appears more than once" % lbl)
        seen_lbl.add(lbl)

        # Provenance is mandatory. A level and a percentage with no stated series is exactly the
        # shape of the defect: nothing on the tile said what it was, so nothing contradicted it.
        for field in ("src", "asof"):
            if not (row.get(field) or "").strip():
                fail("%s: missing %s -- every tile must state its own series and vintage" % (lbl, field))

        asof = (row.get("asof") or "").strip()
        if asof and not re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", asof):
            fail("%s: asof %r is not YYYY-MM-DD or YYYY-MM" % (lbl, asof))

        val = str(row.get("val") or "")
        money = re.fullmatch(r"\$([\d,]+)(?:/mo)?", val.strip())
        amount = int(money.group(1).replace(",", "")) if money else None

        # A tile that calls itself a median must BE a median.
        if re.search(r"\bmedian\b", lbl, re.I) or re.search(r"\bmedian\b", str(row.get("src") or ""), re.I):
            if amount is None:
                fail("%s: labelled a median but %r is not a dollar amount" % (lbl, val))
            elif amount % 100 != 0:
                fail("%s: %s is labelled a median but is not a round dollar amount. A median of "
                     "transactions is a closing price (or the midpoint of two), so it cannot be "
                     "non-round to the dollar. This is a model estimate -- ZHVI or similar -- "
                     "mislabelled as a median (issue #8)." % (lbl, val))
            n = row.get("n")
            if n is None:
                fail("%s: an MLS-median tile must render its sale count (\"n\"). A monthly ZIP median "
                     "over ~30 sales has a sampling error near 7%%, so a YoY print without n hides "
                     "the one number that says whether it means anything." % lbl)
            elif not isinstance(n, int) or n < 0:
                fail("%s: sale count n=%r is not a non-negative integer" % (lbl, n))
            elif n < 50 and str(row.get("delta") or "").strip():
                fail("%s: n=%d is below the 50-sale threshold, so the YoY must be suppressed rather "
                     "than rendered as a confident-looking percentage." % (lbl, n))

        # ZHVI must never be described as a median or attributed to the MLS.
        blob = " ".join(str(row.get(k) or "") for k in ("lbl", "src", "delta"))
        if re.search(r"\bZHVI\b", blob, re.I):
            if re.search(r"\bmedian\b", blob, re.I):
                fail("%s: ZHVI is a typical-value index, not a median sale price -- do not call it one"
                     % lbl)
            if re.search(r"\bMLS\b", blob, re.I):
                fail("%s: ZHVI does not come from the MLS -- drop the MLS attribution" % lbl)

    # Tiles that are compared side by side must say which series each came from. Two ZIP tiles on
    # different series, or on vintages months apart, is a cross-ZIP comparison that is not
    # like-for-like -- and in a falling market the skew is the whole story.
    zips = [r for r in market if re.match(r"\s*(Redmond|Bellevue)\s+9\d{4}\b", r.get("lbl") or "")]
    srcs = {(r.get("src") or "").strip() for r in zips}
    if len(zips) >= 2 and len(srcs) > 1:
        fail("the ZIP tiles are on different series (%s) and are still rendered side by side. Either "
             "put them on one series or say on the page that they are not comparable."
             % "; ".join(sorted(srcs)))
    asofs = {(r.get("asof") or "").strip() for r in zips}
    if len(zips) >= 2 and len(asofs) > 1:
        note("ZIP tiles are on different vintages (%s) -- allowed, because each tile renders its own "
             "asof, but any cross-ZIP claim in the read must acknowledge it" % ", ".join(sorted(asofs)))


def check_zhvi(z):
    """The Eastside context band (issue #8 fix E). Same rules: one series, per-row vintage."""
    if not z:
        note("no zhvi context band in this snapshot")
        return
    rows = z.get("rows") or []
    if not (z.get("src") or "").strip():
        fail("zhvi block has no src")
    if len(rows) < 2:
        fail("zhvi context band needs at least two ZIPs to be context at all")
    seen = set()
    for r in rows:
        zp = str(r.get("zip") or "")
        if not re.fullmatch(r"9\d{4}", zp):
            fail("zhvi row has a bad ZIP: %r" % zp)
        if zp in seen:
            fail("zhvi row %s appears more than once" % zp)
        seen.add(zp)
        if not isinstance(r.get("val"), (int, float)) or r["val"] <= 0:
            fail("zhvi %s: value %r is not a positive number" % (zp, r.get("val")))
        if not isinstance(r.get("yoy"), (int, float)):
            fail("zhvi %s: yoy %r is not a number" % (zp, r.get("yoy")))
        elif abs(r["yoy"]) > 25:
            fail("zhvi %s: a %.1f%% one-year move in a ZIP this size is a parse error, not a market "
                 "event -- verify before shipping" % (zp, r["yoy"]))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(r.get("asof") or "")):
            fail("zhvi %s: asof %r is not YYYY-MM-DD" % (zp, r.get("asof")))

    # The band must actually contain the ZIPs the tiles headline, or it is not context for them.
    for core in ("98008", "98052"):
        if core not in seen:
            fail("zhvi band omits %s, one of the two headline ZIPs" % core)


def check_market_vs_zhvi(market, z):
    """The tiles and the band are two renderings of one series. If they disagree, one is stale."""
    if not z:
        return
    by_zip = {str(r.get("zip")): r for r in (z.get("rows") or [])}
    for row in market:
        m = re.search(r"\b(9\d{4})\b", row.get("lbl") or "")
        if not m or m.group(1) not in by_zip:
            continue
        band = by_zip[m.group(1)]
        money = re.fullmatch(r"\$([\d,]+)", str(row.get("val") or "").strip())
        if money and int(money.group(1).replace(",", "")) != band.get("val"):
            fail("%s: tile says %s but the zhvi band says $%s for the same ZIP -- one of them is stale"
                 % (row["lbl"], row["val"], format(band.get("val"), ",")))
        pct = re.match(r"\s*([+-]?\d+(?:\.\d+)?)%", str(row.get("delta") or ""))
        if pct and abs(float(pct.group(1)) - float(band.get("yoy", 0))) > 0.05:
            fail("%s: tile YoY %s disagrees with the zhvi band's %.1f%% for the same ZIP"
                 % (row["lbl"], row.get("delta"), band.get("yoy")))
        if (row.get("asof") or "") != (band.get("asof") or ""):
            fail("%s: tile asof %r disagrees with the zhvi band's %r for the same ZIP -- the level and "
                 "the change must come from ONE vintage" % (row["lbl"], row.get("asof"), band.get("asof")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data.json")
    ap.add_argument("--archive", default="archive.json")
    ap.add_argument("--prev", default=None)
    args = ap.parse_args()

    try:
        with open(args.data) as fh:
            data = json.load(fh)
    except Exception as exc:
        sys.exit("data.json does not parse: %s" % exc)
    try:
        with open(args.archive) as fh:
            archive = json.load(fh)
    except Exception as exc:
        sys.exit("archive.json does not parse: %s" % exc)

    listings = data.get("listings") or []
    market = data.get("market") or []
    zhvi = data.get("zhvi")
    check_listings(listings)
    check_market(market)
    check_zhvi(zhvi)
    check_market_vs_zhvi(market, zhvi)
    check_archive(archive, listings)

    if args.prev:
        try:
            with open(args.prev) as fh:
                check_prev(json.load(fh), listings)
        except FileNotFoundError:
            note("no previous snapshot supplied — listing arithmetic not checked")

    for n in NOTES:
        print("  " + n)
    if PROBLEMS:
        print("\n%d problem(s) — DO NOT PUSH:" % len(PROBLEMS))
        for p in PROBLEMS:
            print("  - " + p)
        return 1
    print("\nall invariants hold — safe to push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
