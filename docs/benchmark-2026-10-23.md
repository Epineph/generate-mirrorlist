# Copenhagen mirror benchmark, 23 October 2026

Recommendation: retain **osbeck first, dotsrc second, Lysator third** for a general-purpose list. Osbeck led the database workload and had lower package variability and mean completion time. If the objective is specifically median throughput of larger packages, dotsrc is the nominal leader; swapping the first two entries expresses that choice. These data do not identify one universally fastest mirror.

## Measurements

The survey screened 154 eligible European HTTPS mirrors; 144 completed valid downloads within the configured timeouts. All 18 finalists passed three separate shuffled repeat rounds. Screening samples were excluded from final estimates. The address family was auto.

The live host was confirmed as Arch Linux x86_64. Raw evidence is stored alongside this report. Timings include connection setup; rates are bytes/time_total in binary MiB/s. SD is sample SD (denominator n−1), describing variation across transfers within this session.

### Database: approximately 8.4 MiB, three repeat rounds

| Mirror | n | Median MiB/s | Mean ± SD MiB/s | Range MiB/s | Median s | Mean s |
| :--- | ---: | ---: | :--- | :--- | ---: | ---: |
| mirror.osbeck.com | 3 | 55.58 | 55.85 ± 3.50 | 52.49–59.47 | 0.152 | 0.151 |
| mirrors.dotsrc.org | 3 | 37.79 | 38.52 ± 2.24 | 36.73–41.04 | 0.223 | 0.219 |
| ftp.lysator.liu.se | 3 | 36.68 | 35.81 ± 1.92 | 33.61–37.15 | 0.230 | 0.236 |

### Exploratory Firefox check: three rounds

| Mirror | n | Median MiB/s | Mean ± SD MiB/s | Range MiB/s | Median s | Mean s |
| :--- | ---: | ---: | :--- | :--- | ---: | ---: |
| mirror.osbeck.com | 3 | 74.94 | 77.33 ± 11.18 | 67.54–89.51 | 1.150 | 1.129 |
| mirrors.dotsrc.org | 3 | 90.96 | 87.36 ± 6.41 | 79.96–91.15 | 0.947 | 0.990 |
| ftp.lysator.liu.se | 3 | 67.21 | 67.23 ± 2.45 | 64.79–69.68 | 1.282 | 1.283 |

### Longer Firefox confirmation: nine fresh rounds

The exact file `firefox-158.0.1-1-x86_64.pkg.tar.zst` contained 90,351,212 bytes (86.17 MiB). Every successful package payload in both runs had the same SHA256. The two runs remain separate rather than pooling a follow-up chosen after inspecting the exploratory results.

| Mirror | n | Median MiB/s | Mean ± SD MiB/s | Range MiB/s | Median s | Mean s |
| :--- | ---: | ---: | :--- | :--- | ---: | ---: |
| mirror.osbeck.com | 9 | 77.17 | 78.33 ± 8.61 | 64.70–90.57 | 1.117 | 1.112 |
| mirrors.dotsrc.org | 9 | 88.44 | 77.15 ± 16.24 | 52.79–92.00 | 0.974 | 1.169 |
| ftp.lysator.liu.se | 9 | 67.74 | 70.24 ± 6.26 | 66.13–84.86 | 1.272 | 1.234 |

## Practical effect sizes

Dotsrc's ratio of median package rates was 1.146: 14.6% higher than osbeck. Its median transfer saved 0.142 seconds (12.7% less time). Its mean transfer instead took 0.057 seconds longer (5.1%), because of its slower tail.

Dotsrc won 6/9 round comparisons. The median of the round-paired throughput differences was +8.0%, with range -41.7% to +23.3%. This is a different quantity from the ratio of marginal medians above; neither is presented as a whole-upgrade speedup.

Per-round dotsrc throughput differences relative to osbeck (%): +10.6, +23.3, -41.7, +14.6, +8.0, -6.1, -27.9, +3.3, +9.5.

## Why descriptive statistics

The experimental observations are serial transfers blocked by shuffled round, on one host, network path and day. A round is not a new ISP or an independent day. Repeating downloads estimates within-session variation; it does not supply independent evidence of long-term superiority. No p-values, SEM or 95% confidence claims are used to select the order. Mean rate and mean completion time also need not rank mirrors identically: taking a reciprocal is nonlinear.

The large-package test considered only the database top three, so a mirror with slow setup but exceptional sustained throughput may have been missed. Neither IPv4/IPv6 alternatives, other times of day, nor pacman's five concurrent downloads were compared. No package was installed, no pacman database was refreshed, and no system mirrorlist was applied. Signature authenticity was not tested; SHA256 equality checks only payload consistency.

## Evidence and reproduction

- [Database raw data](evidence/database/raw.csv), [summary](evidence/database/summary.json), [proposed list](evidence/database/mirrorlist)
- [Exploratory package raw data](evidence/package-exploratory/raw.csv)
- [Confirmation package raw data](evidence/package-confirm/raw.csv), [summary](evidence/package-confirm/summary.json)
- [Official mirror-status snapshot](mirror-status-20261023.json)
- Recreate this report: `/usr/bin/python docs/analyze_results.py`.

Primary definitions: [Arch Mirror Status](https://archlinux.org/mirrors/status/), [Reflector documentation](https://xyne.dev/projects/reflector/).
