#!/usr/bin/env python3
"""Render the latest refresh into a Markdown digest and hand it to Buttondown.

Reads   data.json      the current snapshot (market, listings)
        archive.json   append-only changelog; entry[0] is the run being reported
        [--prev]       the previous run's data.json, if one is available
Writes  nothing on disk. Creates one email in Buttondown, a DRAFT unless --send.

Standard library only, like the other two tools here: the refresh task runs on whatever
Python the desktop happens to have, so there is nothing to install.

Run:  python3 tools/send_newsletter.py --dry-run          # render, no network at all
      python3 tools/send_newsletter.py                    # create a draft
      python3 tools/send_newsletter.py --send             # create and send

Exit 0 = nothing went wrong, which includes the ordinary case of deciding not to send.
Exit 1 = something is wrong and a human should look.

Why the gates exist
-------------------
Two of them, and they are the whole point of this script.

1. SATURDAY ONLY. The site refreshes Tuesday and Saturday; the list gets one email a week.
   At two sends a week this would be ~104 emails a year about the same 74 houses, which is
   how you earn unsubscribes rather than readers.

2. ONLY IF SOMETHING HAPPENED. A new listing, a price cut, a home going pending or leaving
   the market, or a rate move of at least RATE_MOVE_PP. A quiet week sends nothing at all --
   deliberately not a "no news this week" email, which is still an email.

The day is read from the snapshot's own date, not from the clock. The run being reported is
identified by the data it produced, so a task that starts at 9 PM and finishes after midnight
still reports Saturday's run as Saturday's run.

And the ordering rule that lives outside this file: the refresh must run this only AFTER
validate_snapshot.py passes and AFTER the push succeeds. A bad commit can be reverted. A bad
email cannot.

Links
-----
Every property link is built from the stored realtor.com `mpr` id and from nothing else. A
listing without one gets no link. There is no constructed fallback anywhere in this project,
because a link that silently goes somewhere else is worse than no link.
"""

import argparse
import datetime
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request

API_URL = "https://api.buttondown.com/v1/emails"
SITE_URL = "https://melon-claw.github.io/bellevue-redmond-housing/"
REALTOR_DETAIL = "https://www.realtor.com/realestateandhomes-detail/M%s"

# A rate move smaller than this is noise, not news. 6.66 -> 6.69 is not a reason to email.
RATE_MOVE_PP = 0.10

# Saturday. datetime.date.weekday(): Monday is 0.
SEND_WEEKDAY = 5

# Non-ASCII kept as explicit escapes: some editors write literal \uXXXX into source files,
# and inside a string literal that stays a valid escape rather than turning into visible junk.
ARROW = "→"      # right arrow
MDASH = "—"      # em dash
MINUS = "−"      # true minus sign
DOT = "·"        # middle dot

# CDOM is stored with the date it was read and aged forward at render time, same as the page.
# Past this many days without re-verification the number is marked uncertain.
CDOM_STALE_DAYS = 45

# Changelog labels whose bullets a structured section can fully replace. See undisplayed_changes.
DEDUPABLE_LABELS = {"new", "drop"}


# --------------------------------------------------------------------------- rendering helpers


def money(n):
    try:
        return "$%s" % format(int(round(float(n))), ",d")
    except (TypeError, ValueError):
        return str(n)


