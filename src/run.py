"""One posting cycle: plan -> simulate -> audio -> render -> publish -> log.

python src/run.py [--dry-run] [--preview] [--mode escape|grow] [--theme countries|colors]
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
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
    ap.add_argument("--only", choices=["ig", "fb"], help="publish to one network")
    ap.add_argument("--queue-first", action="store_true", help="publish the next ready-made video from PAYLASILACAK/ if any")
    ap.add_argument("--render-to", help="render one finished video + job json into this folder (no publishing); use with --name")
    ap.add_argument("--name")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.queue_first:
        queue_cycle()
        return
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
    if a.render_to:
        os.makedirs(a.render_to, exist_ok=True)
        mp4 = os.path.join(a.render_to, a.name + ".mp4")
        job["file"] = a.name + ".mp4"
    audio.build(events, job["duration"], wav, job["key"])
    render.render(sim, job, mp4, wav)
    if a.render_to:
        with open(os.path.join(a.render_to, a.name + ".json"), "w", encoding="utf8") as f:
            json.dump(job, f, ensure_ascii=False, indent=1)
        return
    if a.dry_run:
        import notify
        notify.video(mp4, f"👀 Önizleme (yayınlanmadı)\n{job['hook']}\n{job['mode']}/{job['theme']} · winner {job['winner']} · {job['duration']}s")
        return
    import publish
    thumb_ms = int(min(win_t * 0.5, 4.0) * 1000)
    for net, fn in (("ig_id", lambda: publish.ig_reel(mp4, job["caption"], thumb_ms)),
                    ("fb_id", lambda: publish.fb_reel(mp4, job["caption"]))):
        if a.only and not net.startswith(a.only):
            continue
        for attempt in (1, 2):  # one retry: transient Meta errors are common
            try:
                job[net] = fn()
                job.pop(net + "_error", None)
                break
            except Exception as e:  # one network failing must not block the other
                traceback.print_exc()
                job[net + "_error"] = str(e)[:300]
                if attempt == 1:
                    time.sleep(30)
    if job.get("first_comment"):
        for net, fn in (("ig", publish.ig_comment), ("fb", publish.fb_comment)):
            if job.get(net + "_id"):
                time.sleep(5)
                try:
                    fn(job[net + "_id"], job["first_comment"])
                except Exception as e:
                    print(f"{net} first comment:", e)
                    job[net + "_comment_error"] = str(e)[:200]
    log_post(job)
    report(job, mp4)
    if "ig_id" not in job and "fb_id" not in job:
        sys.exit("both publishes failed")


PDIR = os.path.join(ROOT, "PAYLASILACAK")
QUEUE = os.path.join(PDIR, "queue.json")
KEEP = 6  # keep at least this many videos ready in PAYLASILACAK/


def load_queue():
    return json.load(open(QUEUE, encoding="utf8")) if os.path.exists(QUEUE) else []


def pending(q):
    return [i for i in q if not i.get("ig_id") and i.get("tries", 0) < 3 and os.path.exists(os.path.join(PDIR, i["file"]))]


def add_video(q):
    """Renders one fresh video into PAYLASILACAK/ (numbering continues from the highest number ever used)."""
    import mkqueue
    for _ in range(4):
        job = plan.make_job()
        sim = physics.simulate(job["mode"], job["teams"], job["seed"], render.CX, render.CY, render.ARENA_R, job["params"])
        if sim:
            break
    else:
        raise RuntimeError("no winner within time limit")
    frames, events, winner, win_t = sim
    job["winner"] = job["teams"][winner]
    job["win_t"] = round(win_t, 2)
    job["duration"] = round(len(frames) / physics.FPS, 2)
    n = max([i["order"] for i in q], default=0) + 1
    name = f"{n:02d}_{job['mode']}_{job['theme']}"
    job["file"] = name + ".mp4"
    os.makedirs(PDIR, exist_ok=True)
    wav = os.path.join(OUT, f"{job['id']}.wav")
    audio.build(events, job["duration"], wav, job["key"])
    render.render(sim, job, os.path.join(PDIR, job["file"]), wav)
    item = {"order": n, "file": job["file"], "job": job}
    q.append(item)
    mkqueue.write_txt(item)
    mkqueue.save(q)
    print("queued", name)


def queue_cycle():
    """Scheduled slot: post the next ready video to Instagram (IG only; Facebook is scheduled by hand), delete it
    from PAYLASILACAK/, then top the folder up with fresh videos."""
    import fb_schedule
    import mkqueue
    q = load_queue()
    lp = fb_schedule.last_post(q)  # the cron fires daily; post only every EVERY_DAYS days
    if lp and dt.datetime.now(dt.timezone.utc) - lp < dt.timedelta(days=fb_schedule.EVERY_DAYS, hours=-6):
        print("skip: last post", lp.isoformat(), "- posting every", fb_schedule.EVERY_DAYS, "days")
        return
    if not pending(q):
        add_video(q)  # nothing ready: make one now so this slot still posts
    publish_next(q)
    for _ in range(2):
        if len(pending(q)) >= KEEP:
            break
        try:
            add_video(q)
        except Exception:
            traceback.print_exc()
            break
    # every ready video also gets scheduled on the Facebook Page, in queue order
    for it in pending(q):
        if not it.get("fb_id") and it.get("fb_tries", 0) < 3:
            fb_schedule.schedule_item(q, it, PDIR)
    mkqueue.save(q)


def publish_next(q):
    import mkqueue
    import publish
    item = pending(q)[0]
    job = item["job"]
    mp4 = os.path.join(PDIR, item["file"])
    item["tries"] = item.get("tries", 0) + 1
    thumb_ms = int(min(job["win_t"] * 0.5, 4.0) * 1000)
    try:
        item["ig_id"] = job["ig_id"] = publish.ig_reel(mp4, job["caption"], thumb_ms)
        item.pop("error", None)
    except Exception as e:
        traceback.print_exc()
        item["error"] = str(e)[:300]
        mkqueue.save(q)
        sys.exit("queue publish failed")
    if job.get("first_comment"):
        time.sleep(5)
        try:
            publish.ig_comment(item["ig_id"], job["first_comment"])
        except Exception as e:
            print("ig first comment:", e)
    job["posted_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log_post(job)
    try:
        report(job, mp4)
    except Exception as e:
        print("report failed:", e)
    for ext in (".mp4", ".txt"):  # posted: take it out of the folder
        try:
            os.remove(os.path.join(PDIR, item["file"][:-4] + ext))
        except OSError:
            pass
    mkqueue.save(q)


def report(job, mp4):
    import notify
    import publish
    import requests
    lines = [f"🎬 {job['hook']}", f"{job['mode']}/{job['theme']} · winner {job['winner']} · {job['duration']}s"]
    if job.get("ig_id"):
        try:
            link = requests.get(f"{publish.IG}/{job['ig_id']}", params={"fields": "permalink", "access_token": os.environ["IG_TOKEN"]}, timeout=20).json().get("permalink")
        except Exception:
            link = None
        lines.append(f"IG ✅ {link or job['ig_id']}")
    if job.get("fb_id"):
        lines.append(f"FB ✅ https://www.facebook.com/reel/{job['fb_id']}")
    for net in ("ig_id", "fb_id"):
        if job.get(net + "_error"):
            lines.append(f"{net[:2].upper()} ❌ {job[net + '_error'][:200]}")
    lines += ["", job["caption"]]
    notify.video(mp4, "\n".join(lines))


def log_post(job):
    p = os.path.join(ROOT, "state", "posts.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    posts = json.load(open(p, encoding="utf8")) if os.path.exists(p) else []
    job["posted_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    posts.append(job)
    with open(p, "w", encoding="utf8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
