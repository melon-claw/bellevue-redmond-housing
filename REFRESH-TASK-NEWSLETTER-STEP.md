# Paste-ready: add the newsletter step to the refresh task

The refresh task is stored by the desktop app, so nothing here takes effect until you paste it
in yourself. Open the Claude desktop app → Settings → scheduled tasks → the **Tue/Sat 9 PM
refresh**, and make the two edits below.

Everything the step depends on is already committed to the repo, so a run that clones fresh
will have `tools/send_newsletter.py` waiting for it.

---

## Edit A — one line inside the existing push step

The push step already clones the repo to a temp directory. Add one line to it, **before** the
line that copies this run's `data.json` in:

```
Before copying anything in, save the clone's existing data.json as /tmp/prev-data.json.
That file is the PREVIOUS run's snapshot, which the newsletter step uses to work out
which homes are new and which have left.
```

While you are in that step, add `tools/send_newsletter.py` to the list of files it copies by
name, and add `.buttondown-credentials` to the list of things that must never appear in
`git status`.

---

## Edit B — the new final step

Paste this as the **last** step of the task, after the push:

```
FINALLY, AFTER THE PUSH HAS SUCCEEDED — send the weekly email digest.

Run, from the project folder:

    python3 tools/send_newsletter.py --send --prev /tmp/prev-data.json

Report exactly what it prints in the run summary.

Do NOT run this if the validator failed or the push did not go through. The order matters:
a bad commit can be reverted, a bad email cannot. The email is the last thing that happens,
and only on a run that already reached GitHub.

Do not add any other flags. In particular never add --force or --confirm-first-send. The
script decides on its own whether this run warrants an email, and it is meant to say no
most of the time:

  - It sends only on SATURDAY runs. Tuesday's run will call it and it will decline and
    exit 0. That is correct behaviour, not a failure — do not retry it, and do not report
    it as a problem.
  - It sends only when something actually happened: a new listing, a price cut, a home
    going pending or leaving the market, or a mortgage-rate move of at least 0.10 points.
    A quiet Saturday sends nothing at all. Also correct, also not a failure.
  - It exits 1 without sending if data.json and the newest archive.json entry carry
    different dates. If that happens, report it — it means the two files describe
    different runs and something went wrong earlier in this run.

A non-zero exit here means the email did not go out. The site is already updated and pushed
at that point, so the refresh itself succeeded; report the failure but do not roll anything
back and do not re-run the refresh.

--prev is optional. If /tmp/prev-data.json is missing, drop the flag and run it anyway —
the email loses its linked "new this week" and "left the active list" sections and the
changelog prose covers those homes instead.
```

---

## What you do not need to do

- **The one-time send confirmation is already cleared.** Buttondown holds the first send on
  each API key and returns `400 sending_requires_confirmation`; that was cleared by hand on
  2026-08-10 when the first issue went out. Automated runs will send without intervention.
- **No API key goes in the task prompt.** The script reads `.buttondown-credentials` from the
  repo root itself. That file is mode 600 and gitignored, so it exists only on this machine —
  which also means the task has to run on this machine.

## Checking it later

```
python3 tools/send_newsletter.py --dry-run
```

Prints the rendered Markdown and the two gate verdicts, and touches the network not at all.
Safe to run any time, including in the middle of the week.

Past issues, including anything a run sends: https://buttondown.com/bellevue-redmond-housing/archive/
