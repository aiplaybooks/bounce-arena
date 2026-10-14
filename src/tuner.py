"""Autonomous tuner: after each analytics run, Claude reads summary.md and retunes config/strategy.json.

Same narrow toolset as the Telegram agent (read config/state, edit strategy.json) plus appending
state/changelog.md. Reports what changed to the owner on Telegram.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notify  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRATEGY = os.path.join(ROOT, "config", "strategy.json")
REPORT = os.path.join(ROOT, "state", "tuner_report.txt")

PROMPT = """You are the autonomous growth operator of Bounce Arena: an Instagram (@bouncearena.tv) + Facebook Page channel posting code-generated physics battle Reels (formats "escape" and "grow", themes "countries"/"colors") for US/UK/CA/AU, 4 posts/day. Goal: 5k followers + 250k views by 2026-10-21, $0 budget. The owner does not intervene: you decide.

Now is {now}. Do this:
1. Read state/summary.md (metrics), state/changelog.md (your past changes and their reasoning), config/strategy.json.
2. Decide the changes that most likely raise views, watch time, comments and follows. Rules:
   - Judge with data. Below ~3 posts per variant treat differences as noise; keep exploring (never set a weight to 0, keep >=20% on the non-leader).
   - Watch time vs length (avg watch s / len) is the key retention signal: if viewers drop early, make races shorter (seconds, gap_deg wider, fewer rings) and hooks sharper.
   - Rewrite weak hooks (curiosity, challenge, "pick before the end", tension), keep 5-8 per format, keep exactly one {{champ}} hook and at most one {{a}}/{{b}} hook per format. Keep captions short with a comment prompt. first_comment entries ({{a}},{{b}} allowed) should provoke replies. Rotate tags_rotating toward tags fitting the niche.
   - Use comment requests and engagement to adjust countries_core/extra.
   - Change a few things at a time so effects stay measurable. If nothing justified, change nothing.
3. Edit config/strategy.json only (valid JSON, same schema, keep all keys).
4. Append to state/changelog.md a section "## {now}" with 2-5 bullets: what you changed and why (cite numbers), plus what to check next time.
5. Write state/tuner_report.txt: a short Turkish message for the owner (max 6 lines, plain text): what you changed and why, or that you kept the strategy. If summary.md shows publish errors or broken metrics that need code fixes, add one line starting with "KOD:" describing it.
"""


def main():
    before = open(STRATEGY, encoding="utf8").read()
    if os.path.exists(REPORT):
        os.remove(REPORT)
    env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "TELEGRAM_TOKEN")}
    cmd = ["claude", "-p", PROMPT.format(now=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())),
           "--output-format", "json", "--model", "sonnet", "--max-turns", "15",
           "--allowedTools", "Read(./config/**)", "Read(./state/**)", "Read(./CLAUDE.md)",
           "Edit(./config/strategy.json)", "Edit(./state/changelog.md)", "Write(./state/changelog.md)",
           "Write(./state/tuner_report.txt)",
           "--disallowedTools", "Bash", "WebFetch", "WebSearch", "Task", "NotebookEdit"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600, cwd=ROOT)
        print(r.stdout[-2000:], r.stderr[-1000:])
    except subprocess.TimeoutExpired:
        print("tuner timeout")
    report = open(REPORT, encoding="utf8").read().strip() if os.path.exists(REPORT) else ""
    try:
        json.load(open(STRATEGY, encoding="utf8"))
    except ValueError:
        open(STRATEGY, "w", encoding="utf8").write(before)
        report += "\n⚠️ strategy.json bozuldu, değişiklik geri alındı."
    if os.path.exists(REPORT):
        os.remove(REPORT)
    changed = open(STRATEGY, encoding="utf8").read() != before
    if report and (changed or "KOD:" in report or "⚠️" in report):  # stay quiet when nothing happened
        notify.text("🧠 Otomatik ayar\n" + report)


if __name__ == "__main__":
    main()
