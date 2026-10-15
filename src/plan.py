"""Picks the next post: format, teams, hook, caption, and a seed that gives a close race."""
import json
import os
import random
import time

import physics
from render import ARENA_R, CX, CY, PALETTE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(rel, default):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf8") as f:
        return json.load(f)


def wpick(rng, weights):
    keys = list(weights)
    return rng.choices(keys, [weights[k] if isinstance(weights[k], (int, float)) else weights[k]["weight"] for k in keys])[0]


def explore(rng, weights, posts, field, n=3):
    """Any option with weight > 0 but fewer than n posts goes first, so every variant gets data."""
    low = [k for k in weights if wpick_w(weights[k]) > 0 and sum(p.get(field) == k for p in posts) < n]
    return rng.choice(low) if low else wpick(rng, weights)


def wpick_w(v):
    return v if isinstance(v, (int, float)) else v["weight"]


def make_job(force_mode=None, force_theme=None):
    st = load("config/strategy.json", {})
    posts = load("state/posts.json", [])
    requests = load("state/requests.json", {})
    rng = random.Random(time.time_ns())
    mode = force_mode or explore(rng, st["formats"], posts, "mode")
    fm = st["formats"][mode]
    theme = force_theme or explore(rng, st["themes"], posts, "theme")
    n = rng.randint(*fm["teams"])
    champ = None
    request_line = ""
    if theme == "countries":
        last = next((p for p in reversed(posts) if p.get("theme") == "countries" and p.get("winner")), None)
        picks = []
        if last and rng.random() < st["champion_rematch_prob"]:
            champ = last["winner"]
            picks.append(champ)
        asked = [c for c, _ in sorted(requests.items(), key=lambda kv: -kv[1]) if c not in picks][:1]
        if asked:
            picks += asked
            request_line = f"\nYou asked for {asked[0]} — they're in! 🔥"
        core = [c for c in st["countries_core"] if c not in picks]
        rng.shuffle(core)
        picks += core[: max(0, min(len(core), n - len(picks) - 1))]
        extra = [c for c in st["countries_extra"] if c not in picks]
        rng.shuffle(extra)
        picks += extra[: n - len(picks)]
        teams = picks[:n]
        rng.shuffle(teams)
        colors = PALETTE[:]
        rng.shuffle(colors)
        colors = colors[:n]
    else:
        idx = list(range(len(st["colors"])))
        rng.shuffle(idx)
        idx = idx[:n]
        teams = [st["colors"][i] for i in idx]
        colors = [PALETTE[i] for i in idx]
    hooks = [h for h in st["hooks"][mode] if ("{champ}" in h) == bool(champ)]
    if theme != "countries":
        hooks = [h.replace("country", "color") for h in hooks]
    hook = rng.choice(hooks).format(a=teams[0], b=teams[1], champ=champ)
    params = {}
    if mode == "escape":
        params = {"rings": rng.randint(*fm["rings"]), "gap_deg": rng.uniform(*fm["gap_deg"]), "spin": tuple(fm["spin"])}
    else:
        params = {"grow_step": rng.uniform(*fm["grow_step"]), "target_r": rng.uniform(*fm["target_r"]), "ball_r": 34.0}
    seed = find_seed(mode, teams, params, fm["seconds"], rng)
    tags = st["tags_core"] + rng.sample(st["tags_rotating"], 2)
    caption = rng.choice(st["caption"]).format(hook=hook, request_line=request_line, tags=" ".join(tags))
    first = rng.choice(st.get("first_comment") or [""]).format(a=teams[0], b=teams[1])
    return {
        "id": time.strftime("%Y%m%d-%H%M%S", time.gmtime()),
        "mode": mode, "theme": theme, "teams": teams, "colors": colors, "hook": hook,
        "cta": rng.choice(st["cta"]), "caption": caption, "first_comment": first, "params": params, "seed": seed,
        "key": rng.choice(st["music_keys"]), "champ": champ, "requested": request_line != "",
    }


def find_seed(mode, teams, params, seconds, rng, tries=120):
    lo, hi = seconds
    best, best_score = None, 1e9
    base = rng.randint(0, 10 ** 6)
    for s in range(base, base + tries):
        st = physics.race_stats(mode, teams, s, CX, CY, ARENA_R, params)
        if not st:
            continue
        # prefer races inside the target window with a close runner-up
        out = max(0, lo - st["t"]) + max(0, st["t"] - hi)
        score = out * 10 + st["runner_up_gap"] * 3 - st["movers"] * 0.2
        if score < best_score:
            best, best_score = s, score
        if out == 0 and st["runner_up_gap"] <= 1:
            return s
    return best
