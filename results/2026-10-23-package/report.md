# Separate large-package validation

Package: `firefox-158.0.1-1-x86_64.pkg.tar.zst` (86.17 MiB)
Started: 2026-10-23T16:26:28.787856+00:00; finished: 2026-10-23T16:26:39.674125+00:00
Family: auto; rounds: 3; seed: 20261024
Status: **complete**; transferred 0.757 GiB.

| Mirror | Median MiB/s | Min–max MiB/s | Median s |
| :--- | ---: | :--- | ---: |
| https://mirrors.dotsrc.org/archlinux/ | 90.96 | 79.96–91.15 | 0.947 |
| https://mirror.osbeck.com/archlinux/ | 74.94 | 67.54–89.51 | 1.150 |
| https://ftp.lysator.liu.se/pub/archlinux/ | 67.21 | 64.79–69.68 | 1.282 |

One current Firefox package was pinned by filename and exact size from the official Arch package API, then downloaded in full serially in shuffled rounds. Rates divide package bytes by full transaction time. Comparisons require every successful payload to have the same SHA256; a mismatch suppresses ranking. This consistency check is not package signature verification or a claim of authenticity. A mirror must pass every round to enter the table.

These descriptive measurements test whether the database ranking generalizes to this larger package during this session. They do not establish time-of-day stability, a global optimum, or pacman throughput with parallel streams and connection reuse. Repeat on another day before treating small differences as persistent.

Metadata source: [official Arch Firefox API](https://archlinux.org/packages/extra/x86_64/firefox/json/).
