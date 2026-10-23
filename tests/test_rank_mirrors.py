"""Offline checks for measurement validity and ranking decisions."""

import datetime as dt
import gzip
import importlib.util
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
  "rank_mirrors", ROOT / "rank_mirrors.py",
)
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)
NOW = dt.datetime(2026, 10, 23, 16, tzinfo=dt.timezone.utc)


def mirror(url="https://fast.example/arch/", **changes):
  value = {
    "url": url, "active": True, "protocol": "https",
    "completion_pct": 1.0, "country_code": "DK",
    "last_sync": "2026-10-23T15:00:00Z", "ipv4": True, "ipv6": False,
  }
  return dict(value, **changes)


def row(url, round_number, seconds, size_mib=10, success=True, phase="repeat"):
  return {
    "phase": phase, "url": url, "round": round_number,
    "success": success, "time_total": seconds,
    "size_download": size_mib * engine.MIN_BYTES,
  }


class EligibilityTests(unittest.TestCase):
  def test_health_age_country_and_scheme_are_all_required(self):
    entries = [
      mirror(),
      mirror("https://failed.example/", completion_pct=0.99),
      mirror("https://inactive.example/", active=False),
      mirror("http://plain.example/", protocol="http"),
      mirror("https://wrong.example/", country_code="US"),
      mirror("https://old.example/", last_sync="2026-10-22T00:00:00Z"),
      mirror("https://future.example/", last_sync="2026-10-24T00:00:00Z"),
      mirror("https://credentials:secret@example/"),
      mirror("https://bad.example/$repo/"),
    ]
    result = engine.eligible_mirrors(
      {"urls": entries}, {"DK", "SE"}, 12, "auto", NOW,
    )
    self.assertEqual([item["url"] for item in result], [entries[0]["url"]])

  def test_family_is_an_explicit_support_filter(self):
    status = {"urls": [mirror(), mirror("https://v6.example/", ipv6=True)]}
    result = engine.eligible_mirrors(status, {"DK"}, 12, "6", NOW)
    self.assertEqual([item["url"] for item in result], ["https://v6.example/"])

  def test_baseline_keeps_first_five_eligible_distinct_servers(self):
    with tempfile.TemporaryDirectory() as directory:
      path = Path(directory) / "mirrorlist"
      entries = [mirror(f"https://{i}.example/") for i in range(7)]
      lines = ["# Server = https://comment.example/$repo/os/$arch"]
      lines += [
        f"Server = {item['url']}$repo/os/$arch" for item in entries
      ]
      path.write_text("\n".join(lines))
      result = engine.baseline_urls(path, entries)
    self.assertEqual(result, [item["url"] for item in entries[:5]])


class RankingTests(unittest.TestCase):
  def test_independent_median_throughput_not_single_winner_or_smallest_body(self):
    a = mirror("https://a.example/")
    b = mirror("https://b.example/")
    measurements = [
      row(a["url"], 0, 0.0001, phase="screen"),
      row(a["url"], 1, 1), row(a["url"], 2, 1), row(a["url"], 3, 0.01),
      row(b["url"], 1, 1.5, 20), row(b["url"], 2, 1.5, 20),
      row(b["url"], 3, 4, 20),
    ]
    result = engine.rank_repeats(measurements, [a, b], 3)
    self.assertEqual([item["url"] for item in result], [b["url"], a["url"]])
    self.assertAlmostEqual(result[0]["median_mib_per_second"], 20 / 1.5)
    self.assertEqual(result[1]["median_seconds"], 1)

  def test_failed_missing_or_duplicate_round_excludes_candidate(self):
    entries = [mirror(f"https://{i}.example/") for i in range(4)]
    measurements = [
      row(entries[0]["url"], 1, 1), row(entries[0]["url"], 2, 1),
      row(entries[0]["url"], 3, 1, success=False),
      row(entries[1]["url"], 1, 1), row(entries[1]["url"], 2, 1),
      row(entries[2]["url"], 1, 1), row(entries[2]["url"], 1, 1),
      row(entries[2]["url"], 3, 1),
      row(entries[3]["url"], 1, 1), row(entries[3]["url"], 2, 1),
      row(entries[3]["url"], 3, 1),
    ]
    result = engine.rank_repeats(measurements, entries, 3)
    self.assertEqual([item["url"] for item in result], [entries[3]["url"]])


