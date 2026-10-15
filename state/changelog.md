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

## 2026-10-15 06:57 UTC
- All 4 posts so far are escape/countries (grow/colors still at 0 — random draw, weights 3:2 and 4:1 left untouched since nothing is broken, just unlucky sampling).
- Watch%/len is monotonically improving as videos get shorter across all 3 posts with IG data: 12.2/30.62 (40%), 8.2/21.83 (38%), 8.6/18.85 (46%) — the shortest post has the best retention, so trimmed escape further: seconds 18-30 -> 16-26, gap_deg 36-46 -> 40-50 (faster races, same ring count since no data isolates rings alone).
- Hooks/captions/tags/countries left untouched — max 2 posts per hook variant, 0 comment requests in state/requests.json, nowhere near the ~3-per-variant threshold.
- Views (792) and followers (26) are far behind the 250k/5k week-1 goal with 6 days left; once grow has a few posts, compare format performance and reconsider the hook set with real data.
- Next time: check if avg watch% keeps climbing with the 16-26s range; if grow/colors still have 0 posts after this round, that's worth a second look (not just randomness).
