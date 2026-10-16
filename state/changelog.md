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

## 2026-10-16 00:53 UTC
- No strategy.json changes this round. The 3 grow posts with watch data (singers x2, billionaires x1) are all from BEFORE the 18:53 UTC trim to seconds 14-22 — no new grow post has landed since, so there's still zero evidence on whether that trim worked; re-judging the same stale 3 points again would be noise, not a new signal.
- Themes colors and brands still have 0 posts after 9 total (weight 2 and 3, both >=20% of leader) despite plan.py's forced-first-run explore() logic making them eligible every cycle — statistically unlucky (~13-40% chance each) but worth a hard look next round if they're still at 0, since 5 days remain to hit 5k/250k.
- No hook has reached the n=3 threshold yet (max is 2: "Only one gets out first" ~44% retention avg, "Watch till the last bounce" ~32% avg) and state/requests.json is still empty (no comment requests), so hooks, captions, tags and countries lists are untouched.
- Escape retention (42-46% across 5 posts with IG data) continues to beat grow (30-35%, pre-trim) — consistent with prior rounds, already acted on via the 14-22s trim; no further escape/grow weight change until post-trim grow data exists.
- Reality check: 3299/250000 views and 26/5000 followers with 5 days left — far behind pace, but overreacting to n=1-2 posts (confounded by how long each post has been live) would just add noise. Next time: judge the grow trim once new grow posts land; if colors/brands are still at 0 posts, consider flagging plan.py's uniform-random explore() as a real fix target (it treats every eligible option equally regardless of weight, so a stuck streak is possible even though each is individually low-probability).

## 2026-10-16 06:56 UTC
- Found a real correctness bug: caption template #2 and the first_comment "Comment your country..." line are hardcoded to "country" wording, but plan.py only applies the country->noun substitution to hooks (line ~90-92), not to caption templates or first_comment. Posts like 20261015-192915 (escape/footballers, Mbappe race) shipped with caption text "Drop your country in the comments" — nonsensical for 6 of 10 posts so far (any non-countries theme). Fixed at the strategy level by making both generic ("Drop your pick...", "Comment your pick...") since that works for every theme without code changes. KOD flag below for the proper fix (apply the same noun substitution plan.py does for hooks to caption and first_comment too).
- Shares are 0/10 across every post regardless of format/theme/hook — a full-sample signal, not noise. Added one share-oriented CTA ("Tag a friend who'd pick wrong") to the cta pool shown on the winner screen; IG's distribution algorithm weights shares heavily, so even a small lift here could help reach more than further hook/pacing tweaks at this view scale (130-1350 views/post).
- Swapped tags_rotating "#countryballs" -> "#ballrace": that tag only fits the countries theme, but themes are now split across countries/colors/singers/footballers/billionaires/brands, so a universal tag fits the current rotation better.
- No format/theme/hook weight or pacing changes: escape retention (42.9% avg, n=6) still beats grow (33.0% avg, n=3) but all 3 grow posts predate the 18:53 UTC seconds 14-22 trim (mode-level explore() stopped forcing grow after it hit n=3, so it now only gets drawn ~20% of the time via weight) — still zero post-trim grow data to judge, third round noting this. No hook has reached n=3 (max 2), no comment requests in state/requests.json, brands theme still 0/10 posts (plausible at ~19% draw chance per cycle, not yet alarming) — all below the noise threshold, left untouched.
- Next time: judge the grow 14-22s trim once a post-trim grow post lands; check if the generic caption/first_comment wording reads naturally across themes; check if shares move off 0 after the new CTA; if brands is still at 0 after this round, escalate past "statistically unlucky."
- 2026-10-16: themes countries 4->6, footballers 3->4, singers 3->2 (escape/countries avg 608 views n=4, footballers 447 n=1, singers grow 142 n=2); replaced bottom hooks 'Watch till the last bounce' (130/128 views) and 'Only one gets out first' (143/131) with new variants; format weights unchanged (escape 4 : grow 1, grow avg ~140 vs escape 400+).

## 2026-10-16 18:50 UTC
- Added an explicit share nudge ("Send this to someone who'd pick wrong" / "Tag someone who'd lose this bet" / "Share this with someone who'd pick wrong") to all 3 caption templates. Why: shares are 0/13 across every post so far (full-sample signal, not noise), and avg retention is only ~43.5% on escape / ~32.4% on grow — meaning most viewers never reach the end-screen CTA where the only existing share prompt ("Tag a friend who'd pick wrong", added last round) lives. Putting the ask in the caption text means every viewer sees it immediately regardless of watch time.
- No format/theme/hook weight or pacing changes: 11 of 13 variant combos are still below the ~3-post noise threshold. The one comparison at threshold (escape n=7 avg 43.5% retention / ~800 views vs grow n=3 avg 32.4% / ~145 views) is unchanged from prior rounds and already reflected in the 2:1 format weight — all 3 grow posts still predate the seconds 14-22 trim (queue-first posting via PAYLASILACAK has been filling slots with new arena formats — maze, golf so far — so grow hasn't gotten a fresh slot yet). escape/footballers (1445 views avg, n=2) and golf/clubs (1553, n=1) are the top performers but both still below n=3, worth re-checking next round.
- No comment requests in state/requests.json, so countries_core/extra untouched.
- Found a likely analytics blind spot (not fixed here, flagged as KOD to owner): IG "comments" count is 1 for 11 of the last 12 posts — almost certainly just the bot's own auto first_comment being counted, not real user replies. This makes it impossible to tell whether any hook/caption is actually driving real comments; analytics.py should subtract 1 (or match+exclude the bot's own first_comment id) before reporting cmts in summary.md.
- Next time: check if shares move off 0 now that the ask is in the caption text; judge escape/footballers and golf/clubs once they reach n=3; judge the grow 14-22s trim once a post-trim grow post lands (still 0 so far, 4th round noting this — queue needs to clear ~10 more arena-format slots first).
