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

## Verified measurements and decision

- 154 screened mirrors; 144 valid survey downloads; 18 finalists all passed
  three shuffled repeat rounds. Body traffic: 1.652 GiB.
- Database medians: osbeck 55.58, dotsrc 37.79, Lysator 36.68 MiB/s.
- Firefox 86.17 MiB exploratory test: three rounds; nominal dotsrc lead.
- Nine fresh confirmation rounds: dotsrc median 88.44 versus osbeck 77.17 MiB/s,
  but mean completion 1.169 versus 1.112 seconds, and greater variability.
- Recommend osbeck, dotsrc, Lysator for database performance and observed mean
  package completion. Dotsrc first optimizes the observed package median.
- Use descriptive mean, sample SD, median, ranges and paired effect sizes.
  One host/day does not establish persistent superiority or global optimality.
- Primary report: `docs/benchmark-2026-10-23.md`; raw evidence is retained under
  `docs/evidence/`. Reproduce with `/usr/bin/python docs/analyze_results.py`.

## Verification and limits

Fourteen Python tests, ShellCheck, shfmt and Ruff passed. Bash integration
fixtures cover preview, backups, atomic application, bad lists, target/lock
symlinks and cleanup after backup failure. Stable-file preview completed.
System script byte equality and mirrorlist SHA256 were verified unchanged.
No privileged real-host installation, pacman update or application throughput
test was performed. The host already uses `ParallelDownloads = 5`.

During development an initial survey was interrupted after identifying a curl
JSON URL-identity collision; a regression test now covers the entire pipeline.
The subsequent completed data run contains all 208 validly recorded probes.
Editing the Bash wrapper while it ran was followed by an attempted duplicate
invocation, refused by output-reuse protection after the successful preview.
Do not edit a running Bash script; benchmark evidence was complete and stable
preview was checked separately. The invalid/interrupted run remains ignored in
`results/`; it was not used in the analysis.

Future work, if requested: repeat across days/address families and compare a
fixed uncached package workload with actual pacman concurrency. No additional
measurement or system changes are necessary for the current reviewable result.
