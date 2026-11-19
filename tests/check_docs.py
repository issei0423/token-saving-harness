#!/usr/bin/env python3
"""文書の点検。PASS／FAIL を出し、FAIL があれば終了コード 1。

1. 核（core/graph.md）が 5,000 字以内（常時読む分を小さく保つ）
2. 文書が指す ~/.claude/token-harness/<パス> が、このリポジトリにある
3. 核の「→ 読む」の合図の文書が core/graph/ にある
4. 係の文書の頭に name・description・tools・model がある
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 5000
fails = 0


def report(label, ok, note=""):
    global fails
    fails += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}: {label}{'（' + note + '）' if note and not ok else ''}")


core = (ROOT / "core" / "graph.md").read_text(encoding="utf-8")
report(f"core/graph.md は {LIMIT:,} 字以内（いま {len(core):,} 字）", len(core) <= LIMIT)

# 2. ~/.claude/token-harness/ の下を指すパス
texts = [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and p.suffix in (".md", ".sh", ".py", ".json")]
missing = []
for p in texts:
    for m in re.finditer(r"~/\.claude/token-harness/([A-Za-z0-9_./-]+)", p.read_text(encoding="utf-8")):
        rel = m.group(1).rstrip("./")
        if rel.startswith("runs") or not rel:
            continue  # 状態ファイルの置き場（リポジトリには入れない）
        if not (ROOT / rel).exists():
            missing.append(f"{p.relative_to(ROOT).as_posix()} → {rel}")
report("文書が指す ~/.claude/token-harness/ の下のパスが全部ある", not missing, "; ".join(missing))

# 3. 「→ 読む」の合図
signals = re.findall(r"→ 読む：`([^`]+)`", core)
bad = [s for s in signals if not (ROOT / "core" / "graph" / s).is_file()]
report(f"核の「→ 読む」の合図（{len(signals)} 件）の文書が core/graph/ にある", bool(signals) and not bad, ", ".join(bad))
orphans = sorted(p.name for p in (ROOT / "core" / "graph").glob("*.md") if p.name not in signals and p.name != "worker-rules.md")
report("core/graph/ の文書は、どれも核から合図で辿れる", not orphans, ", ".join(orphans))

# 4. 係の文書の頭
agents = sorted((ROOT / "core" / "agents").glob("*.md"))
bad = []
for p in agents:
    t = p.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", t, re.S)
    head = dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line) if m else {}
    if not all(k in head for k in ("name", "description", "tools", "model")) or head.get("name", "").strip() != p.stem:
        bad.append(p.name)
report(f"係の文書（{len(agents)} 件）の頭に name・description・tools・model があり、name がファイル名と同じ", len(agents) == 5 and not bad, ", ".join(bad))

print(f"合計 FAIL {fails}")
sys.exit(1 if fails else 0)
