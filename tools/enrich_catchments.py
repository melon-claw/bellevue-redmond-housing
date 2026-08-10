#!/usr/bin/env python3
"""Resolve each listing's assigned elementary school from published attendance boundaries.

Reads   data.json                       (listings, each needing lat/lon)
        bsd-elementary-2024-25.geojson   (Bellevue School District attendance areas)
Writes  data.json                       (adds elem / elemSrc / elemFlag per listing)

Standard library only — no shapely, no numpy, nothing to install. The refresh task runs on
whatever Python the desktop happens to have, so this deliberately has no dependencies.

Run:  python3 tools/enrich_catchments.py [--data data.json] [--boundaries FILE] [--check]

--check reports what would change and writes nothing. Exit code is 0 on success, 1 if an
invariant fails (see "Invariants" below) — the refresh should treat a non-zero exit as a
failed run and NOT push.

Invariants
----------
1. Every listing already has numeric lat/lon. Without coordinates there is nothing to resolve,
   and silently skipping would look identical to "no boundary covers this home".
2. A listing resolves only if exactly ONE polygon contains it. Never fall back to the nearest
   polygon: the closest school is not the assigned school.
3. A listing that already carries a hand-verified target tag (Audubon, Somerset, Woodridge,
   Newport Heights) must not be contradicted silently. If the district polygon disagrees with
   the Redfin-derived tag, that is reported and the run fails. As of 2026-08-10 all 19 such
   listings agreed, so a disagreement means something upstream changed and a human should look.
4. Resolution never removes a previously good value by accident: if a listing had `elem` and now
   resolves to nothing, that is reported and the run fails.
"""

import argparse
import json
import sys

# The four catchments the search is built around. These are verified from Redfin school
# attendance pages during the scrape, so they are trusted even outside BSD's boundary file
# (Audubon is in Lake Washington SD, which publishes no machine-readable boundaries).
TARGETS = {"Audubon", "Somerset", "Woodridge", "Newport Heights"}


def rings_of(geom):
    """Yield each linear ring of a Polygon or MultiPolygon as a list of (lon, lat) points.

    Yields (ring, is_outer). Holes matter: Bellevue's attendance areas are not all simply
    connected, and treating a hole as solid would assign homes to a school they are carved
    out of.
    """
    t = geom.get("type")
    if t == "Polygon":
        polys = [geom["coordinates"]]
    elif t == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        return
    for poly in polys:
        for i, ring in enumerate(poly):
            yield ring, (i == 0)


def point_in_ring(x, y, ring):
    """Ray-casting test. Returns True if (x, y) is inside the ring."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        # Does the edge straddle the horizontal line through y, and is the crossing to the right?
        if (yi > y) != (yj > y):
            denom = (yj - yi)
            if denom != 0 and x < (xj - xi) * (y - yi) / denom + xi:
                inside = not inside
        j = i
    return inside


def point_in_geometry(x, y, geom):
    """True if the point falls inside an outer ring and not inside any hole of that polygon."""
    t = geom.get("type")
    polys = [geom["coordinates"]] if t == "Polygon" else geom["coordinates"] if t == "MultiPolygon" else []
    for poly in polys:
        if not poly:
            continue
        if point_in_ring(x, y, poly[0]):
            in_hole = any(point_in_ring(x, y, hole) for hole in poly[1:])
            if not in_hole:
                return True
    return False


def load_boundaries(path):
    with open(path) as fh:
        gj = json.load(fh)
    out = []
    for f in gj.get("features", []):
        name = (f.get("properties") or {}).get("BSD_Name") or ""
        name = name.replace(" Elementary", "").strip()
        if name and f.get("geometry"):
            out.append((name, f["geometry"]))
    if not out:
        sys.exit("boundary file contained no usable polygons: " + path)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data.json")
    ap.add_argument("--boundaries", default="bsd-elementary-2024-25.geojson")
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    polys = load_boundaries(args.boundaries)
    with open(args.data) as fh:
        data = json.load(fh)
    listings = data.get("listings", [])

    missing_coords = [x.get("addr") for x in listings
                      if not isinstance(x.get("lat"), (int, float)) or not isinstance(x.get("lon"), (int, float))]

    resolved = ambiguous = unresolved = mismatched = 0
    conflicts, regressions = [], []

    for x in listings:
        lat, lon = x.get("lat"), x.get("lon")
        had = x.get("elem")

        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue  # reported separately; leave whatever was there alone

        hits = [n for n, g in polys if point_in_geometry(lon, lat, g)]

        if len(hits) == 1:
            name = hits[0]
            if x.get("school") in TARGETS and x["school"] != name:
                conflicts.append((x.get("addr"), x["school"], name))
            x["elem"] = name
            x["elemSrc"] = "bsd-2024-25"
            # A Redmond mailing address inside a Bellevue SD attendance area is a real thing,
            # not a bug — but it is surprising enough to surface rather than quietly accept.
            if x.get("sd") != "BSD":
                x["elemFlag"] = "district-mismatch"
                mismatched += 1
            else:
                x.pop("elemFlag", None)
            resolved += 1
        elif len(hits) > 1:
            ambiguous += 1
            conflicts.append((x.get("addr"), "overlapping polygons", "|".join(hits)))
        else:
            # No BSD polygon. Keep a hand-verified target tag; otherwise leave unresolved.
            if x.get("school") in TARGETS:
                x["elem"] = x["school"]
                x["elemSrc"] = "redfin-attendance"
                x.pop("elemFlag", None)
                resolved += 1
            else:
                x.pop("elem", None)
                x.pop("elemSrc", None)
                x.pop("elemFlag", None)
                unresolved += 1
                if had:
                    regressions.append((x.get("addr"), had))

    total = len(listings)
    print("listings           : %d" % total)
    print("resolved catchment : %d" % resolved)
    print("unresolved         : %d  (no boundary source covers them)" % unresolved)
    print("district mismatch  : %d  (Redmond address inside a BSD attendance area)" % mismatched)
    if ambiguous:
        print("ambiguous          : %d" % ambiguous)

    ok = True
    if missing_coords:
        ok = False
        print("\nFAIL: %d listing(s) have no coordinates, so their catchment cannot be resolved:" % len(missing_coords))
        for a in missing_coords[:10]:
            print("  - %s" % a)
    if conflicts:
        ok = False
        print("\nFAIL: verified tag disagrees with the district boundary — do not push, look at these:")
        for addr, was, now in conflicts:
            print("  - %s: tagged %r, boundary says %r" % (addr, was, now))
    if regressions:
        ok = False
        print("\nFAIL: %d listing(s) lost a catchment they previously had:" % len(regressions))
        for addr, was in regressions[:10]:
            print("  - %s (was %s)" % (addr, was))

    if not ok:
        print("\nNothing written.")
        return 1

    if args.check:
        print("\n--check: no changes written.")
        return 0

    with open(args.data, "w") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
    print("\nwrote %s" % args.data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
