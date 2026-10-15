# Strategy changelog

## 2026-10-15 (desktop)
- Added first_comment (auto first comment on IG+FB), one publish retry, autonomous tuner after each analytics run.

## 2026-10-14 22:04 UTC
- Only 2 posts exist (day 1), both escape/countries with the champion hook — below the ~3-per-variant noise threshold, so weights, hooks, captions, tags and countries lists are untouched this round.
- The one post with watch data: 8.4s avg watch on a 30.62s video (~27% retention) — low. Per the retention rule, trimmed escape pacing: seconds 20-38 -> 18-30, rings 4-6 -> 3-5, gap_deg 32-42 -> 36-46 (faster, shorter races).
- No comment requests yet (state/requests.json empty), so countries_core/extra left as-is.
- Next time: check avg watch s / len for escape posts under the new shorter range — if retention improves, consider the same trim for grow once it has posts; if escape/countries still has only 1-2 posts, keep waiting before touching weights.

## 2026-10-15 00:53 UTC
- Only 3 posts total exist, all escape/countries (no grow, no colors yet) and no comment requests in state/requests.json — below the ~3-per-variant noise threshold for every comparison (format, theme, hook), so left config/strategy.json untouched this round.
- The shorter escape pacing from the previous trim looks like it's helping: watch%/len is now ~38% on both posts with IG watch data (11.8/30.62, 8.2/21.83) vs ~27% before the trim — consistent across n=2 but still too few to lock in further changes.
- Post 20261014-210125 (first ever post) has no ig_id/ig metrics at all, only fb — looks like the IG publish failed that cycle even with the one retry. Flagged below as KOD for the owner to check publish logs.
- Next time: once grow/colors posts exist and/or comment requests come in, compare format and hook performance properly; keep watching whether the ~38% retention holds as more escape posts land.
