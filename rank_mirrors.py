#!/usr/bin/python
"""Measure Arch HTTPS mirrors serially and save a reviewable mirrorlist."""

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import zlib


# ---------------------------------------------------------------------------
# Configuration and input validation
# ---------------------------------------------------------------------------

STATUS_URL = "https://archlinux.org/mirrors/status/json/"
DB_PATH = "extra/os/x86_64/extra.db"
DEFAULT_COUNTRIES = "DK,SE,NO,FI,DE,NL,PL,BE,CZ,AT,CH,FR,GB,EE,LV,LT,ES,UA"
MIN_BYTES = 1024 * 1024
MAX_BYTES = 64 * 1024 * 1024
FIELDS = [
  "phase", "round", "position", "timestamp", "url", "country_code",
  "success", "error", "curl_exit", "http_code", "size_download",
  "time_total", "time_starttransfer", "speed_download", "remote_ip",
  "url_effective", "sha256",
]
METRIC_FIELDS = (
  "http_code", "size_download", "time_total", "time_starttransfer",
  "speed_download", "remote_ip", "url_effective",
)


def positive_int(value):
  number = int(value)
  if number <= 0:
    raise argparse.ArgumentTypeError("must be a positive integer")
  return number


def positive_float(value):
  number = float(value)
  if not math.isfinite(number) or number <= 0:
    raise argparse.ArgumentTypeError("must be a finite positive number")
  return number


def at_least_three(value):
  number = positive_int(value)
  if number < 3:
    raise argparse.ArgumentTypeError("must be at least 3")
  return number


def timestamp(value):
  parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
  if parsed.tzinfo is None:
    raise ValueError("timestamp must include its timezone")
  return parsed


def utc_now():
  return dt.datetime.now(dt.timezone.utc)


def build_parser():
  parser = argparse.ArgumentParser(
    description=(
      "Screen European Arch HTTPS mirrors, then rank repeated SERIAL "
      "extra.db downloads by median bytes/total-time. No system files change."
    ),
    epilog=(
      "Example: ./generate-mirrorlist --output-dir results/morning "
      "--rounds 5 --family auto"
    ),
  )
  parser.add_argument("--output-dir", type=Path, required=True)
  parser.add_argument("--countries", default=DEFAULT_COUNTRIES,
                      help="comma-separated ISO country codes")
  parser.add_argument("--age", type=positive_float, default=12,
                      help="maximum last-sync age in hours (default: 12)")
  parser.add_argument("--number", type=at_least_three, default=10,
                      help="number of mirrors to keep (default: 10)")
  parser.add_argument("--rounds", type=at_least_three, default=3,
                      help="separate shuffled finalist rounds (default: 3)")
  parser.add_argument("--finalists", type=positive_int, default=15,
                      help="fastest screening candidates to retest (default: 15)")
  parser.add_argument("--seed", type=int, default=20261023)
  parser.add_argument("--family", choices=("auto", "4", "6"), default="auto",
                      help="actual socket family, unlike Reflector's filter")
  parser.add_argument("--status-file", type=Path,
                      help="reuse an Arch mirror-status JSON snapshot")
  parser.add_argument("--baseline", type=Path,
                      default=Path("/etc/pacman.d/mirrorlist"),
                      help="also retest first five eligible baseline mirrors")
  parser.add_argument("--connect-timeout", type=positive_float, default=3)
  parser.add_argument("--max-time", type=positive_float, default=8)
  return parser


def curl_base(args):
  command = [
    "curl", "--disable", "--fail", "--silent", "--show-error",
    "--location", "--proto", "=https", "--proto-redir", "=https",
    "--retry", "0", "--connect-timeout", str(args.connect_timeout),
    "--max-time", str(args.max_time),
  ]
  if args.family != "auto":
    command.append("-" + args.family)
  return command


def load_status(args):
  if args.status_file:
    status = json.loads(args.status_file.read_text())
  else:
    result = subprocess.run(
      curl_base(args) + ["--max-filesize", str(8 * MIN_BYTES), STATUS_URL],
      capture_output=True, text=True, check=False,
      timeout=args.max_time + 5,
    )
    if result.returncode:
      raise ValueError("cannot retrieve mirror status: " + result.stderr.strip())
    status = json.loads(result.stdout)
  if not isinstance(status.get("urls"), list):
    raise ValueError("mirror status has no urls array")
  age = (utc_now() - timestamp(status["last_check"])).total_seconds()
  if age > 24 * 3600 or age < -300:
    raise ValueError("mirror-status last_check must be within the past 24 hours")
  return status


