"""Offline checks for package transfer identity and byte-for-byte comparison."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
  "verify_package", ROOT / "verify_package.py",
)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def measurement(url, round_number, elapsed=2, digest="a" * 64, success=True):
  return {
    "url": url, "round": round_number, "time_total": elapsed,
    "size_download": 100 * 1024 * 1024, "sha256": digest, "success": success,
  }


class TransferTests(unittest.TestCase):
  def test_probe_retains_base_url_and_checks_size_http_magic_and_hash(self):
    payload = helper.ZSTD_MAGIC + b"fixture payload"
    args = argparse.Namespace(family="4", max_time=20, connect_timeout=3)

    def fake_curl(command, **_kwargs):
      self.assertEqual(command[:2], ["curl", "--disable"])
      self.assertIn("-4", command)
      path = Path(command[command.index("--output") + 1])
      path.write_bytes(payload)
      return argparse.Namespace(returncode=0, stderr="", stdout=json.dumps({
        "url": command[-1], "http_code": 200, "size_download": len(payload),
        "time_total": 1,
      }))

    with patch.object(helper.subprocess, "run", side_effect=fake_curl):
      row = helper.package_probe(
        "https://mirror.example/arch/", "firefox.pkg.tar.zst", len(payload),
        args, 1, 1,
      )
    self.assertTrue(row["success"])
    self.assertEqual(row["url"], "https://mirror.example/arch/")
    self.assertEqual(len(row["sha256"]), 64)

    with tempfile.TemporaryDirectory() as directory:
      path = Path(directory) / "package"
      path.write_bytes(payload)
      metrics = {
        "http_code": 200, "size_download": len(payload), "time_total": 1,
      }
      self.assertEqual(helper.validate_package(path, metrics, len(payload)), "")
      self.assertIn("size differs", helper.validate_package(path, metrics, 100))
      self.assertIn("HTTP 200", helper.validate_package(
        path, dict(metrics, http_code=206), len(payload),
      ))
      path.write_bytes(b"<html>" + b"x" * (len(payload) - 6))
      self.assertIn("Zstandard", helper.validate_package(
        path, metrics, len(payload),
      ))


class ComparisonTests(unittest.TestCase):
  def test_same_bytes_compared_by_median_effective_throughput(self):
    urls = ["https://a.example/", "https://b.example/"]
    rows = [
      measurement(url, round_number, elapsed=index + 2)
      for index, url in enumerate(urls) for round_number in range(1, 4)
    ]
    status, ranking = helper.compare_payloads(rows, urls, 3)
    self.assertEqual(status, "complete")
    self.assertEqual([item["url"] for item in ranking], urls)
    self.assertEqual(ranking[0]["median_mib_per_second"], 50)

  def test_one_mismatching_successful_hash_suppresses_all_ranking(self):
    urls = ["https://a.example/", "https://b.example/"]
    rows = [
      measurement(url, round_number)
      for url in urls for round_number in range(1, 4)
    ]
    rows[-1]["sha256"] = "b" * 64
    self.assertEqual(helper.compare_payloads(rows, urls, 3), (
      "digest_mismatch", [],
    ))

  def test_any_failed_round_excludes_mirror_from_comparison(self):
    urls = ["https://a.example/", "https://b.example/"]
    rows = [
      measurement(url, round_number)
      for url in urls for round_number in range(1, 4)
    ]
    rows[-1]["success"] = False
    status, ranking = helper.compare_payloads(rows, urls, 3)
    self.assertEqual(status, "insufficient_comparisons")
    self.assertEqual([item["url"] for item in ranking], urls[:1])


if __name__ == "__main__":
  unittest.main()