def html_to_md(s):
    """The changelog and the read are stored as small HTML fragments for the page.

    Only a handful of tags are ever used (strong, b, em, i, and the cl-* label spans), so this
    converts those and strips the rest rather than pretending to be a general HTML parser.
    """
    if not s:
        return ""
    s = re.sub(r"<(strong|b)>(.*?)</\1>", r"**\2**", s, flags=re.S)
    s = re.sub(r"<(em|i)>(.*?)</\1>", r"*\2*", s, flags=re.S)
    s = re.sub(r'<span class="cl-[a-z]+">(.*?)</span>', r"**\1**", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def undisplayed_changes(changes, covered, universe):
    """Drop changelog bullets that the structured sections above have already said better.

    The changelog is written for the page, where it is the only account of the run. Here the
    new / cut / departed lists are rendered from the data itself, with links and details the
    prose does not carry, so repeating the prose verbatim doubles the length of the email for
    nothing.

    A bullet is dropped only when it is a pure restatement: it carries one of the cl-* labels,
    every tracked address it names is already in the matching structured section, and it names
    at least one. That last condition is what keeps the notes worth having. The reference-home
    cut, for instance, is labelled the same way but names an address that is not in the
    listings table, so it survives -- as does every unlabelled note about methodology,
    corrections or rates.

    The departure bullets (cl-off) are never dropped. The structured list can only say a home
    is no longer active; the prose is the only place that says whether it went pending, closed,
    or was genuinely withdrawn, and that distinction is the whole point of the section.
    """
    kept = []
    for raw in changes:
        m = re.match(r'<span class="cl-([a-z]+)">', raw or "")
        if not m or m.group(1) not in DEDUPABLE_LABELS:
            kept.append(raw)
            continue
        addrs = {a for a in universe if a and a in raw}
        if addrs and addrs <= covered.get(m.group(1), set()):
            continue
        kept.append(raw)
    return kept


def realtor_link(x):
    """A link only when a real property id is on file. Never construct one from the address."""
    mpr = x.get("mpr")
    if mpr is None or not re.fullmatch(r"\d+", str(mpr)):
        return None
    return REALTOR_DETAIL % mpr


def label(x):
    """Address + city, linked when we have an id for it."""
    text = "%s, %s" % (x.get("addr", "?"), x.get("city", ""))
    text = text.rstrip(", ")
    url = realtor_link(x)
    return "[%s](%s)" % (text, url) if url else text


def facts(x, today):
    """The short trailing description: beds/baths, size, catchment, days on market."""
    bits = []
    beds, baths = x.get("beds"), x.get("baths")
    if beds:
        bits.append("%sBD/%sBA" % (beds, baths) if baths else "%sBD" % beds)
    if x.get("sqft"):
        bits.append("%s sqft" % format(int(x["sqft"]), ",d"))

    # Display the catchment only where it is verified, on the same rule the page uses: a
    # resolved name that is flagged as a district mismatch is a boundary-file artefact, not
    # an assignment, and must not be asserted here either.
    if x.get("elem") and not x.get("elemFlag"):
        bits.append(x["elem"])

    d = days_on_market(x, today)
    if d:
        bits.append(d)
    return (" %s " % DOT).join(bits)


def days_on_market(x, today):
    """Cumulative days on market, aged forward from the date it was read (as the page does)."""
    cdom, read_on = x.get("cdom"), x.get("cdomDate")
    if not cdom:
        return ""
    try:
        age = (today - datetime.date.fromisoformat(read_on)).days if read_on else 0
    except ValueError:
        age = 0
    if age < 0:
        age = 0
    mark = "?" if age > CDOM_STALE_DAYS else ""
    total = cdom + age
    return "%d day%s on market%s" % (total, "" if total == 1 else "s", mark)


# --------------------------------------------------------------------------- what changed


def cuts_this_run(listings, date, prev_date):
    """Price cuts recorded by this run.

    Read from the listings themselves rather than parsed out of the changelog prose: `cutDate`
    is written when the diff spots the reduction, so the cuts belonging to this run are the
    ones dated after the previous run and no later than this one.
    """
    out = []
    for x in listings:
        if not x.get("cut") or not x.get("cutDate"):
            continue
        d = x["cutDate"]
        if (prev_date is None or d > prev_date) and d <= date:
            out.append(x)
    return sorted(out, key=lambda x: -(x.get("cut") or 0))


def diff_against_prev(listings, prev_listings):
    """New and departed listings, by address. Only available when --prev is supplied."""
    now = {x["addr"]: x for x in listings if x.get("addr")}
    was = {x["addr"]: x for x in prev_listings if x.get("addr")}
    new = [now[a] for a in now if a not in was]
    gone = [was[a] for a in was if a not in now]
    return (sorted(new, key=lambda x: x.get("price") or 0),
            sorted(gone, key=lambda x: x.get("price") or 0))


def gate(entry, prev_entry, new_count, cut_count):
    """Did enough happen to be worth an email? Returns (send, reasons, blockers)."""
    reasons, blockers = [], []
    m = entry.get("metrics")

    if m is None:
        # Without metrics there is no structured account of the run, and the changelog always
        # has at least a summary line, so falling back to "is the changelog non-empty" would
        # make the gate vacuous. Silence is the safe direction.
        blockers.append("the newest archive entry has no metrics block, so the change gate "
                        "cannot be evaluated")
        return False, reasons, blockers

    if new_count:
        reasons.append("%d new listing%s" % (new_count, "" if new_count == 1 else "s"))
    if cut_count:
        reasons.append("%d price cut%s" % (cut_count, "" if cut_count == 1 else "s"))
    if m.get("pending"):
        reasons.append("%d went pending" % m["pending"])
    if m.get("delisted"):
        reasons.append("%d left the market" % m["delisted"])

    rate, prev_rate = m.get("rate"), (prev_entry or {}).get("metrics", {}).get("rate")
    if rate is not None and prev_rate is not None:
        move = abs(float(rate) - float(prev_rate))
        if move >= RATE_MOVE_PP:
            reasons.append("the 30-yr fixed moved %.2f points to %.2f%%" % (move, rate))

    return bool(reasons), reasons, blockers


# --------------------------------------------------------------------------- the email


def subject_line(entry, new_count, cut_count):
    when = pretty_date(entry["date"])
    m = entry.get("metrics") or {}
    bits = []
    if new_count:
        bits.append("%d new" % new_count)
    if cut_count:
        bits.append("%d price cut%s" % (cut_count, "" if cut_count == 1 else "s"))
    if m.get("pending"):
        bits.append("%d pending" % m["pending"])
    if m.get("delisted"):
        bits.append("%d gone" % m["delisted"])
    tail = ", ".join(bits[:3]) if bits else "%s active listings" % m.get("active", "")
    return "Bellevue + Redmond %s %s: %s" % (DOT, when, tail)


def pretty_date(iso):
    try:
        return datetime.date.fromisoformat(iso).strftime("%b %-d")
    except (ValueError, TypeError):
        try:
            return datetime.date.fromisoformat(iso).strftime("%b %d").replace(" 0", " ")
        except (ValueError, TypeError):
            return iso


def long_date(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (ValueError, TypeError):
        return iso
    return "%s, %s %d, %d" % (d.strftime("%A"), d.strftime("%B"), d.day, d.year)


def render(data, entry, new, gone, cuts):
    date = entry["date"]
    today = datetime.date.fromisoformat(date)
    m = entry.get("metrics") or {}
    read = entry.get("read") or {}
    out = []

    out.append("*Refresh of %s %s %s active listings*" % (long_date(date), DOT, m.get("active",
                                                          len(data.get("listings") or []))))
    out.append("")
    if read.get("headline"):
        out.append("**%s**" % html_to_md(read["headline"]))
        out.append("")

    if new:
        out.append("## New this week (%d)" % len(new))
        out.append("")
        for x in new:
            out.append("- %s %s **%s** %s %s" % (label(x), MDASH, money(x.get("price")), DOT,
                                                 facts(x, today)))
        out.append("")

    if cuts:
        total = sum(x.get("cut") or 0 for x in cuts)
        out.append("## Price cuts (%d, %s off asking)" % (len(cuts), money(total)))
        out.append("")
        for x in cuts:
            before = (x.get("price") or 0) + (x.get("cut") or 0)
            out.append("- %s %s %s %s %s (%s%s) %s %s"
                       % (label(x), MDASH, money(before), ARROW, money(x.get("price")),
                          MINUS, money(x.get("cut")), DOT, facts(x, today)))
        out.append("")

    if gone:
        out.append("## Left the active list (%d)" % len(gone))
        out.append("")
        for x in gone:
            out.append("- %s %s last asking %s" % (label(x), MDASH, money(x.get("price"))))
        out.append("")
        out.append("*Pending, sold or withdrawn %s the changelog below says which.*" % MDASH)
        out.append("")

    universe = {x.get("addr") for x in (data.get("listings") or [])} | {x.get("addr") for x in gone}
    covered = {"new": {x.get("addr") for x in new},
               "drop": {x.get("addr") for x in cuts},
               "off": {x.get("addr") for x in gone}}
    changes = [html_to_md(c)
               for c in undisplayed_changes(entry.get("changes") or [], covered, universe)]
    changes = [c for c in changes if c]
    if changes:
        out.append("## What changed")
        out.append("")
        for c in changes:
            out.append("- %s" % c)
        out.append("")

    points = [html_to_md(p) for p in (read.get("points") or [])]
    points = [p for p in points if p]
    if points:
        out.append("## The read")
        out.append("")
        for p in points:
            out.append("- %s" % p)
        out.append("")
        if read.get("lean"):
            out.append("**On the numbers this week, the model leans toward %s.**"
                       % ("renting" if read["lean"] == "rent" else "buying"))
            out.append("")

    market = data.get("market") or []
    if market:
        out.append("## Market snapshot")
        out.append("")
        out.append("| | Now | Change |")
        out.append("|---|---|---|")
        for row in market:
            out.append("| %s | %s | %s |" % (row.get("lbl", ""), row.get("val", ""),
                                             row.get("delta", "")))
        out.append("")

    out.append("---")
    out.append("")
    out.append("The full dashboard %s map, filters, school comparison and the buy-vs-rent "
               "calculator %s is at [%s](%s)." % (MDASH, MDASH, SITE_URL, SITE_URL))
    out.append("")
    out.append("*Not financial, investment or real-estate advice. Listing data is third-party "
               "and can lag the market; school attendance boundaries change %s confirm any "
               "specific address with the district's own boundary tool.*" % MDASH)
    return "\n".join(out)


# --------------------------------------------------------------------------- Buttondown


def read_key(path):
    """A single bare line. Never printed, never logged, never echoed on error."""
    if not os.path.exists(path):
        sys.exit("no credentials file at %s %s create it with the Buttondown API key on one "
                 "line, mode 600, and keep it gitignored" % (path, MDASH))
    with open(path) as fh:
        key = fh.read().strip()
    if not key:
        sys.exit("%s is empty" % path)
    if "PASTE" in key.upper() or key.upper().startswith("YOUR"):
        sys.exit("%s still holds the placeholder, not a key" % path)
    if "=" in key:
        sys.exit("%s looks like KEY=value; it should be the bare key on one line" % path)
    return key


def post(key, payload, live_dangerously=False):
    body = json.dumps(payload).encode("utf-8")
    headers = {"Authorization": "Token %s" % key, "Content-Type": "application/json"}
    if live_dangerously:
        headers["X-Buttondown-Live-Dangerously"] = "true"
    req = urllib.request.Request(API_URL, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(detail or "{}")
        except ValueError:
            return exc.code, {"raw": detail}
    except urllib.error.URLError as exc:
        sys.exit("could not reach Buttondown: %s" % exc.reason)


def describe_failure(code, resp):
    detail = resp.get("detail") or resp.get("raw") or json.dumps(resp)[:400]
    return "Buttondown returned %s: %s" % (code, detail)


# --------------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description="Send the weekly Bellevue/Redmond digest.")
    ap.add_argument("--data", default="data.json")
    ap.add_argument("--archive", default="archive.json")
    ap.add_argument("--prev", default=None,
                    help="the previous run's data.json; enables the new/departed sections. "
                         "The fresh clone still holds it before you copy the new one in.")
    ap.add_argument("--credentials", default=".buttondown-credentials")
    ap.add_argument("--dry-run", action="store_true",
                    help="render and print, touch the network not at all")
    ap.add_argument("--send", action="store_true",
                    help="actually send. Without this the email is created as a draft.")
    ap.add_argument("--force", action="store_true",
                    help="ignore the Saturday and change gates")
    ap.add_argument("--confirm-first-send", action="store_true",
                    help="clear Buttondown's one-time sending confirmation for this key. Use "
                         "once, deliberately, after eyeballing a real draft in the dashboard.")
    args = ap.parse_args()

    try:
        with open(args.data) as fh:
            data = json.load(fh)
        with open(args.archive) as fh:
            archive = json.load(fh)
    except Exception as exc:
        sys.exit("could not read the snapshot: %s" % exc)

    listings = data.get("listings") or []
    entries = archive.get("entries") or []
    if not entries:
        sys.exit("archive.json has no entries, so there is no run to report")
    entry = entries[0]
    prev_entry = entries[1] if len(entries) > 1 else None
    date = entry.get("date")
    if not date:
        sys.exit("the newest archive entry has no date")

    # The digest claims to describe the current snapshot. If the newest changelog entry belongs
    # to a different run than data.json, one of the two did not get written, and emailing the
    # mismatch would put a wrong date on real numbers.
    if data.get("updated") and data["updated"] != date:
        sys.exit("data.json is stamped %s but the newest archive entry is %s %s they must be "
                 "the same run" % (data["updated"], date, MDASH))

    prev_listings = None
    if args.prev:
        try:
            with open(args.prev) as fh:
                prev_listings = (json.load(fh) or {}).get("listings") or []
        except FileNotFoundError:
            print("  no previous snapshot at %s; new/departed sections omitted" % args.prev)

    new, gone = diff_against_prev(listings, prev_listings) if prev_listings is not None else ([], [])
    cuts = cuts_this_run(listings, date, (prev_entry or {}).get("date"))
    new_count = len(new) if prev_listings is not None else ((entry.get("metrics") or {}).get("new") or 0)

    body = render(data, entry, new, gone, cuts)
    subject = subject_line(entry, new_count, len(cuts))

    # Not fatal, but worth saying out loud: the changelog and the snapshots are two independent
    # accounts of the same run, and validate_snapshot.py checks several ways they must agree.
    claimed_new = (entry.get("metrics") or {}).get("new")
    if prev_listings is not None and claimed_new is not None and claimed_new != len(new):
        print("  note: the changelog claims %d new listings, the snapshot diff finds %d"
              % (claimed_new, len(new)))

    send_ok, reasons, blockers = gate(entry, prev_entry, new_count, len(cuts))
    is_saturday = False
    try:
        is_saturday = datetime.date.fromisoformat(date).weekday() == SEND_WEEKDAY
    except ValueError:
        blockers.append("the archive date %r is not a real date" % date)

    if args.dry_run:
        print("subject: %s\n" % subject)
        print(body)
        print("\n" + "-" * 70)

    print("  run %s | %d listings | %d new | %d cuts"
          % (date, len(listings), new_count, len(cuts)))
    if blockers:
        for b in blockers:
            print("  problem: %s" % b)
        return 1
    print("  change gate: %s" % ("; ".join(reasons) if reasons else "nothing happened"))
    print("  weekly gate: %s" % ("Saturday run" if is_saturday else "not a Saturday run"))

    if args.dry_run:
        print("  dry run, nothing sent")
        return 0

    if not (is_saturday and send_ok):
        if not args.force:
            print("  no email this run%s" % ("" if is_saturday else " (site still refreshed)"))
            return 0
        print("  --force: gates overridden")

    payload = {"subject": subject, "body": body,
               "status": "about_to_send" if args.send else "draft"}
    key = read_key(args.credentials)
    code, resp = post(key, payload)

    # Buttondown deliberately refuses the first real send on a new key. Clearing it is a
    # decision, not a retry, so it needs the flag rather than happening automatically.
    if code == 400 and "confirmation" in json.dumps(resp).lower():
        if not args.confirm_first_send:
            print("  Buttondown is holding the first send on this key for confirmation.")
            print("  Re-run with --send --confirm-first-send once you have looked at a draft "
                  "in the dashboard.")
            return 1
        print("  clearing the one-time send confirmation for this key")
        code, resp = post(key, payload, live_dangerously=True)

    if code not in (200, 201):
        print("  %s" % describe_failure(code, resp))
        return 1

    print("  created %s: %s" % (payload["status"],
                                resp.get("absolute_url") or resp.get("id") or "(no id returned)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
