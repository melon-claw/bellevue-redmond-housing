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
    check_listings(listings)
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
