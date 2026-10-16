# Bounce Arena — autonomous IG/FB Reels channel

Owner talks Turkish; reply in Turkish. Content is English (US/UK/CA/AU).
Goal: week 1 (until ~2026-10-21) 5k followers + 250k views. Budget $0. Never render video on the owner's PC — rendering runs in GitHub Actions.

## Token-saving rules
- Start a session by reading ONLY `state/summary.md` (written by analytics every 6h). Do not reread chat history or the whole codebase.
- Tune behaviour by editing `config/strategy.json` (format/theme weights, hooks, captions, tags). Code changes only when the summary shows a real problem.
- Test narrowly: `gh workflow run post -f preview=true` (3 PNG stills) or `-f dry_run=true` (mp4 artifact, no publish). Never full-run to test.
- Pull state before editing: `git pull`. Bot commits to `state/` after every run.

## Layout
- `src/physics.py` deterministic sim (escape rings / grow); `race_stats` for cheap seed search.
- `src/plan.py` picks format/theme/teams/hook/caption from strategy + comment requests + last champion.
- `src/render.py` pygame -> ffmpeg 1080x1920@60. `src/audio.py` synthesized pentatonic bounce sounds (no licensed audio).
- `src/publish.py` IG (graph.instagram.com, video_url from temp asset on public `media` release, deleted after) + FB Page `video_reels`. `src/run.py` one cycle.
- `src/analytics.py` metrics, comment country requests -> `state/requests.json`, `state/summary.md`.
- `src/arenas.py` 12 extra headless arena sims (maze, golf, plinko, race, storm, territory, sumo, tower, chain, flip, pinball, hole) emitting generic shapes that `render.py` draws; each is a `formats` entry in strategy.json (params there). Themes `clubs`/`ai` added to pools.
- `PAYLASILACAK/` = 12 ready-made videos (built once by `batch.yml`, order in `queue.json`/`PLAN.md`, captions in NN_*.txt). `post.yml` schedule runs `--queue-first`: publishes the next queued video to IG only (FB is scheduled by hand from the same folder); when the queue is empty it generates fresh posts as before.
- Workflows: `post.yml` (4 UTC slots), `analytics.yml` (every 6h, then `src/tuner.py`: claude -p Sonnet retunes strategy.json, logs to `state/changelog.md`, Telegram note only when it changed something or flags `KOD:`).
- Each post gets an auto first comment (`first_comment` in strategy) on IG+FB; publishes retry once.
- `src/notify.py` Telegram @bounce_arena_bot -> owner (chat 1274408121): video per post + daily digest at 06:15 UTC.

## Accounts / secrets
IG @bouncearena.tv (IG Login token, expires ~2026-12-13 — refresh via `GET graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token` then `gh secret set IG_TOKEN`).
FB Page Bounce Arena 1197361546796323, page token never expires. Local copies in `.secrets/` (gitignored, never print them).

## Telegram chat (owner talks to a restricted Claude)
Telegram -> Cloudflare Worker `worker/` (https://bounce-arena-bot.bouncearena.workers.dev, checks webhook secret + owner chat id) -> `repository_dispatch: telegram` -> `.github/workflows/telegram.yml` -> `src/tg_agent.py` runs `claude -p` (CLAUDE_CODE_OAUTH_TOKEN, owner's Pro plan) with ONLY: Read config/state/CLAUDE.md, Edit config/strategy.json, Write state/tg_action.json (post/preview triggers). No shell/web/code edits — by owner's choice (option A). History: state/tg_chat.json (last 20). Worker secrets: TG_TOKEN, GH_PAT (fine-grained, 90 days), WEBHOOK_SECRET. Redeploy: `cd worker && npx wrangler@4.42.0 deploy`.
