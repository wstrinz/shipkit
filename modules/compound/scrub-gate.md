# Scrub gate: before a personal learning leaves the ship

Every compound learning carries `scope: employer | personal` ([compound.md](compound.md) →
"Scope"). A `personal` doc still lives in the ship's data ([DATA.md](../../DATA.md)). The scrub
gate is the step that has to pass **before** a `personal` doc is copied anywhere outside that
data, whether that's a personal repo, a blog post, a gist, a talk or a pull request to a
public kit. `employer` docs don't leave the employer; a team repo the employer owns, such as
the compound share lane, is as far as they go.

The Captain publishes; an agent may draft the scrubbed copy and run the sweep, but never
publishes unattended.

## Whose is it?

*This is not legal advice. Your employment agreement and your employer's policies decide what
you may keep or publish, and they override this list. If they're unclear, ask before
publishing, not after.*

- **The employer's:** tickets, logs, the queue, `state/`, service and system docs, incident
  data, anything naming customers, colleagues or internal systems, and lessons that only make
  sense alongside the employer's code or infrastructure.
- **The person's:** the kit itself, your working-style overlay (`mate.local.md`), and generic
  lessons about tools, agents and working practice that would hold at any employer.

When a doc is both, the generic lesson can be rewritten as a new `personal` doc that
contains none of the employer's specifics. The original stays `employer`.

## Checklist

Work on a **copy** of the doc. Don't edit the original in place.

1. **Scope is right.** It's tagged `personal`, and the lesson still holds at a different
   employer. If it doesn't, stop here.
2. **Names are gone:** the employer, customers, colleagues, vendors under NDA, product
   codenames, internal team names.
3. **Systems are gone:** hostnames, internal URLs, IPs, account, tenant and customer ids,
   repo names and paths, ticket keys, channel names.
4. **Secrets are gone:** tokens, keys, passwords and connection strings, even expired ones.
5. **Numbers are gone or made generic:** volumes, revenue, customer counts, incident dates
   and durations.
6. **Provenance is cut.** Drop the `source:` line and every link into the ship's data
   (`logs/`, `projects/`, tickets) or into internal tools.
7. **Code is rewritten, not copied.** Snippets are minimal generic examples, not excerpts of
   the employer's code.
8. **The sweep below is clean.** Every hit is fixed or written down as a deliberate keep.
9. **A fresh read.** Read the whole scrubbed copy start to finish as an outsider would. A
   second human reader is better still.

## The sweep

Keep your own deny-list in the data root, for example `<data-root>/scrub-terms.txt`. Put one
term per line: the employer's name and domains, customer names, product codenames,
colleagues, internal hostnames and ticket-key prefixes. Leave no blank lines, because a blank
line matches everything. The list names the employer, so it never travels with what you
publish.

Run both from the directory holding the scrubbed copy; `<files>` is that copy.

```
# 1. Your terms (fixed strings, case-insensitive).
rg -n -i -F -f <data-root>/scrub-terms.txt <files>

# 2. Generic leaks. Review every hit; URLs and ticket-key matches need judgment.
rg -n \
  -e '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' \
  -e '\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b' \
  -e 'https?://[^\s)>]+' \
  -e '(?i:api[_-]?key|secret|token|passw(?:or)?d|bearer)\s*[:=]' \
  -e 'AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-|sk-[A-Za-z0-9]{20,}' \
  -e '-----BEGIN [A-Z ]*PRIVATE KEY' \
  -e '/(?:Users|home)/[^/\s]+' \
  -e '\b[A-Z][A-Z0-9]+-[0-9]+\b' \
  -e '\b(?:logs|projects|inbox|state)/' \
  <files>
```

A clean pass prints nothing (`rg` exits 1). **An empty result proves nothing until you've seen
the sweep find something**, so run this positive control once per session. Every term matches
its own line, so the two numbers it prints must be equal:

```
rg -c -i -F -f <data-root>/scrub-terms.txt <data-root>/scrub-terms.txt
wc -l < <data-root>/scrub-terms.txt
```

If the `rg` count is lower, or it prints nothing, fix the terms file or the path before you
trust a clean sweep.
