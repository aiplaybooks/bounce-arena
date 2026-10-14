"""Telegram chat agent: runs Claude Code on the owner's message with a narrow toolset.

Claude may only read config/, state/, CLAUDE.md, edit config/strategy.json and request
actions via state/tg_action.json. No shell, no web, no code edits, no Meta tokens.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notify  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAT = os.path.join(ROOT, "state", "tg_chat.json")
ACTION = os.path.join(ROOT, "state", "tg_action.json")
STRATEGY = os.path.join(ROOT, "config", "strategy.json")

SYSTEM = """You are Claude, the operator of Bounce Arena: an automated Instagram (@bouncearena.tv) + Facebook Page channel that posts code-generated physics battle Reels for US/UK/CA/AU. Formats: "escape" (balls escape rotating rings with gaps, first out wins) and "grow" (each wall bounce grows the ball, first to target size wins). Themes: "countries" or "colors". GitHub Actions posts 4x/day (UTC 09:30, 16:00, 22:30, 01:30) and runs analytics every 6h. Goal: 5k followers + 250k views by 2026-10-21, $0 budget.

You are chatting with the owner on Telegram. Reply in Turkish, warm and natural like a teammate, short (plain text, no markdown tables, max ~12 lines).

What you can do:
- Read CLAUDE.md, config/strategy.json, state/summary.md (latest metrics), state/changelog.md, state/requests.json, state/posts.json.
- Edit config/strategy.json. Keep valid JSON and the exact schema. Keys: formats.{escape,grow}.weight (relative), teams [min,max], escape: rings [min,max], gap_deg [min,max] (bigger = faster races), spin; grow: grow_step, target_r; seconds [min,max] target race length; themes {countries: w, colors: w}; countries_core (always favored), countries_extra; colors; champion_rematch_prob; hooks.{escape,grow} (hooks with {champ} are only used for rematches; {a},{b} = first two teams); cta (end-card line); caption templates ({hook},{request_line},{tags}); tags_core, tags_rotating; music_keys.
- Trigger actions by writing state/tg_action.json: {"actions":[{"type":"post"|"preview","mode":"escape|grow or empty","theme":"countries|colors or empty"}]}. "post" renders and publishes now to IG+FB; "preview" renders without publishing and sends the video to Telegram.

You cannot change code, visuals, posting times, or run commands. If a request needs that, say so briefly and tell the owner to ask the desktop Claude Code session; offer the closest thing you can do via strategy.json. Never invent numbers: quote state/summary.md. After changes, say exactly what you changed."""


def load(path, default):
    try:
        with open(path, encoding="utf8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def main():
    msg = os.environ["MSG"].strip()
    hist = load(CHAT, [])
    if msg.lower() in ("/reset", "/start"):
        json.dump([], open(CHAT, "w", encoding="utf8"))
        notify.text("Sohbet geçmişini sıfırladım. Merhaba! Durumu sorabilir, strateji değişikliği isteyebilir ya da \"şimdi paylaş\" diyebilirsin.")
        return
    convo = "\n".join(f"Owner: {h['u']}\nYou: {h['a']}" for h in hist[-8:])
    prompt = f"{SYSTEM}\n\n## Recent conversation\n{convo or '(none)'}\n\n## New message from owner\n{msg}"
    if os.path.exists(ACTION):
        os.remove(ACTION)
    before = open(STRATEGY, encoding="utf8").read()
    env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "TELEGRAM_TOKEN")}
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--model", "sonnet", "--max-turns", "12",
           "--allowedTools", "Read(./config/**)", "Read(./state/**)", "Read(./CLAUDE.md)",
           "Edit(./config/strategy.json)", "Write(./state/tg_action.json)",
           "--disallowedTools", "Bash", "WebFetch", "WebSearch", "Task", "NotebookEdit"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600, cwd=ROOT)
        reply = json.loads(r.stdout)["result"]
    except Exception as e:
        tail = locals().get("r")
        reply = f"⚠️ Claude çalışırken hata oldu: {(tail.stderr or tail.stdout)[-400:] if tail else e}"
    try:
        json.load(open(STRATEGY, encoding="utf8"))
    except ValueError:
        open(STRATEGY, "w", encoding="utf8").write(before)
        reply += "\n\n⚠️ strategy.json geçersiz hale geldi, değişikliği geri aldım."
    hist.append({"t": time.strftime("%Y-%m-%d %H:%M"), "u": msg[:1500], "a": reply[:1500]})
    json.dump(hist[-20:], open(CHAT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    # commit before triggering posts so they check out the new strategy
    git("add", "config/strategy.json", "state/tg_chat.json")
    if git("diff", "--cached", "--quiet").returncode:
        git("commit", "-qm", f"telegram: {msg[:60]}")
        git("pull", "-q", "--rebase")
        git("push", "-q")
    acts = load(ACTION, {}).get("actions", [])
    notes = []
    for a in acts[:3]:
        typ = a.get("type")
        if typ not in ("post", "preview"):
            continue
        args = ["gh", "workflow", "run", "post", "-f", f"dry_run={'false' if typ == 'post' else 'true'}"]
        if a.get("mode") in ("escape", "grow"):
            args += ["-f", f"mode={a['mode']}"]
        if a.get("theme") in ("countries", "colors"):
            args += ["-f", f"theme={a['theme']}"]
        ok = subprocess.run(args, cwd=ROOT).returncode == 0
        notes.append(f"{'▶️' if ok else '⚠️'} {typ} {a.get('mode') or ''} {'başlatıldı (~3 dk)' if ok else 'başlatılamadı'}")
    if os.path.exists(ACTION):
        os.remove(ACTION)
    notify.text(reply + ("\n\n" + "\n".join(notes) if notes else ""))


if __name__ == "__main__":
    main()
