# generate-mirrorlist

Arch mirror ranking measured from the connection of a user in Copenhagen.
The original script is preserved in
[docs/original-generate-mirrorlist.sh](docs/original-generate-mirrorlist.sh).

The objective is fast package downloads. Faster execution of the ranking script
is a separate objective: concurrent speed tests finish sooner but can interfere
with each other. This implementation measures mirrors one at a time and keeps
the raw evidence.

## Measured recommendation

The [23 October benchmark](docs/benchmark-2026-10-23.md) screened 154 mirrors,
retested 18 finalists, then compared the strongest three using full 86.17 MiB
Firefox downloads. The recommended general order is **osbeck, dotsrc, Lysator**.
Your current first mirror was already osbeck; no general speedup over it has
been established.

In nine package confirmation rounds, dotsrc had a 14.6% higher median throughput
but a 5.1% longer mean completion time and greater variability. Osbeck also won
the database test. Choosing dotsrc first is reasonable if median throughput of
large packages is the specific objective. The report includes mean, sample SD,
median, ranges, effect sizes and raw evidence; it makes no significance claim.

## Brief report

The results are also available as a concise
[Markdown summary](docs/mirrorlist-summary.md) and a
[one-page PDF](docs/mirrorlist-summary.pdf). Both are generated from the saved
CSV measurements using [R Markdown](docs/mirrorlist-summary.Rmd).

```bash
Rscript scripts/render-report.R
# Or regenerate only the Markdown version:
Rscript scripts/render-report.R --markdown-only
```

Rendering requires R packages `rmarkdown`, `knitr` and `jsonlite`, plus Pandoc.
The PDF additionally uses XeLaTeX and Noto Serif. Its settings are A4, 12-point
text, 1.5 cm margins and Tango syntax highlighting. The render command reads
saved data only; it performs no network requests or system changes.

## Use

Requirements on Arch Linux: Bash, Python 3, curl, GNU coreutils and util-linux
(`flock`). These are already available on the development host. To install
missing dependencies:

```bash
sudo pacman -S --needed bash python curl coreutils util-linux
cd ~/my_repos/generate-mirrorlist
./generate-mirrorlist --help
./generate-mirrorlist --plan
./generate-mirrorlist --output-dir ./results/evening
```

The last command performs real downloads and prints a preview; it does not write
to `/etc`. Expect several minutes and roughly 1–3 GiB depending on the candidate
count and database size. Avoid other heavy network use during measurement.

Review `report.md`, `ranking.csv` and `mirrorlist` in the run directory. Apply a
reviewed result explicitly, without downloading the survey again:

```bash
./generate-mirrorlist --from ./results/evening/mirrorlist --apply
```

Applying creates a timestamped backup beside `/etc/pacman.d/mirrorlist`, stages
and validates the replacement in that directory, then renames it atomically.
An advisory lock serializes this tool's writes; other mirrorlist tools do not
necessarily honor it. Root access is requested only for applying to a protected
destination. Neither pacman nor the installed `/usr/local/bin/generate-mirrorlist`
is changed automatically. Run this repository's script by its explicit path.

## What changes from the original

| Original behavior | Proposed behavior and reason |
| --- | --- |
| `United Kingdom` is unquoted; `Ukrain` is misspelled | ISO codes avoid both silent country-selection errors. |
| Eight simultaneous downloads | Serial downloads avoid candidates competing for local bandwidth. |
| One throughput sample per mirror | A survey followed by three shuffled repeat rounds for finalists. |
| Body-only timing in installed Reflector | Bytes divided by total transaction time includes DNS, TCP/TLS and response setup. |
| 35 entries | Ten verified entries; the first entries determine normal operation, later entries provide fallback. |
| Failed speed tests remain at the bottom | A finalist must pass every repeat; insufficient results abort generation. |
| Direct write to `/etc` | Preview, validation, backup and atomic replacement on explicit apply. |

The broader starting pool is Denmark, Sweden, Norway, Finland, Germany, the
Netherlands, Poland, Belgium, Czechia, Austria, Switzerland, France, the United
Kingdom, Estonia, Latvia, Lithuania, Spain and Ukraine. Country order does not
affect the final ranking. Routing and peering can outweigh geographic distance.
This is a search pool, not proof that a European mirror always beats every
mirror elsewhere in the world.

The health criteria remain active HTTPS, 100% status-check completion and a
last synchronization within 12 hours. Reflector already defaults to 100%
completion; making that explicit is not an additional improvement. `--number`
is applied **after** rating in installed Reflector. `--latest` and `--score`
reduce the candidates before rating, but can discard a fast local mirror.
This tool surveys every candidate meeting its health/country filters.

