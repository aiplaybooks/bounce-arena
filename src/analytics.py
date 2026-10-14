"""Pulls IG + FB metrics, harvests country requests from comments, writes a compact state/summary.md.

summary.md is the ONLY file Claude needs to read for daily tuning — keep it short.
"""
import json
import os
import re
import time

import requests

V = "v23.0"
IG = f"https://graph.instagram.com/{V}"
FB = f"https://graph.facebook.com/{V}"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOAL_FOLLOWERS, GOAL_VIEWS = 5000, 250000


def get(url, **params):
    try:
        r = requests.get(url, params=params, timeout=30)
        return r.json() if r.status_code < 400 else {"error": r.text[:200]}
    except requests.RequestException as e:
        return {"error": str(e)}


def ig_metrics(mid, tok):
    out = {}
    for m in ("views", "reach", "likes", "comments", "shares", "saved", "ig_reels_avg_watch_time"):
        d = get(f"{IG}/{mid}/insights", metric=m, access_token=tok)
        if "data" in d and d["data"]:
            out[m] = d["data"][0]["values"][0]["value"]
    return out


def fb_metrics(vid, tok):
    out = {}
    d = get(f"{FB}/{vid}/video_insights", access_token=tok)
    for row in d.get("data", []):
        if row["name"] in ("blue_reels_play_count", "post_video_avg_time_watched", "post_impressions_unique", "post_video_followers"):
            out[row["name"]] = row["values"][0]["value"]
    return out


def harvest_requests(posts, ig_tok, countries):
    path = os.path.join(ROOT, "state", "requests.json")
    req = json.load(open(path, encoding="utf8")) if os.path.exists(path) else {}
    seen_path = os.path.join(ROOT, "state", "seen_comments.json")
    seen = set(json.load(open(seen_path))) if os.path.exists(seen_path) else set()
    pats = {c: re.compile(r"\b" + re.escape(c.lower()) + r"\b") for c in countries}
    aliases = {"usa": "USA", "america": "USA", "us": "USA", "uk": "UK", "england": "UK", "britain": "UK", "aussie": "Australia", "canada": "Canada"}
    for p in posts[-15:]:
        if "ig_id" not in p:
            continue
        d = get(f"{IG}/{p['ig_id']}/comments", fields="id,text", limit=100, access_token=ig_tok)
        for c in d.get("data", []):
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            text = c.get("text", "").lower()
            hit = {name for name, rx in pats.items() if rx.search(text)}
            hit |= {v for k, v in aliases.items() if re.search(r"\b" + k + r"\b", text)}
            for h in hit:
                req[h] = req.get(h, 0) + 1
    json.dump(req, open(path, "w", encoding="utf8"), indent=1)
    json.dump(sorted(seen), open(seen_path, "w"))
    return req


def main():
    ig_tok, fb_tok = os.environ["IG_TOKEN"], os.environ["FB_PAGE_TOKEN"]
    posts_path = os.path.join(ROOT, "state", "posts.json")
    posts = json.load(open(posts_path, encoding="utf8")) if os.path.exists(posts_path) else []
    acct = get(f"{IG}/me", fields="followers_count,media_count", access_token=ig_tok)
    page = get(f"{FB}/{os.environ['FB_PAGE_ID']}", fields="followers_count,fan_count", access_token=fb_tok)
    for p in posts:
        if "ig_id" in p:
            p["ig"] = ig_metrics(p["ig_id"], ig_tok)
        if "fb_id" in p:
            p["fb"] = fb_metrics(p["fb_id"], fb_tok)
    json.dump(posts, open(posts_path, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    st = json.load(open(os.path.join(ROOT, "config", "strategy.json"), encoding="utf8"))
    req = harvest_requests(posts, ig_tok, st["countries_core"] + st["countries_extra"])

    def views(p):
        return (p.get("ig", {}).get("views") or 0) + (p.get("fb", {}).get("blue_reels_play_count") or 0)

    igf, fbf = acct.get("followers_count", 0), page.get("followers_count", 0)
    total_views = sum(views(p) for p in posts)
    lines = [
        f"# Summary {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
        f"Followers IG {igf} + FB {fbf} = {igf + fbf} / {GOAL_FOLLOWERS} | Views {total_views} / {GOAL_VIEWS} | Posts {len(posts)}",
        "",
        "| id | mode/theme | hook | views IG/FB | avg watch s IG | likes | cmts | shares | saves |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for p in sorted(posts, key=views, reverse=True)[:12]:
        ig, fb = p.get("ig", {}), p.get("fb", {})
        aw = ig.get("ig_reels_avg_watch_time")
        lines.append(f"| {p['id']} | {p['mode']}/{p['theme']} | {p['hook'][:38]} | {ig.get('views', '-')}/{fb.get('blue_reels_play_count', '-')} | "
                     f"{round(aw / 1000, 1) if aw else '-'} (len {p.get('duration')}) | {ig.get('likes', '-')} | {ig.get('comments', '-')} | {ig.get('shares', '-')} | {ig.get('saved', '-')} |")
    by = {}
    for p in posts:
        k = f"{p['mode']}/{p['theme']}"
        by.setdefault(k, []).append(views(p))
    lines += ["", "Avg views by format: " + ", ".join(f"{k} {sum(v) // max(1, len(v))} (n={len(v)})" for k, v in by.items())]
    errs = [f"{p['id']}: {p.get('ig_id_error') or p.get('fb_id_error')}" for p in posts[-6:] if p.get("ig_id_error") or p.get("fb_id_error")]
    if errs:
        lines += ["", "Recent publish errors:"] + [f"- {e[:160]}" for e in errs]
    if req:
        lines += ["", "Comment requests: " + ", ".join(f"{k} {v}" for k, v in sorted(req.items(), key=lambda kv: -kv[1])[:8])]
    with open(os.path.join(ROOT, "state", "summary.md"), "w", encoding="utf8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:2]))


if __name__ == "__main__":
    main()
