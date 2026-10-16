"""Merges the per-video job files in PAYLASILACAK/ into queue.json (+ one caption .txt per video + PLAN.md).

Re-running keeps ig_id / tries of items that were already published.
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "PAYLASILACAK")


def write_txt(item):
    job = item["job"]
    with open(os.path.join(D, item["file"][:-4] + ".txt"), "w", encoding="utf8") as f:
        f.write(job["caption"] + "\n\n--- first comment ---\n" + job.get("first_comment", "") + "\n")


def write_plan(q):
    pend = [i for i in q if not i.get("ig_id")]
    rows = ["# PAYLASILACAK - bekleyen videolar", "",
            "Instagram: GitHub Actions siradaki videoyu otomatik paylasir, paylasilinca video ve .txt buradan silinir. Yeni videolar son numaradan devam eder.",
            "Facebook: videoyu ve ayni isimli .txt'deki aciklamayi, IG'de paylasilmadan once Page'den planla.", "",
            f"Paylasilan: {len(q) - len(pend)} - Bekleyen: {len(pend)}", "",
            "| # | video | tema | sure | kazanan | hook |", "|---|---|---|---|---|---|"]
    for it in pend:
        j = it["job"]
        rows.append(f"| {it['order']} | {it['file']} | {j['mode']}/{j['theme']} | {j['duration']}s | {j['winner']} | {j['hook']} |")
    with open(os.path.join(D, "PLAN.md"), "w", encoding="utf8") as f:
        f.write("\n".join(rows) + "\n")


def save(q):
    with open(os.path.join(D, "queue.json"), "w", encoding="utf8") as f:
        json.dump(q, f, ensure_ascii=False, indent=1)
    write_plan(q)


def main():
    qp = os.path.join(D, "queue.json")
    old = {i["file"]: i for i in json.load(open(qp, encoding="utf8"))} if os.path.exists(qp) else {}
    q = []
    for jp in sorted(glob.glob(os.path.join(D, "*.json"))):
        name = os.path.basename(jp)
        if name == "queue.json":
            continue
        job = json.load(open(jp, encoding="utf8"))
        file = name[:-5] + ".mp4"
        if not os.path.exists(os.path.join(D, file)):
            continue
        item = {"order": len(q) + 1, "file": file, "job": job}
        if file in old:
            for k in ("ig_id", "tries", "error"):
                if k in old[file]:
                    item[k] = old[file][k]
        q.append(item)
        write_txt(item)
        os.remove(jp)
    save(q)
    print(f"{len(q)} videos queued")


if __name__ == "__main__":
    main()
