# Project context

## Objective and scope

Measure local Arch Linux mirror performance for a user in Copenhagen, then
prepare a defensible mirrorlist. System changes require an explicit `--apply`.
The installed `/usr/local/bin/generate-mirrorlist` is preserved.

## Decisions

- Use broad European ISO country codes and current official Arch mirror data.
- Require active HTTPS mirrors with 100% recent status-check completion.
- Keep the original 12-hour last-sync limit; avoid arbitrary latest/score caps.
- Screen candidates serially; retest finalists in separate shuffled rounds.
- Rank median effective throughput including connection setup; record failures.
- Preserve baseline leaders in finalist comparisons when eligible.
- Preview by default; apply with a backup, lock and same-directory rename.

## Verified source findings

Installed Reflector 2023-5 uses `/usr/lib/python3.14/site-packages/Reflector.py`.
`--number` truncates after rating; `--latest` and `--score` prefilter. Rate failures
remain eligible at zero rate. HTTP timing excludes connection setup. `--ipv4`
only filters advertised support. Status completion defaults to 100 already.
Unquoted `United Kingdom` and misspelled `Ukrain` exclude intended countries.

## Verification and next actions

Live measurements and offline checks are in progress. Record the final results,
commands and limits here before finishing. No real mirrorlist installation or
pacman update has been requested.
