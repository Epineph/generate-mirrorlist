# Separate large-package validation

Package: `firefox-158.0.1-1-x86_64.pkg.tar.zst` (86.17 MiB)
Started: 2026-10-23T16:29:15.258412+00:00; finished: 2026-10-23T16:29:49.138569+00:00
Family: auto; rounds: 9; seed: 20261024
Status: **complete**; transferred 2.272 GiB.

| Mirror | Median MiB/s | Min–max MiB/s | Median s |
| :--- | ---: | :--- | ---: |
| https://mirrors.dotsrc.org/archlinux/ | 88.44 | 52.79–92.00 | 0.974 |
| https://mirror.osbeck.com/archlinux/ | 77.17 | 64.70–90.57 | 1.117 |
| https://ftp.lysator.liu.se/pub/archlinux/ | 67.74 | 66.13–84.86 | 1.272 |

One current Firefox package was pinned by filename and exact size from the official Arch package API, then downloaded in full serially in shuffled rounds. Rates divide package bytes by full transaction time. Comparisons require every successful payload to have the same SHA256; a mismatch suppresses ranking. This consistency check is not package signature verification or a claim of authenticity. A mirror must pass every round to enter the table.

These descriptive measurements test whether the database ranking generalizes to this larger package during this session. They do not establish time-of-day stability, a global optimum, or pacman throughput with parallel streams and connection reuse. Repeat on another day before treating small differences as persistent.

Metadata source: [official Arch Firefox API](https://archlinux.org/packages/extra/x86_64/firefox/json/).
