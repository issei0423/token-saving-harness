"""Markdown ファイルのトークン数を、Anthropic の count_tokens（数えるだけの API）で測る。

使い方（キーは環境変数 ANTHROPIC_API_KEY から読む。値は表示しない）：
    python token/measure/count_tokens.py before.md after.md
    python token/measure/count_tokens.py --model claude-sonnet-5-5 --json core/graph.md

「常時読み込まれる量」の目安として、分割前と分割後を比べる。
`/context` の実測は、セッション全体（システム、道具、他の規則を含む）なので、これとは別に取る。

キーは 1 回の呼び出しの中だけで渡す。ユーザーの環境変数に常設すると、Claude Code が契約のログインでなく
そのキーを使うようになる。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

URL = "https://api.anthropic.com/v1/messages/count_tokens"
DEFAULT_MODEL = "claude-sonnet-5-5"


def count(text, model, key):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": text}]}).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["input_tokens"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        sys.exit("ANTHROPIC_API_KEY が無い。1 回の呼び出しの中だけで環境変数に入れて実行する（値は表示しない）")

    rows = []
    for path in a.files:
        text = open(path, encoding="utf-8").read()
        try:
            n = count(text, a.model, key)
        except urllib.error.HTTPError as e:
            # 本文（キーを含みうる）は出さず、状態だけ
            sys.exit(f"{path}: HTTP {e.code}（モデル名かキーを確かめる）")
        rows.append({"file": path, "chars": len(text), "tokens": n})

    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    print(f"{'ファイル':40s} {'文字数':>8s} {'トークン':>9s} {'1字あたり':>8s}")
    for r in rows:
        per = r["tokens"] / r["chars"] if r["chars"] else 0
        print(f"{r['file']:40s} {r['chars']:8,d} {r['tokens']:9,d} {per:8.2f}")
    if len(rows) >= 2 and rows[0]["tokens"]:
        d = rows[0]["tokens"] - rows[1]["tokens"]
        print(f"差（1 番目 − 2 番目）: {d:,d} トークン（{d / rows[0]['tokens'] * 100:.0f}% 減）")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
