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
- 2026-10-15: <4 posts with full metrics (3 IG: 434/216/136 views, watch 8.2-12.2s) -> no weight changes; added escape hook 'Bet you can't guess the winner'. grow still 0 posts.

## 2026-10-15 owner/desk change
- AUDIO CHANGED: melody removed (owner said it was headache-inducing), now only soft low collision pops/ticks. Compare avg watch%/len of posts after 2026-10-15 vs before before judging other changes.
- Posts 4 -> 6/day (added 12:30 and 19:00 UTC).
- plan.py now forces any format/theme with weight>0 and <3 posts first (grow and colors had 0 posts).

## 2026-10-15 12:57 UTC
- Found themes.colors weight=0, which breaks the "never 0, keep >=20% of leader" rule (leader weight 3) — fixed to 2, matching billionaires' weight. No colors posts exist yet; plan.py's forced-first-run logic should now pick it up.
- Still only 5 posts total (4 escape/countries, 1 grow/singers) — every format/theme/hook comparison is well below the ~3-per-variant noise threshold, so weights, hooks, captions and tags are otherwise untouched this round.
- Watch%/len on the 3 escape posts with IG data (42.6%, 39.8%, 45.1%) still looks consistent with the shortest post retaining best, matching the prior trend; the single grow/singers post is lower (35% at 22.85s) but n=1 so no pacing change yet.
- No comment requests in state/requests.json, so countries_core/extra untouched.
- Next time: once grow/colors/footballers/billionaires/brands each have >=3 posts, compare theme performance properly; watch whether grow's retention stays below escape's as more grow posts land (would justify trimming grow seconds range too).

## 2026-10-15 18:53 UTC
- grow now has n=3 with IG watch data (singers x2, billionaires x1) and is consistently below escape's n=3: grow watch%/len 32.8%, 35.0%, 30.2% (avg ~33%) vs escape 42.1%, 41.8%, 45.6% (avg ~43%) — same gap flagged last round but now both sides hit the ~3-per-variant threshold, so trimmed grow.seconds 16-32 -> 14-22 to match the shortening that already worked for escape. Left grow_step/target_r untouched to isolate the effect of length alone.
- Still 0 posts for themes colors/footballers/brands despite weight>=2 each (only countries, singers, billionaires have posted) — plan.py's forced-first-run logic should pick these next; not a bug yet, just sequencing, revisit if still 0 after a few more cycles.
- No comment requests in state/requests.json, so countries_core/extra and first_comment left untouched.
- Hooks: no hook variant has reached 3 uses yet (max is 2, "Champion {champ}" and "Watch till the last bounce" each used twice) — below threshold, hooks/captions/tags untouched this round.
- Next time: check grow watch%/len after the 14-22s trim — if it closes the gap with escape, the length theory is confirmed and escape could be trimmed further too; also check whether colors/footballers/brands have posted yet.
