"""One posting cycle: plan -> simulate -> audio -> render -> publish -> log.

python src/run.py [--dry-run] [--preview] [--mode escape|grow] [--theme countries|colors]
"""
import argparse
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audio  # noqa: E402
import physics  # noqa: E402
import plan  # noqa: E402
import render  # noqa: E402

ROOT = plan.ROOT
OUT = os.path.join(ROOT, "out")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--preview", action="store_true", help="only write 3 PNG stills, no video")
    ap.add_argument("--mode")
    ap.add_argument("--theme")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    job = plan.make_job(a.mode, a.theme)
    sim = physics.simulate(job["mode"], job["teams"], job["seed"], render.CX, render.CY, render.ARENA_R, job["params"])
    if sim is None:
        sys.exit("no winner within time limit")
    frames, events, winner, win_t = sim
    job["winner"] = job["teams"][winner]
    job["win_t"] = round(win_t, 2)
    job["duration"] = round(len(frames) / physics.FPS, 2)
    print(json.dumps({k: job[k] for k in ("id", "mode", "theme", "teams", "hook", "winner", "win_t", "duration")}))
    if a.preview:
        render.render(sim, job, None, None, preview_dir=os.path.join(OUT, "preview"))
        return
    wav, mp4 = os.path.join(OUT, f"{job['id']}.wav"), os.path.join(OUT, f"{job['id']}.mp4")
    audio.build(events, job["duration"], wav, job["key"])
    render.render(sim, job, mp4, wav)
    if a.dry_run:
        return
    import publish
    thumb_ms = int(min(win_t * 0.5, 4.0) * 1000)
    for net, fn in (("ig_id", lambda: publish.ig_reel(mp4, job["caption"], thumb_ms)),
                    ("fb_id", lambda: publish.fb_reel(mp4, job["caption"]))):
        try:
            job[net] = fn()
        except Exception as e:  # one network failing must not block the other
            traceback.print_exc()
            job[net + "_error"] = str(e)[:300]
    log_post(job)
    if "ig_id" not in job and "fb_id" not in job:
        sys.exit("both publishes failed")


def log_post(job):
    p = os.path.join(ROOT, "state", "posts.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    posts = json.load(open(p, encoding="utf8")) if os.path.exists(p) else []
    import time
    job["posted_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    posts.append(job)
    with open(p, "w", encoding="utf8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
