#!/usr/bin/python
"""Reproduce the descriptive analysis of the saved Copenhagen benchmark."""

import argparse
import csv
import json
from pathlib import Path
import statistics as stats


OSBECK = "https://mirror.osbeck.com/archlinux/"
DOTSRC = "https://mirrors.dotsrc.org/archlinux/"
LYSATOR = "https://ftp.lysator.liu.se/pub/archlinux/"
MIRRORS = [OSBECK, DOTSRC, LYSATOR]


def load_rows(directory, phase):
  with (directory / "raw.csv").open() as handle:
    return [
      row for row in csv.DictReader(handle)
      if row["phase"] == phase and row["success"] == "True"
    ]


def rate(row):
  return int(row["size_download"]) / float(row["time_total"]) / 2**20


def describe(rows, url):
  selected = [row for row in rows if row["url"] == url]
  rates = [rate(row) for row in selected]
  times = [float(row["time_total"]) for row in selected]
  return {
    "n": len(rates), "median_rate": stats.median(rates),
    "mean_rate": stats.mean(rates), "sd_rate": stats.stdev(rates),
    "median_time": stats.median(times), "mean_time": stats.mean(times),
    "min_rate": min(rates), "max_rate": max(rates),
  }


def table(rows):
  lines = [
    "| Mirror | n | Median MiB/s | Mean ± SD MiB/s | Range MiB/s | "
    "Median s | Mean s |",
    "| :--- | ---: | ---: | :--- | :--- | ---: | ---: |",
  ]
  for url in MIRRORS:
    d = describe(rows, url)
    name = url.split("/")[2]
    lines.append(
      f"| {name} | {d['n']} | {d['median_rate']:.2f} | "
      f"{d['mean_rate']:.2f} ± {d['sd_rate']:.2f} | "
      f"{d['min_rate']:.2f}–{d['max_rate']:.2f} | "
      f"{d['median_time']:.3f} | {d['mean_time']:.3f} |"
    )
  return lines


