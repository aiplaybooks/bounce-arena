# Strategy changelog

## 2026-10-15 (desktop)
- Added first_comment (auto first comment on IG+FB), one publish retry, autonomous tuner after each analytics run.

## 2026-10-14 22:04 UTC
- Only 2 posts exist (day 1), both escape/countries with the champion hook — below the ~3-per-variant noise threshold, so weights, hooks, captions, tags and countries lists are untouched this round.
- The one post with watch data: 8.4s avg watch on a 30.62s video (~27% retention) — low. Per the retention rule, trimmed escape pacing: seconds 20-38 -> 18-30, rings 4-6 -> 3-5, gap_deg 32-42 -> 36-46 (faster, shorter races).
- No comment requests yet (state/requests.json empty), so countries_core/extra left as-is.
- Next time: check avg watch s / len for escape posts under the new shorter range — if retention improves, consider the same trim for grow once it has posts; if escape/countries still has only 1-2 posts, keep waiting before touching weights.