class DownloadTests(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.payload = gzip.compress(random.Random(42).randbytes(2 * engine.MIN_BYTES))

  def test_complete_database_and_corrupt_bodies(self):
    with tempfile.TemporaryDirectory() as directory:
      path = Path(directory) / "extra.db"
      path.write_bytes(self.payload)
      metrics = {
        "http_code": 200, "size_download": len(self.payload), "time_total": 1,
      }
      self.assertEqual(engine.validate_download(path, metrics), "")
      self.assertIn(
        "byte count",
        engine.validate_download(path, dict(metrics, size_download=1)),
      )
      self.assertIn(
        "HTTP 200",
        engine.validate_download(path, dict(metrics, http_code=206)),
      )
      path.write_bytes(self.payload[:-10])
      self.assertIn(
        "complete gzip",
        engine.validate_download(
          path, dict(metrics, size_download=path.stat().st_size),
        ),
      )
      path.write_bytes(b"<html>" + b"x" * (2 * engine.MIN_BYTES))
      self.assertIn(
        "complete gzip",
        engine.validate_download(
          path, dict(metrics, size_download=path.stat().st_size),
        ),
      )

  def test_probe_forces_requested_family_and_disables_curl_configuration(self):
    args = engine.build_parser().parse_args([
      "--output-dir", "/tmp/example", "--family", "6",
    ])

    def fake_curl(command, **_kwargs):
      self.assertEqual(command[:2], ["curl", "--disable"])
      self.assertIn("-6", command)
      self.assertEqual(command[command.index("--proto") + 1], "=https")
      path = Path(command[command.index("--output") + 1])
      path.write_bytes(self.payload)
      metrics = {
        "http_code": 200, "size_download": len(self.payload),
        "time_total": 0.5, "speed_download": 9,
        "url": "https://fast.example/arch/extra/os/x86_64/extra.db",
      }
      return type("Result", (), {
        "returncode": 0, "stdout": json.dumps(metrics), "stderr": "",
      })()

    with patch.object(engine.subprocess, "run", side_effect=fake_curl):
      result = engine.probe(mirror(), args, "repeat", 1, 1)
    self.assertTrue(result["success"])
    self.assertEqual(len(result["sha256"]), 64)
    self.assertEqual(result["speed_download"], 9)
    self.assertEqual(result["url"], mirror()["url"])


class FailureTests(unittest.TestCase):
  def test_failed_repeat_leaves_evidence_but_no_installable_mirrorlist(self):
    with tempfile.TemporaryDirectory() as directory:
      root = Path(directory)
      status_path = root / "input.json"
      status_path.write_text(json.dumps({
        "last_check": NOW.isoformat(),
        "urls": [mirror(f"https://{i}.example/") for i in range(3)],
      }))
      args = engine.build_parser().parse_args([
        "--output-dir", str(root / "result"), "--status-file", str(status_path),
        "--countries", "DK", "--number", "3", "--finalists", "3",
      ])

      def fake_probe(item, _args, phase, round_number, position):
        result = dict.fromkeys(engine.FIELDS, "")
        result.update(row(
          item["url"], round_number, 1, success=phase == "screen", phase=phase,
        ))
        result.update(country_code="DK", position=position, error="fixture")
        return result

      with (
        patch.object(engine, "utc_now", return_value=NOW),
        patch.object(engine, "probe", side_effect=fake_probe),
      ):
        with self.assertRaisesRegex(ValueError, "no mirrorlist written"):
          engine.run(args)
      self.assertTrue((args.output_dir / "raw.csv").is_file())
      self.assertTrue((args.output_dir / "report.md").is_file())
      self.assertFalse((args.output_dir / "mirrorlist").exists())

  def test_stale_status_is_rejected(self):
    with tempfile.TemporaryDirectory() as directory:
      path = Path(directory) / "status.json"
      path.write_text(json.dumps({
        "urls": [], "last_check": "2026-01-01T00:00:00Z",
      }))
      args = engine.build_parser().parse_args([
        "--output-dir", directory, "--status-file", str(path),
      ])
      with patch.object(engine, "utc_now", return_value=NOW):
        with self.assertRaisesRegex(ValueError, "past 24 hours"):
          engine.load_status(args)


class IntegrationTests(unittest.TestCase):
  def test_real_probe_pipeline_retains_base_urls_and_writes_ranked_list(self):
    payload = DownloadTests.payload
    with tempfile.TemporaryDirectory() as directory:
      root = Path(directory)
      status_path = root / "input.json"
      status_path.write_text(json.dumps({
        "last_check": NOW.isoformat(),
        "urls": [mirror(f"https://{i}.example/") for i in range(3)],
      }))
      args = engine.build_parser().parse_args([
        "--output-dir", str(root / "result"), "--status-file", str(status_path),
        "--countries", "DK", "--number", "3", "--finalists", "3",
        "--baseline", str(root / "missing-baseline"),
      ])

      def fake_curl(command, **_kwargs):
        path = Path(command[command.index("--output") + 1])
        path.write_bytes(payload)
        requested = command[-1]
        elapsed = int(requested.split("//", 1)[1][0]) + 1
        metrics = {
          "http_code": 200, "size_download": len(payload),
          "time_total": elapsed, "url": requested,
        }
        return type("Result", (), {
          "returncode": 0, "stdout": json.dumps(metrics), "stderr": "",
        })()

      with (
        patch.object(engine, "utc_now", return_value=NOW),
        patch.object(engine.subprocess, "run", side_effect=fake_curl),
        patch("sys.stderr"), patch("sys.stdout"),
      ):
        engine.run(args)
      content = (args.output_dir / "mirrorlist").read_text().splitlines()
      servers = [line for line in content if line.startswith("Server =")]
      self.assertEqual(servers, [
        f"Server = https://{i}.example/$repo/os/$arch" for i in range(3)
      ])
      summary = json.loads((args.output_dir / "summary.json").read_text())
      self.assertEqual(summary["repeat_successes"], 3)
      self.assertEqual(summary["ranking"][0]["url"], "https://0.example/")


if __name__ == "__main__":
  unittest.main()
