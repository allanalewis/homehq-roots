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
- Updates `status.json` with the latest successful check date and counts.
- Leaves the published files unchanged when fetching, parsing or validation fails.

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