def eligible_mirrors(status, countries, age_hours, family, now):
  mirrors = {}
  for mirror in status["urls"]:
    if not (
      mirror.get("active") and mirror.get("protocol") == "https"
      and mirror.get("completion_pct") == 1.0
      and mirror.get("country_code") in countries
      and mirror.get("last_sync")
    ):
      continue
    url = mirror.get("url", "")
    parsed = urlsplit(url)
    if (
      parsed.scheme != "https" or not parsed.hostname
      or parsed.username or parsed.password or parsed.query or parsed.fragment
      or any(character.isspace() for character in url)
      or "$" in url
    ):
      continue
    if family != "auto" and not mirror.get("ipv" + family):
      continue
    try:
      age = (now - timestamp(mirror["last_sync"])).total_seconds() / 3600
    except (TypeError, ValueError):
      continue
    if not -5 / 60 <= age <= age_hours:
      continue
    mirrors[url.rstrip("/") + "/"] = mirror.copy()
  return [dict(mirror, url=url) for url, mirror in sorted(mirrors.items())]


def baseline_urls(path, eligible):
  if not path.is_file():
    return []
  known = {mirror["url"] for mirror in eligible}
  urls = []
  pattern = re.compile(r"^\s*Server\s*=\s*(https://\S+?)\$repo/os/\$arch\s*$")
  for line in path.read_text().splitlines():
    match = pattern.match(line)
    if match:
      url = match.group(1).rstrip("/") + "/"
      if url in known and url not in urls:
        urls.append(url)
      if len(urls) == 5:
        break
  return urls


# ---------------------------------------------------------------------------
# Download validation and repeated measurements
# ---------------------------------------------------------------------------

def validate_download(path, metrics):
  size = path.stat().st_size
  if size < MIN_BYTES or size != int(metrics.get("size_download", -1)):
    return "body is too small or differs from curl's byte count"
  if int(metrics.get("http_code", 0)) != 200:
    return "expected HTTP 200 for a complete database"
  total = float(metrics.get("time_total", 0))
  if not math.isfinite(total) or total <= 0:
    return "invalid total download time"
  # Reading to EOF checks gzip CRC and catches truncated/HTML responses.
  try:
    expanded = 0
    with gzip.open(path, "rb") as handle:
      while block := handle.read(MIN_BYTES):
        expanded += len(block)
        if expanded > 512 * MIN_BYTES:
          return "unreasonably large expanded database"
    if expanded < MIN_BYTES:
      return "expanded database is unexpectedly small"
  except (OSError, EOFError, zlib.error):
    return "body is not a complete gzip database"
  return ""


def probe(mirror, args, phase, round_number, position):
  row = dict.fromkeys(FIELDS, "")
  row.update(
    phase=phase, round=round_number, position=position,
    timestamp=utc_now().isoformat(), url=mirror["url"],
    country_code=mirror["country_code"], success=False,
  )
  with tempfile.TemporaryDirectory(prefix="arch-mirror-probe-") as directory:
    destination = Path(directory) / "extra.db"
    command = curl_base(args) + [
      "--max-filesize", str(MAX_BYTES), "--output", str(destination),
      "--write-out", "%{json}", mirror["url"] + DB_PATH,
    ]
    try:
      result = subprocess.run(
        command, capture_output=True, text=True, check=False,
        timeout=args.max_time + 5,
      )
      row["curl_exit"] = result.returncode
      try:
        metrics = json.loads(result.stdout)
      except json.JSONDecodeError:
        metrics = {}
      for field in METRIC_FIELDS:
        if field in metrics:
          row[field] = metrics[field]
      if result.returncode:
        row["error"] = result.stderr.strip()[:1000] or "curl failed"
      elif not destination.is_file():
        row["error"] = "curl did not create its output file"
      else:
        row["error"] = validate_download(destination, metrics)
        row["success"] = not row["error"]
        if row["success"]:
          with destination.open("rb") as handle:
            row["sha256"] = hashlib.file_digest(handle, "sha256").hexdigest()
    except subprocess.TimeoutExpired:
      row["curl_exit"] = "process_timeout"
      row["error"] = "curl exceeded its process deadline"
  return row