## Evidence and interpretation

1. Save the official mirror-status snapshot and eligible candidate list.
2. Shuffle and download each candidate's full `extra.db` serially once.
3. Take the 15 strongest survey candidates, adding the first five eligible
   current baseline mirrors when their survey downloads succeed.
4. Download every finalist in three separate shuffled rounds. Keep survey
   samples out of the final ranking to reduce selection optimism.
5. Rank by median effective MiB/s (`bytes / time_total / 2^20`). Require all
   repeat downloads to succeed and retain the first ten mirrors.

The minimum is three rounds and three retained mirrors. Increase repeat counts
for a more stable descriptive ranking:

```bash
./generate-mirrorlist --rounds 5 --output-dir ./results/morning
./generate-mirrorlist --rounds 5 --output-dir ./results/another-evening
```

The output includes `raw.csv` (one row per transfer, including failures),
`status.json`, `candidates.json`, `summary.json`, `ranking.csv`, `report.md` and
the proposed `mirrorlist`. Raw data contain timestamps, transfer sizes, complete
transaction times, first-byte times, curl metrics, addresses and SHA256 hashes.
Database gzip integrity and actual received size are checked after each probe.
The temporary payload is then removed. Run directories are Git-ignored.

Three rounds from one connection are correlated observations. Small differences
between medians do not establish a statistically significant or persistent
winner. Screening once can miss a temporarily slow candidate. Mirror database
versions can differ; bytes/time normalizes size approximately, and recorded
hashes expose version changes. This is a database download benchmark, not a
proof of sustained throughput for large package downloads.

For a stronger deployment decision, repeat at different times and compare a
common large package on the strongest mirrors:

```bash
/usr/bin/python verify_package.py --run-dir ./results/evening \
  --output-dir ./results/evening-package
```

This optional check retrieves current Firefox package metadata from Arch and
downloads that exact package three times from each of the leading three mirrors
and the first baseline mirror. It keeps a separate report and raw CSV. Full
file size and a common SHA256 are required before comparing rates. This checks
content consistency; it does not verify the package signature. Temporary package
files are removed; nothing is installed. The package check does not rewrite the
database-ranked mirrorlist. Inspect both reports when choosing the first mirror.

A fixed uncached set of packages with pacman's actual parallelism would provide
a stronger application-level comparison. The current host already has
`ParallelDownloads = 5`; that setting was inspected and left as configured.
Neither application-level tests nor any package installation is implied by
the database measurements.

### IPv4 and IPv6

Default `--family auto` follows curl's normal address selection. Use `--family 4`
or `--family 6` for an actual family-specific survey. Reflector's `--ipv4`
option only filters mirrors advertising support; it does not force IPv4 sockets.
A mirrorlist URL does not force pacman to use the family used during testing.
VPN and proxy settings also affect which network path is measured.

## Smaller Reflector-only change

If retaining a short Reflector wrapper is preferable, this is a reasonable
starting command to benchmark from this connection:

```bash
reflector --country DK,SE,NO,FI,DE,NL,PL,BE,CZ,AT,CH,FR,GB,EE,LV,LT,ES,UA \
  --age 12 --protocol https --completion-percent 100 \
  --sort rate --number 10 --threads 1 \
  --connection-timeout 3 --download-timeout 8 \
  --cache-timeout 300 --save "$HOME/mirrorlist.reflector-preview"
```

This still has Reflector's single sample, body-only timing and zero-rate fallback
behavior; review the logs and output. The status cache does not cache speed
measurements. Neither timeouts nor ten fallback entries have been proven optimal
for this connection; they are configurable operational defaults.

## Checks

```bash
shellcheck generate-mirrorlist tests/test_apply.sh
shfmt -d -i 2 -ci generate-mirrorlist tests/test_apply.sh
ruff check rank_mirrors.py verify_package.py tests docs/analyze_results.py
/usr/bin/python -m unittest discover -s tests -v
bash tests/test_apply.sh
```

The archived original is not linted as new code. These checks cover validation,
ranking and fixture application; real root installation remains a separate
operation. Python follows the requested two-space indentation; no whole-project
Black reformat is configured.

## Primary references

- [Arch Mirror Status](https://archlinux.org/mirrors/status/): completion,
  synchronization delay and server-side measurements.
- [Reflector upstream documentation](https://xyne.dev/projects/reflector/):
  country codes, filtering, caching and concurrent-test limitations.
- [pacman.conf manual](https://man.archlinux.org/man/pacman.conf.5.en):
  mirror configuration and concurrent download streams.

The local Reflector 2023-5 source was also inspected at
`/usr/lib/python3.14/site-packages/Reflector.py`.
