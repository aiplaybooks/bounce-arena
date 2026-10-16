"""Schedules every not-yet-scheduled video in PAYLASILACAK/ on the Facebook Page, one per Instagram cron slot, in queue order."""
import datetime as dt
import sys

import publish
import run
import mkqueue

SLOTS = [(1, 30), (9, 30), (12, 30), (16, 0), (19, 0), (22, 30)]  # same UTC slots as post.yml


def upcoming(after):
    day = after.replace(hour=0, minute=0, second=0, microsecond=0)
    while True:
        for h, m in SLOTS:
            t = day.replace(hour=h, minute=m)
            if t > after:
                yield t
        day += dt.timedelta(days=1)


def main():
    q = run.load_queue()
    slots = upcoming(dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=20))
    for it in run.pending(q):
        t = next(slots)  # slot k is also when Instagram posts the k-th pending video
        if it.get("fb_id"):
            continue
        try:
            it["fb_id"] = publish.fb_reel(run.os.path.join(run.PDIR, it["file"]), it["job"]["caption"], t.timestamp())
            it["fb_scheduled_utc"] = t.strftime("%Y-%m-%d %H:%M")
            print("scheduled", it["file"], it["fb_scheduled_utc"], it["fb_id"])
        except Exception as e:
            it["fb_error"] = str(e)[:300]
            print("FAILED", it["file"], e)
            mkqueue.save(q)
            sys.exit(1)
        mkqueue.save(q)


if __name__ == "__main__":
    main()