def rank_repeats(rows, mirrors, rounds):
  by_url = {mirror["url"]: mirror for mirror in mirrors}
  groups = {}
  for row in rows:
    if row["phase"] == "repeat":
      groups.setdefault(row["url"], []).append(row)
  ranked = []
  for url, group in groups.items():
    if (
      len(group) != rounds
      or {row["round"] for row in group} != set(range(1, rounds + 1))
      or not all(row["success"] for row in group)
    ):
      continue
    times = [float(row["time_total"]) for row in group]
    sizes = [int(row["size_download"]) for row in group]
    median_time = statistics.median(times)
    ranked.append({
      "url": url,
      "country_code": by_url[url]["country_code"],
      "median_seconds": median_time,
      "min_seconds": min(times),
      "max_seconds": max(times),
      "median_mib_per_second": statistics.median(
        size / elapsed / MIN_BYTES for size, elapsed in zip(sizes, times)
      ),
      "min_bytes": min(sizes),
      "max_bytes": max(sizes),
      "successful_rounds": len(group),
    })
  return sorted(
    ranked,
    key=lambda item: (-item["median_mib_per_second"], item["url"]),
  )


def write_json(path, value):
  path.write_text(json.dumps(value, indent=2) + "\n")


def write_report(output_dir, summary, ranking):
  lines = [
    "# Local Arch mirror benchmark", "",
    f"Started: {summary['started']}",
    f"Finished: {summary['finished']}",
    f"Arch status last check: {summary['status_last_check']}",
    f"Family: {summary['family']}; seed: {summary['seed']}",
    f"Countries: {summary['countries']}", "",
    f"Screened {summary['screened']} eligible HTTPS mirrors serially; "
    f"{summary['screen_successes']} succeeded. Retested "
    f"{summary['finalists']} finalists in {summary['rounds']} shuffled rounds.",
    f"Transferred {summary['downloaded_gib']:.3f} GiB of recorded bodies.", "",
    "| Rank | Country | Mirror | Median s | Min–max s | MiB/s |",
    "| ---: | :--- | :--- | ---: | :--- | ---: |",
  ]
  for index, item in enumerate(ranking, 1):
    lines.append(
      f"| {index} | {item['country_code']} | {item['url']} | "
      f"{item['median_seconds']:.3f} | {item['min_seconds']:.3f}–"
      f"{item['max_seconds']:.3f} | {item['median_mib_per_second']:.2f} |"
    )
  lines += [
    "", "## Interpretation", "",
    "Ranking uses median effective throughput: bytes divided by full "
    "transaction time including DNS, TCP/TLS, headers, and body. This differs "
    "from Reflector's body-only timing. Curl's speed_download metric is "
    "retained alongside bytes and total time in raw.csv. Normalizing by size "
    "avoids favoring smaller database versions. "
    "Screening samples "
    "are excluded from final medians. Every retained finalist must pass "
    "every repeat. First eligible baseline mirrors are included among "
    "finalists when their screening download succeeds.", "",
    "These observations describe this host's current network path, VPN/proxy "
    "settings, and time window. They do not prove the globally fastest mirror. "
    "One screening sample can miss a temporarily slow contender. Shuffling "
    "reduces order effects but does not eliminate background traffic or "
    "time-of-day effects. Use multiple sessions and sustained package "
    "downloads before claiming persistent superiority.", "",
    "The object is extra/os/x86_64/extra.db, a compressed repository database. "
    "It may change during the run, and mirrors can serve slightly different "
    "versions. Raw byte counts and SHA256 hashes are retained for assessing "
    "this limitation. "
    "This does not simulate pacman's five concurrent package streams, "
    "connection reuse, or much larger packages. No package databases were "
    "installed or refreshed on this computer.", "",
    "Official status completion is a health filter measured by Arch, not a "
    "download-speed measurement from Copenhagen. Geographic country is only "
    "a search prior; measured times determine the order.", "",
    "Sources: [Arch mirror status](https://archlinux.org/mirrors/status/), "
    "[Reflector documentation](https://xyne.dev/projects/reflector/).", "",
  ]
  (output_dir / "report.md").write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Main: stage artifacts only; the Bash wrapper controls installation
# ---------------------------------------------------------------------------

