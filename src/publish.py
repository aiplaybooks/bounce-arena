"""Publishes a local MP4 as a Reel to Instagram (IG Login API) and the Facebook Page (binary uploads, no hosting)."""
import os
import time

import requests

V = "v23.0"
IG = f"https://graph.instagram.com/{V}"
FB = f"https://graph.facebook.com/{V}"


def _check(r):
    if r.status_code >= 400:
        raise RuntimeError(f"{r.request.method} {r.url.split('?')[0]} -> {r.status_code}: {r.text[:400]}")
    return r.json()


def ig_reel(path, caption, thumb_ms):
    tok, uid = os.environ["IG_TOKEN"], os.environ["IG_USER_ID"]
    c = _check(requests.post(f"{IG}/{uid}/media", data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption,
        "share_to_feed": "true", "thumb_offset": str(thumb_ms), "access_token": tok}))
    cid = c["id"]
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        _check(requests.post(c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{V}/{cid}", data=f, headers={
            "Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)}))
    for _ in range(60):
        s = _check(requests.get(f"{IG}/{cid}", params={"fields": "status_code,status", "access_token": tok}))
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError(f"IG processing error: {s}")
        time.sleep(10)
    else:
        raise RuntimeError("IG processing timeout")
    pub = _check(requests.post(f"{IG}/{uid}/media_publish", data={"creation_id": cid, "access_token": tok}))
    return pub["id"]


def fb_reel(path, description):
    tok, pid = os.environ["FB_PAGE_TOKEN"], os.environ["FB_PAGE_ID"]
    st = _check(requests.post(f"{FB}/{pid}/video_reels", data={"upload_phase": "start", "access_token": tok}))
    vid = st["video_id"]
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        _check(requests.post(st.get("upload_url") or f"https://rupload.facebook.com/video-upload/{V}/{vid}", data=f, headers={
            "Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)}))
    _check(requests.post(f"{FB}/{pid}/video_reels", data={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
        "description": description, "access_token": tok}))
    return vid
