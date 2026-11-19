"""Markdown ファイルの文字数とバイト数（UTF-8）を数える。"""
import argparse
import json
import sys


def count(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return {"path": path, "chars": len(text), "bytes": len(text.encode("utf-8"))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("files", nargs="+", help="Markdown ファイルのパス")
    p.add_argument("--json", action="store_true", help="JSON で出力する")
    args = p.parse_args()
    rows = [count(f) for f in args.files]
    total = {"chars": sum(r["chars"] for r in rows), "bytes": sum(r["bytes"] for r in rows)}
    if args.json:
        print(json.dumps({"files": rows, "total": total}, ensure_ascii=False, indent=2))
        return
    w = max(len(r["path"]) for r in rows + [{"path": "合計"}])
    print(f"{'ファイル':<{w}}  {'文字数':>8}  {'バイト数':>8}")
    for r in rows:
        print(f"{r['path']:<{w}}  {r['chars']:>8,}  {r['bytes']:>8,}")
    print(f"{'合計':<{w}}  {total['chars']:>8,}  {total['bytes']:>8,}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