def analyze(evidence):
  database = load_rows(evidence / "database", "repeat")
  exploratory = load_rows(evidence / "package-exploratory", "package")
  confirm = load_rows(evidence / "package-confirm", "package")
  metadata = json.loads((evidence / "database/summary.json").read_text())
  package = json.loads((evidence / "package-confirm/summary.json").read_text())
  a, b = describe(confirm, DOTSRC), describe(confirm, OSBECK)
  by_round = {
    url: {int(row["round"]): rate(row) for row in confirm if row["url"] == url}
    for url in (DOTSRC, OSBECK)
  }
  paired = [
    100 * (by_round[DOTSRC][number] / by_round[OSBECK][number] - 1)
    for number in sorted(by_round[DOTSRC])
  ]
  lines = [
    "# Copenhagen mirror benchmark, 23 October 2026", "",
    "Recommendation: retain **osbeck first, dotsrc second, Lysator third** "
    "for a general-purpose list. Osbeck led the database workload and had "
    "lower package variability and mean completion time. If the objective "
    "is specifically median throughput of larger packages, dotsrc is the "
    "nominal leader; swapping the first two entries expresses that choice. "
    "These data do not identify one universally fastest mirror.", "",
    "## Measurements", "",
    f"The survey screened {metadata['screened']} eligible European HTTPS "
    f"mirrors; {metadata['screen_successes']} completed valid downloads "
    f"within the configured timeouts. All {metadata['finalists']} finalists "
    "passed three separate shuffled repeat rounds. Screening samples were "
    "excluded from final estimates. The address family was auto.", "",
    "The live host was confirmed as Arch Linux x86_64. Raw evidence is "
    "stored alongside this report. Timings include connection setup; rates "
    "are bytes/time_total in binary MiB/s. SD is sample SD (denominator n−1), "
    "describing variation across transfers within this session.", "",
    "### Database: approximately 8.4 MiB, three repeat rounds", "",
  ]
  lines += table(database)
  lines += [
    "", "### Exploratory Firefox check: three rounds", "",
  ]
  lines += table(exploratory)
  lines += [
    "", "### Longer Firefox confirmation: nine fresh rounds", "",
    f"The exact file `{package['filename']}` contained "
    f"{package['package_bytes']:,} bytes "
    f"({package['package_bytes'] / 2**20:.2f} MiB). "
    "Every successful package payload in both runs had the same SHA256. "
    "The two runs remain separate rather than pooling a follow-up "
    "chosen after inspecting the exploratory results.", "",
  ]
  lines += table(confirm)
  lines += [
    "", "## Practical effect sizes", "",
    f"Dotsrc's ratio of median package rates was "
    f"{a['median_rate'] / b['median_rate']:.3f}: "
    f"{100 * (a['median_rate'] / b['median_rate'] - 1):.1f}% higher "
    "than osbeck. Its median transfer saved "
    f"{b['median_time'] - a['median_time']:.3f} seconds "
    f"({100 * (1 - a['median_time'] / b['median_time']):.1f}% less time). "
    f"Its mean transfer instead took "
    f"{a['mean_time'] - b['mean_time']:.3f} seconds longer "
    f"({100 * (a['mean_time'] / b['mean_time'] - 1):.1f}%), "
    "because of its slower tail.", "",
    f"Dotsrc won {sum(value > 0 for value in paired)}/{len(paired)} "
    "round comparisons. The median of the round-paired throughput "
    f"differences was {stats.median(paired):+.1f}%, with range "
    f"{min(paired):+.1f}% to {max(paired):+.1f}%. This is a different "
    "quantity from the ratio of marginal medians above; neither is "
    "presented as a whole-upgrade speedup.", "",
    "Per-round dotsrc throughput differences relative to osbeck (%): "
    + ", ".join(f"{value:+.1f}" for value in paired) + ".", "",
    "## Why descriptive statistics", "",
    "The experimental observations are serial transfers blocked by shuffled "
    "round, on one host, network path and day. A round is not a new ISP or "
    "an independent day. Repeating downloads estimates within-session "
    "variation; it does not supply independent evidence of long-term "
    "superiority. No p-values, SEM or 95% confidence claims are used to "
    "select the order. Mean rate and mean completion time also need not "
    "rank mirrors identically: taking a reciprocal is nonlinear.", "",
    "The large-package test considered only the database top three, so a "
    "mirror with slow setup but exceptional sustained throughput may have "
    "been missed. Neither IPv4/IPv6 alternatives, other times of day, nor "
    "pacman's five concurrent downloads were compared. No package was "
    "installed, no pacman database was refreshed, and no system mirrorlist "
    "was applied. Signature authenticity was not tested; SHA256 equality "
    "checks only payload consistency.", "",
    "## Evidence and reproduction", "",
    "- [Database raw data](evidence/database/raw.csv), "
    "[summary](evidence/database/summary.json), "
    "[proposed list](evidence/database/mirrorlist)",
    "- [Exploratory package raw data](evidence/package-exploratory/raw.csv)",
    "- [Confirmation package raw data](evidence/package-confirm/raw.csv), "
    "[summary](evidence/package-confirm/summary.json)",
    "- [Official mirror-status snapshot](mirror-status-20261023.json)",
    "- Recreate this report: `/usr/bin/python docs/analyze_results.py`.", "",
    "Primary definitions: [Arch Mirror Status]"
    "(https://archlinux.org/mirrors/status/), "
    "[Reflector documentation](https://xyne.dev/projects/reflector/).", "",
  ]
  return "\n".join(lines)


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--evidence", type=Path,
                      default=Path(__file__).parent / "evidence")
  parser.add_argument("--output", type=Path,
                      default=Path(__file__).parent / "benchmark-2026-10-23.md")
  args = parser.parse_args()
  args.output.write_text(analyze(args.evidence))
  print(args.output)


if __name__ == "__main__":
  main()
