"""Publishes a local MP4 as a Reel to Instagram (IG Login API, fetched from a release URL) and the Facebook Page (binary upload)."""
import os
import subprocess
import time

import requests

V = "v23.0"
IG = f"https://graph.instagram.com/{V}"
FB = f"https://graph.facebook.com/{V}"


def _check(r):
    if r.status_code >= 400:
        raise RuntimeError(f"{r.request.method} {r.url.split('?')[0]} -> {r.status_code}: {r.text[:400]}")
    return r.json()


def _release_asset(path):
    """Hosts the mp4 on the repo's public 'media' release; IG fetches it by URL."""
    repo = os.environ["GITHUB_REPOSITORY"]
    subprocess.run(["gh", "release", "upload", "media", path, "--clobber", "-R", repo], check=True)
    return f"https://github.com/{repo}/releases/download/media/{os.path.basename(path)}"


def _drop_asset(path):
    subprocess.run(["gh", "release", "delete-asset", "media", os.path.basename(path), "-y", "-R", os.environ["GITHUB_REPOSITORY"]])


def ig_reel(path, caption, thumb_ms):
    tok, uid = os.environ["IG_TOKEN"], os.environ["IG_USER_ID"]
    url = _release_asset(path)
    try:
        c = _check(requests.post(f"{IG}/{uid}/media", data={
            "media_type": "REELS", "video_url": url, "caption": caption,
            "share_to_feed": "true", "thumb_offset": str(thumb_ms), "access_token": tok}))
        cid = c["id"]
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
    finally:
        _drop_asset(path)


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


def ig_comment(media_id, message):
    return _check(requests.post(f"{IG}/{media_id}/comments", data={"message": message, "access_token": os.environ["IG_TOKEN"]}))["id"]


def fb_comment(video_id, message):
    return _check(requests.post(f"{FB}/{video_id}/comments", data={"message": message, "access_token": os.environ["FB_PAGE_TOKEN"]}))["id"]
