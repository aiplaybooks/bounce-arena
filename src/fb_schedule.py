"""Schedules every not-yet-scheduled video in PAYLASILACAK/ on the Facebook Page, one per Instagram slot (every EVERY_DAYS days), in queue order."""
import datetime as dt
import sys

import publish

SLOTS = [(16, 0)]  # same UTC slot as post.yml (19:00 Turkey time, best IG hour in analytics)
EVERY_DAYS = 2  # one post every 2 days (owner, 2026-10-19)


def last_post(q):
    """UTC time of the last Instagram post in the queue (None if nothing posted yet)."""
    ts = [i["job"]["posted_utc"] for i in q if i.get("ig_id") and i.get("job", {}).get("posted_utc")]
    return dt.datetime.strptime(max(ts), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) if ts else None


def upcoming(after, q=None):
    """Slots after `after`, EVERY_DAYS apart, starting EVERY_DAYS after the last Instagram post."""
    day = after.replace(hour=0, minute=0, second=0, microsecond=0)
    lp = last_post(q or [])
    if lp:
        day = max(day, lp.replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(days=EVERY_DAYS))
    while True:
        for h, m in SLOTS:
            t = day.replace(hour=h, minute=m)
            if t > after:
                yield t
        day += dt.timedelta(days=EVERY_DAYS)


def next_slot(q):
    """First Instagram slot after everything already scheduled (the queue posts in order, so FB follows the same order)."""
    now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15)
    last = max([dt.datetime.strptime(i["fb_scheduled_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
                for i in q if i.get("fb_scheduled_utc") and not i.get("ig_id")] + [now])
    return next(upcoming(max(now, last), q))


def schedule_item(q, item, pdir):
    import os
    t = next_slot(q)
    try:
        item["fb_id"] = publish.fb_reel(os.path.join(pdir, item["file"]), item["job"]["caption"], t.timestamp())
        item["fb_scheduled_utc"] = t.strftime("%Y-%m-%d %H:%M")
        item.pop("fb_error", None)
        print("fb scheduled", item["file"], item["fb_scheduled_utc"])
        return True
    except Exception as e:
        item["fb_error"] = str(e)[:300]
        item["fb_tries"] = item.get("fb_tries", 0) + 1
        print("fb schedule failed", item["file"], e)
        return False


def main():
    import mkqueue
    import run
    q = run.load_queue()
    slots = upcoming(dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=20), q)
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
