"""Merges the per-video job files in PAYLASILACAK/ into queue.json (+ one caption .txt per video + PLAN.md).

Re-running keeps ig_id / tries of items that were already published.
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "PAYLASILACAK")


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
                    if k == "ig_id":
                        job["ig_id"] = old[file][k]
        q.append(item)
        with open(os.path.join(D, name[:-5] + ".txt"), "w", encoding="utf8") as f:
            f.write(job["caption"] + "\n\n--- first comment ---\n" + job.get("first_comment", "") + "\n")
        os.remove(jp)
    for i, it in enumerate(q, 1):
        it["order"] = i
    with open(qp, "w", encoding="utf8") as f:
        json.dump(q, f, ensure_ascii=False, indent=1)
    rows = ["# PAYLASILACAK - yayin sirasi", "", "Instagram: GitHub Actions sirayla otomatik paylasir (queue.json). Facebook: ayni sirayla, ayni isimli .txt'deki aciklamayla Page'den planla.", "",
            "| # | video | tema | sure | kazanan | hook | IG |", "|---|---|---|---|---|---|---|"]
    for it in q:
        j = it["job"]
        rows.append(f"| {it['order']} | {it['file']} | {j['mode']}/{j['theme']} | {j['duration']}s | {j['winner']} | {j['hook']} | {'paylasildi' if it.get('ig_id') else 'bekliyor'} |")
    with open(os.path.join(D, "PLAN.md"), "w", encoding="utf8") as f:
        f.write("\n".join(rows) + "\n")
    print(f"{len(q)} videos queued")


if __name__ == "__main__":
    main()