def run(args):
  if not shutil.which("curl"):
    raise ValueError("curl is required; install it with pacman -S curl")
  if args.finalists < args.number:
    raise ValueError("--finalists must be at least --number")
  countries = {part.strip().upper() for part in args.countries.split(",")}
  if not countries or any(not re.fullmatch(r"[A-Z]{2}", c) for c in countries):
    raise ValueError("--countries must contain comma-separated ISO codes")
  args.output_dir.mkdir(parents=True, exist_ok=True)
  artifacts = (
    "raw.csv", "status.json", "candidates.json", "summary.json", "ranking.csv",
    "mirrorlist", "report.md",
  )
  if any((args.output_dir / name).exists() for name in artifacts):
    raise ValueError("output directory already contains benchmark artifacts")
  started = utc_now().isoformat()
  status = load_status(args)
  unknown = countries - {
    mirror.get("country_code") for mirror in status["urls"]
  }
  if unknown:
    raise ValueError("unknown country codes: " + ",".join(sorted(unknown)))
  mirrors = eligible_mirrors(status, countries, args.age, args.family, utc_now())
  if len(mirrors) < args.number:
    raise ValueError("too few eligible mirrors; widen --countries or --age")
  baseline = baseline_urls(args.baseline, mirrors)
  write_json(args.output_dir / "status.json", status)
  write_json(args.output_dir / "candidates.json", mirrors)
  by_url = {mirror["url"]: mirror for mirror in mirrors}
  generator = random.Random(args.seed)
  rows = []
  with (args.output_dir / "raw.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=FIELDS)
    writer.writeheader()

    def measure(pool, phase, round_number):
      ordered = list(pool)
      generator.shuffle(ordered)
      measured = []
      for index, mirror in enumerate(ordered, 1):
        row = probe(mirror, args, phase, round_number, index)
        writer.writerow(row)
        handle.flush()
        rows.append(row)
        measured.append(row)
        result = (
          f"{float(row['time_total']):.3f}s"
          if row["success"] else "FAILED: " + row["error"]
        )
        print(
          f"{phase} {round_number} [{index}/{len(ordered)}] "
          f"{mirror['country_code']} {mirror['url']} {result}",
          file=sys.stderr, flush=True,
        )
      return measured

    screened = measure(mirrors, "screen", 0)
    successful = sorted(
      (row for row in screened if row["success"]),
      key=lambda row: -int(row["size_download"]) / float(row["time_total"]),
    )
    finalists = [by_url[row["url"]] for row in successful[:args.finalists]]
    successful_urls = {row["url"] for row in successful}
    finalist_urls = {mirror["url"] for mirror in finalists}
    for url in baseline:
      if url in successful_urls and url not in finalist_urls:
        finalists.append(by_url[url])
        finalist_urls.add(url)
    if len(finalists) < args.number:
      raise ValueError("too few screening downloads succeeded; see raw.csv")
    for round_number in range(1, args.rounds + 1):
      measure(finalists, "repeat", round_number)

  ranking = rank_repeats(rows, mirrors, args.rounds)
  summary = {
    "started": started, "finished": utc_now().isoformat(),
    "status_last_check": status["last_check"],
    "countries": ",".join(sorted(countries)), "age_hours": args.age,
    "family": args.family, "seed": args.seed, "rounds": args.rounds,
    "number": args.number, "screened": len(screened),
    "screen_successes": len(successful), "finalists": len(finalists),
    "repeat_successes": len(ranking), "baseline_urls": baseline,
    "baseline_file": str(args.baseline), "database": DB_PATH,
    "connect_timeout": args.connect_timeout, "max_time": args.max_time,
    "downloaded_gib": sum(
      int(row["size_download"] or 0) for row in rows
    ) / (1024 ** 3),
    "ranking": ranking,
  }
  write_json(args.output_dir / "summary.json", summary)
  with (args.output_dir / "ranking.csv").open("w", newline="") as handle:
    if ranking:
      writer = csv.DictWriter(handle, fieldnames=list(ranking[0]))
      writer.writeheader()
      writer.writerows(ranking)
  write_report(args.output_dir, summary, ranking)
  if len(ranking) < args.number:
    raise ValueError(
      "too few mirrors passed every repeat; no mirrorlist written; see report.md"
    )
  lines = [
    "# Generated by generate-mirrorlist: median bytes/total-time, serial.",
    f"# Measured: {summary['finished']}",
    f"# Family: {args.family}; rounds: {args.rounds}; object: {DB_PATH}",
    "# See report.md and raw.csv in this run directory for evidence.", "",
  ]
  lines.extend(
    "Server = " + item["url"] + "$repo/os/$arch"
    for item in ranking[:args.number]
  )
  (args.output_dir / "mirrorlist").write_text("\n".join(lines) + "\n")
  print(args.output_dir / "mirrorlist")


def main():
  parser = build_parser()
  args = parser.parse_args()
  try:
    run(args)
  except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
    print(f"generate-mirrorlist: {error}", file=sys.stderr)
    return 1
  except KeyboardInterrupt:
    print(
      "generate-mirrorlist: interrupted; partial raw.csv retained",
      file=sys.stderr,
    )
    return 130
  return 0


if __name__ == "__main__":
  sys.exit(main())
