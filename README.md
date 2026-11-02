# Home HQ roots catalog

Public content-only feed for the Home HQ word-root widget. No app code, private
calendar, device details or credentials are stored here.

Feed: https://raw.githubusercontent.com/allanalewis/homehq-roots/main/roots-pack.json

## What happens automatically

GitHub Actions checks Merriam-Webster's daily-word RSS every hour at minute 17 UTC
(47 minutes past each hour in India), and after approved-content changes.
GitHub schedules can be delayed. The app fetches independently once an hour.

- Validates the approved catalog.
- Publishes changes to `roots-pack.json`, incrementing its version only when root
  content changes.
- Adds unmatched daily words and their source URLs to `review-queue.json`.
- Updates `status.json` with attempt/success timestamps, feed health and counts.
- Preserves prior queue data on source failure while still publishing reviewed
  catalog changes. Invalid approved catalogs stop publication.

**The workflow does not invent roots or automatically approve new etymologies.**
The initial catalog has 41 entries. Exact reviewed word mappings are intentionally
not exhaustive. Some daily words have no useful Greek/Latin root. Unmatched words
remain an explicit empty state in the app until a reviewed match is published.
The review queue contains source word titles, not approved widget content.

## Add or correct a root

1. Read `review-queue.json` and verify the word's etymology with an authoritative
   dictionary. Do not match letter sequences or infer a root from spelling.
2. Edit `approved-roots.json`: add the exact word to the correct entry's `words`,
   or add a new entry with ID, form, language, kind, meaning, HTTPS source and two
   verified examples. Review all text for family suitability.
3. Run `python3 -m unittest discover -s scripts -p 'test_*.py'`.
4. Commit or merge the reviewed change. Actions regenerates the published feed;
   do not manually change its version or edit the generated file.
5. Check the Actions run and the public feed. The app retains its last good cache
   if the internet is unavailable or a catalog is invalid.

The review workflow is a human process, not an enforced multi-reviewer gate.
Only trusted maintainers should have write access. No external AI API or secret
is needed. A fresh successful check does not mean that new roots were approved.

Use the Actions tab's **Run workflow** button for an immediate check. Check failed
runs there; GitHub's inactivity rules can disable scheduled workflows on public
repositories after 60 days of repository inactivity. Re-enable if needed.

## Attribution

Original concise reference entries use Peter Smith (2016), University of Victoria,
*Greek and Latin Roots*, [Part I](https://pressbooks.bccampus.ca/greeklatinroots/) and
[Part II](https://pressbooks.bccampus.ca/greeklatinroots2/), under CC BY 4.0.
Each entry retains its source. The parāre entry references the American Heritage
Dictionary entry for disparate. RSS supplies word titles and source links only;
its dictionary definitions and articles are not republished.

Catalog contributions are offered under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Reliability and review workflow

The publisher now separates source health from approved publication. A daily-word
feed outage does not block a reviewed catalog correction. Existing queue entries
are retained, `status.json` records the failed attempt and last successful fetch,
and the Actions run fails visibly *after* committing approved publication/status.
A feed more than two UTC days old is reported as stale. Fetches use bounded reads,
timeouts, three attempts and reject redirects. No definitions are generated.

`primary` in `approved-roots.json` explicitly selects one root for words with
multiple valid matches. For example, `telescope` has both tele and scope; selecting
tele is a display choice, not a claim that scope is unrelated. These choices
preserve the original display. The publisher rejects missing or invalid choices.

To resolve a word without adding a root, add an entry to `review-decisions.json`:

```json
{
  "word": "the exact word",
  "status": "no-suitable-root",
  "reason": "Explain the dictionary evidence and why no suitable root is shown.",
  "source": "https://dictionary.example/entry",
  "reviewer": "Your name or GitHub handle",
  "reviewed_on": "2026-11-02"
}
```

Use `excluded` for content deliberately kept off the family display. Do not copy
the illustrative entry literally. Decisions need actual source review. A word
cannot be both mapped and resolved without a root. Removing a decision allows it
to re-enter the queue on a future feed appearance. Decisions are review records;
they do not publish potentially unsuitable text to the app.

Run both before merging:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/update.py --validate-only
```

Queue records are not silently truncated, and older RSS appearances cannot replace
newer dates. Feed order is not assumed. Hourly status uses full UTC timestamps.
The workflow retries a rejected push by regenerating from the latest main branch
in its disposable runner; it never force-pushes. All generated files ship in one
commit. It also reports feed health and pending-review counts in its job summary.

CODEOWNERS and the PR checklist request source review; they do **not** enforce
branch protection. Maintainers can still bypass the human process. This repository
does not claim automated linguistic verification or complete daily-word coverage.
