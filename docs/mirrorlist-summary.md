---
title: "Arch mirror benchmark: Copenhagen"
date: "23 October 2026"
lang: en-GB
params:
  evidence_dir: "evidence"
output:
  md_document:
    variant: gfm
    preserve_yaml: true
---

## Recommendation

**Osbeck first, dotsrc second, Lysator third** is the preferred
general-purpose order. Osbeck led database downloads and had lower
observed mean package completion time and variability. Your original
list already started with Osbeck. For median throughput of large
packages, dotsrc is the nominal leader.

## Measurements and results

Of **154 European HTTPS mirrors** screened, 144 passed; all 18 finalists
passed three shuffled repeat rounds. Downloads were serial; elapsed time
included connection setup. The table uses **9 fresh rounds per mirror**
of one 86.17 MiB Firefox package. All 27 payloads had the same SHA256.

| Mirror  | Median MiB/s | Mean ± SD MiB/s | Mean time (s) |
|:--------|-------------:|----------------:|--------------:|
| Osbeck  |        77.17 |    78.33 ± 8.61 |         1.112 |
| dotsrc  |        88.44 |   77.15 ± 16.24 |         1.169 |
| Lysator |        67.74 |    70.24 ± 6.26 |         1.234 |

MiB/s uses binary megabytes. SD is the sample standard deviation across
within-session transfers. Database median rates were **Osbeck 55.58,
dotsrc 37.79, Lysator 36.68 MiB/s** (three rounds each).

Dotsrc’s median package throughput was **14.6% higher** than Osbeck’s,
saving 0.142 seconds at the median. It won 6 of 9 round comparisons.
However, its slower transfers made its **mean completion time 5.1%
longer**, which supports retaining Osbeck first when balancing speed and
consistency.

## Interpretation

These descriptive results cover one host, path and day. Repeated
transfers are not independent days; no significance or confidence claims
are made. Only the database top three received the package check. Other
times of day and pacman’s parallel downloads were not tested. No lasting
winner or whole-upgrade speedup is established; no system mirrorlist was
changed.

Evidence: [detailed benchmark](benchmark-2026-10-23.md) and [saved
measurements](evidence/package-confirm/raw.csv).
