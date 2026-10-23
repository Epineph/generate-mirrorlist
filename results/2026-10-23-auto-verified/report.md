# Local Arch mirror benchmark

Started: 2026-10-23T16:21:03.520339+00:00
Finished: 2026-10-23T16:25:50.283681+00:00
Arch status last check: 2026-10-23T15:19:00.590Z
Family: auto; seed: 20261023
Countries: AT,BE,CH,CZ,DE,DK,EE,ES,FI,FR,GB,LT,LV,NL,NO,PL,SE,UA

Screened 154 eligible HTTPS mirrors serially; 144 succeeded. Retested 18 finalists in 3 shuffled rounds.
Transferred 1.652 GiB of recorded bodies.

| Rank | Country | Mirror | Median s | Min–max s | MiB/s |
| ---: | :--- | :--- | ---: | :--- | ---: |
| 1 | SE | https://mirror.osbeck.com/archlinux/ | 0.152 | 0.142–0.161 | 55.58 |
| 2 | DK | https://mirrors.dotsrc.org/archlinux/ | 0.223 | 0.205–0.230 | 37.79 |
| 3 | SE | https://ftp.lysator.liu.se/pub/archlinux/ | 0.230 | 0.227–0.251 | 36.68 |
| 4 | NO | https://mirror.neuf.no/archlinux/ | 0.254 | 0.247–0.274 | 33.14 |
| 5 | DE | https://mirror.as20647.net/archlinux/ | 0.256 | 0.239–0.276 | 32.96 |
| 6 | SE | https://mirror.tedwall.se/archlinux/ | 0.277 | 0.233–0.528 | 30.44 |
| 7 | NL | https://mirror.ams1.nl.leaseweb.net/archlinux/ | 0.285 | 0.274–0.292 | 29.59 |
| 8 | DE | https://mirrors.xtom.de/archlinux/ | 0.285 | 0.270–0.308 | 29.58 |
| 9 | DE | https://mirror.wtnet.de/archlinux/ | 0.299 | 0.277–0.567 | 28.19 |
| 10 | DK | https://mirror.group.one/archlinux/ | 0.302 | 0.231–0.403 | 27.92 |
| 11 | DE | https://arch.mirror.cloud.thatcyberlynx.de/ | 0.309 | 0.208–0.428 | 27.30 |
| 12 | BE | https://mirror.1ago.be/archlinux/ | 0.312 | 0.288–1.317 | 27.00 |
| 13 | FI | https://mirror.wuki.li/archlinux/ | 0.443 | 0.294–0.540 | 19.05 |
| 14 | FR | https://mirror.trap.moe/archlinux/ | 0.668 | 0.319–0.896 | 12.62 |
| 15 | DE | https://ftp.fau.de/archlinux/ | 0.757 | 0.422–0.950 | 11.14 |
| 16 | DE | https://arch.alhp.dev/ | 0.759 | 0.319–1.349 | 11.11 |
| 17 | FI | https://dornogal.falcao.org/archlinux/ | 1.047 | 0.300–1.197 | 8.05 |
| 18 | DE | https://frankfurt.mirror.pkgbuild.com/ | 1.365 | 0.296–1.401 | 6.18 |

## Interpretation

Ranking uses median effective throughput: bytes divided by full transaction time including DNS, TCP/TLS, headers, and body. This differs from Reflector's body-only timing. Curl's speed_download metric is retained alongside bytes and total time in raw.csv. Normalizing by size avoids favoring smaller database versions. Screening samples are excluded from final medians. Every retained finalist must pass every repeat. First eligible baseline mirrors are included among finalists when their screening download succeeds.

These observations describe this host's current network path, VPN/proxy settings, and time window. They do not prove the globally fastest mirror. One screening sample can miss a temporarily slow contender. Shuffling reduces order effects but does not eliminate background traffic or time-of-day effects. Use multiple sessions and sustained package downloads before claiming persistent superiority.

The object is extra/os/x86_64/extra.db, a compressed repository database. It may change during the run, and mirrors can serve slightly different versions. Raw byte counts and SHA256 hashes are retained for assessing this limitation. This does not simulate pacman's five concurrent package streams, connection reuse, or much larger packages. No package databases were installed or refreshed on this computer.

Official status completion is a health filter measured by Arch, not a download-speed measurement from Copenhagen. Geographic country is only a search prior; measured times determine the order.

Sources: [Arch mirror status](https://archlinux.org/mirrors/status/), [Reflector documentation](https://xyne.dev/projects/reflector/).
