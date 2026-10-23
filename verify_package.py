#!/usr/bin/python
"""Validate a mirror ranking using one identical, larger Arch package."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

import rank_mirrors as engine


# ---------------------------------------------------------------------------
# Package metadata and transfer validation
# ---------------------------------------------------------------------------

PACKAGE_API = "https://archlinux.org/packages/extra/x86_64/firefox/json/"
MAX_BYTES = 256 * 1024 * 1024
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def validate_package(path, metrics, expected_size):
  size = path.stat().st_size
  if size != expected_size or size != int(metrics.get("size_download", -1)):
    return "body size differs from package metadata or curl's byte count"
  if int(metrics.get("http_code", 0)) != 200:
    return "expected HTTP 200 for the full package"
  total = float(metrics.get("time_total", 0))
  if not math.isfinite(total) or total <= 0:
    return "invalid total transfer time"
  with path.open("rb") as handle:
    if handle.read(4) != ZSTD_MAGIC:
      return "package lacks the expected Zstandard magic"
  return ""


def package_probe(url, filename, expected_size, args, round_number, position):
  row = dict.fromkeys(engine.FIELDS, "")
  row.update(
    phase="package", round=round_number, position=position,
    timestamp=engine.utc_now().isoformat(), url=url, success=False,
  )
  with tempfile.TemporaryDirectory(prefix="arch-package-probe-") as directory:
    path = Path(directory) / "package.pkg.tar.zst"
    command = engine.curl_base(args) + [
      "--max-filesize", str(MAX_BYTES), "--output", str(path),
      "--write-out", "%{json}", url + "extra/os/x86_64/" + filename,
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
      for field in engine.METRIC_FIELDS:
        if field in metrics:
          row[field] = metrics[field]
      if result.returncode:
        row["error"] = result.stderr.strip()[:1000] or "curl failed"
      elif not path.is_file():
        row["error"] = "curl did not create its output file"
      else:
        row["error"] = validate_package(path, metrics, expected_size)
        row["success"] = not row["error"]
        if row["success"]:
          with path.open("rb") as handle:
            row["sha256"] = hashlib.file_digest(handle, "sha256").hexdigest()
    except subprocess.TimeoutExpired:
      row["curl_exit"] = "process_timeout"
      row["error"] = "curl exceeded its process deadline"
  return row


def package_metadata(args):
  result = subprocess.run(
    engine.curl_base(args) + ["--max-filesize", "1048576", PACKAGE_API],
    capture_output=True, text=True, check=False, timeout=args.max_time + 5,
  )
  if result.returncode:
    raise ValueError("cannot retrieve package metadata: " + result.stderr.strip())
  metadata = json.loads(result.stdout)
  filename = metadata["filename"]
  size = int(metadata["compressed_size"])
  if (
    not re.fullmatch(r"firefox-[A-Za-z0-9._+:-]+-x86_64\.pkg\.tar\.zst", filename)
    or not 1024 * 1024 <= size <= MAX_BYTES
  ):
    raise ValueError("unexpected Firefox filename or compressed_size")
  return metadata, filename, size


def compare_payloads(rows, urls, rounds):
  hashes = {row["sha256"] for row in rows if row["success"]}
  if not hashes:
    return "no_successful_payloads", []
  if len(hashes) != 1 or "" in hashes:
    return "digest_mismatch", []
  ranking = []
  for url in urls:
    group = [row for row in rows if row["url"] == url]
    if (
      len(group) != rounds
      or {row["round"] for row in group} != set(range(1, rounds + 1))
      or not all(row["success"] for row in group)
    ):
      continue
    rates = [
      int(row["size_download"]) / float(row["time_total"]) / engine.MIN_BYTES
      for row in group
    ]
    ranking.append({
      "url": url, "median_mib_per_second": statistics.median(rates),
      "min_mib_per_second": min(rates), "max_mib_per_second": max(rates),
      "median_seconds": statistics.median(float(r["time_total"]) for r in group),
      "successful_rounds": len(group),
    })
  ranking.sort(key=lambda item: (-item["median_mib_per_second"], item["url"]))
  return "complete" if len(ranking) >= 2 else "insufficient_comparisons", ranking


# ---------------------------------------------------------------------------
# Report a separate workload; never install or rewrite a mirrorlist
# ---------------------------------------------------------------------------

def run(args):
  source = json.loads((args.run_dir / "summary.json").read_text())
  args.family = source["family"]
  if args.family not in {"auto", "4", "6"}:
    raise ValueError("source run has an invalid address family")
  urls = [item["url"] for item in source["ranking"][:args.top]]
  baselines = source.get("baseline_urls", [])
  if baselines and baselines[0] not in urls:
    urls.append(baselines[0])
  urls = list(dict.fromkeys(urls))
  if len(urls) < 2:
    raise ValueError("at least two selected mirrors are required")
  for url in urls:
    parsed = urlsplit(url)
    if (
      parsed.scheme != "https" or not parsed.hostname or not url.endswith("/")
      or parsed.username or parsed.password or parsed.query or parsed.fragment
      or any(c.isspace() for c in url) or "$" in url
    ):
      raise ValueError("source run contains an invalid HTTPS mirror URL")
  args.output_dir.mkdir(parents=True, exist_ok=True)
  if any((args.output_dir / name).exists() for name in (
    "raw.csv", "package.json", "summary.json", "report.md",
  )):
    raise ValueError("output directory already contains package-test artifacts")
  metadata, filename, size = package_metadata(args)
  engine.write_json(args.output_dir / "package.json", metadata)
  started = engine.utc_now().isoformat()
  generator = random.Random(args.seed)
  rows = []
  with (args.output_dir / "raw.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=engine.FIELDS)
    writer.writeheader()
    for round_number in range(1, args.rounds + 1):
      ordered = list(urls)
      generator.shuffle(ordered)
      for index, url in enumerate(ordered, 1):
        row = package_probe(url, filename, size, args, round_number, index)
        rows.append(row)
        writer.writerow(row)
        handle.flush()
        outcome = (
          f"{float(row['time_total']):.3f}s" if row["success"]
          else "FAILED: " + row["error"]
        )
        print(
          f"package {round_number} [{index}/{len(ordered)}] {url} {outcome}",
          file=sys.stderr, flush=True,
        )
  status, ranking = compare_payloads(rows, urls, args.rounds)
  summary = {
    "source_run": str(args.run_dir), "started": started,
    "finished": engine.utc_now().isoformat(), "family": args.family,
    "package_api": PACKAGE_API, "filename": filename, "package_bytes": size,
    "rounds": args.rounds, "seed": args.seed, "selected_urls": urls,
    "baseline_urls": baselines, "status": status, "ranking": ranking,
    "downloaded_gib": sum(int(row["size_download"] or 0) for row in rows)
    / 1024 ** 3,
    "successful_sha256": sorted({r["sha256"] for r in rows if r["success"]}),
  }
  engine.write_json(args.output_dir / "summary.json", summary)
  lines = [
    "# Independent large-package validation", "",
    f"Package: `{filename}` ({size / engine.MIN_BYTES:.2f} MiB)",
    f"Started: {started}; finished: {summary['finished']}",
    f"Family: {args.family}; rounds: {args.rounds}; seed: {args.seed}",
    f"Status: **{status}**; transferred {summary['downloaded_gib']:.3f} GiB.",
    "", "| Mirror | Median MiB/s | Min–max MiB/s | Median s |",
    "| :--- | ---: | :--- | ---: |",
  ]
  for item in ranking:
    lines.append(
      f"| {item['url']} | {item['median_mib_per_second']:.2f} | "
      f"{item['min_mib_per_second']:.2f}–{item['max_mib_per_second']:.2f} | "
      f"{item['median_seconds']:.3f} |"
    )
  lines += [
    "", "One current Firefox package was pinned by filename and exact size "
    "from the official Arch package API, then downloaded in full serially "
    "in shuffled rounds. Rates divide package bytes by full transaction time. "
    "Comparisons require every successful payload to have the same SHA256; "
    "a mismatch suppresses ranking. This consistency check is not package "
    "signature verification or a claim of authenticity. A mirror must pass "
    "every round to enter the table.", "",
    "These descriptive measurements test whether the database ranking "
    "generalizes to this larger package during this session. They do not "
    "establish time-of-day stability, a global optimum, or pacman throughput "
    "with parallel streams and connection reuse. Repeat on another day "
    "before treating small differences as persistent.", "",
    f"Metadata source: [official Arch Firefox API]({PACKAGE_API}).", "",
  ]
  (args.output_dir / "report.md").write_text("\n".join(lines))
  print(args.output_dir / "report.md")
  return 0 if status == "complete" else 1


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--run-dir", type=Path, required=True)
  parser.add_argument("--output-dir", type=Path, required=True)
  parser.add_argument("--rounds", type=engine.at_least_three, default=3)
  parser.add_argument("--top", type=engine.positive_int, default=3)
  parser.add_argument("--seed", type=int, default=20261024)
  parser.add_argument("--connect-timeout", type=engine.positive_float, default=3)
  parser.add_argument("--max-time", type=engine.positive_float, default=20)
  args = parser.parse_args()
  try:
    return run(args)
  except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
    print(f"verify-package: {error}", file=sys.stderr)
    return 1
  except KeyboardInterrupt:
    print("verify-package: interrupted; partial raw.csv retained", file=sys.stderr)
    return 130


if __name__ == "__main__":
  sys.exit(main())
