#!/usr/bin/env bash
# install.sh の試験。PASS／FAIL を出し、FAIL があれば終了コード 1。
# CLAUDE_CONFIG_DIR を一時フォルダへ向ける（本物の ~/.claude には触れない）。
here=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d 2>/dev/null || mktemp -d -t inst)
trap 'rm -rf "$tmp"' EXIT
fails=0
report() { if [ "$2" = 0 ]; then echo "PASS: $1"; else echo "FAIL: $1${3:+（$3）}"; fails=$((fails + 1)); fi; }
conf="$tmp/conf"
n_src=$(ls "$here"/core/agents/*.md | wc -l | tr -d ' ')

# 1) 既定は計画だけ。何も書かない
out=$(CLAUDE_CONFIG_DIR="$conf" bash "$here/install.sh" 2>&1); code=$?
[ "$code" = 0 ] && [ ! -e "$conf" ]; report "引数なしは何も書かない（終了コード 0）" $? "code=$code"
[ "$(printf '%s\n' "$out" | grep -c '\[新しく写す\]')" = "$n_src" ]; report "計画に係の文書が全部（$n_src 件）出る" $? "$out"
printf '%s\n' "$out" | grep -q 'statusLine' && printf '%s\n' "$out" | grep -q 'claude-md-snippet.md'; report "貼る文（CLAUDE.md・statusLine）を表示する" $?

# 2) --apply で写す
mkdir -p "$conf/agents"
echo "mine" > "$conf/agents/my-own-agent.md"
out=$(CLAUDE_CONFIG_DIR="$conf" bash "$here/install.sh" --apply 2>&1); code=$?
ok=0; for f in "$here"/core/agents/*.md; do cmp -s "$f" "$conf/agents/$(basename "$f")" || ok=1; done
[ "$code" = 0 ] && [ "$ok" = 0 ]; report "--apply で係の文書が同じ中身で写る" $? "code=$code $out"
[ "$(cat "$conf/agents/my-own-agent.md")" = "mine" ]; report "もとからある別の係の文書には触れない" $?
[ ! -e "$conf/agents-backup" ]; report "置き換えが無ければ退避のフォルダを作らない" $?

# 3) もう一度回しても何も変わらない
out=$(CLAUDE_CONFIG_DIR="$conf" bash "$here/install.sh" --apply 2>&1); code=$?
[ "$code" = 0 ] && [ "$(printf '%s\n' "$out" | grep -c '\[同じ。飛ばす\]')" = "$n_src" ] && [ ! -e "$conf/agents-backup" ]
report "2回目は全部「同じ。飛ばす」" $? "$out"

# 4) 中身の違う同じ名前のファイルは、退避してから置き換える
echo "old researcher" > "$conf/agents/researcher.md"
out=$(CLAUDE_CONFIG_DIR="$conf" bash "$here/install.sh" 2>&1)
[ "$(cat "$conf/agents/researcher.md")" = "old researcher" ]; report "計画だけのときは置き換えない" $?
out=$(CLAUDE_CONFIG_DIR="$conf" bash "$here/install.sh" --apply 2>&1); code=$?
kept=$(cat "$conf"/agents-backup/*/researcher.md 2>/dev/null)
[ "$code" = 0 ] && [ "$kept" = "old researcher" ] && cmp -s "$here/core/agents/researcher.md" "$conf/agents/researcher.md"
report "違う中身は agents-backup へ退避してから置き換える" $? "kept=$kept $out"

# 5) 知らない引数は終了コード 2 で、何も書かない
CLAUDE_CONFIG_DIR="$tmp/conf2" bash "$here/install.sh" --nazo >/dev/null 2>&1; code=$?
[ "$code" = 2 ] && [ ! -e "$tmp/conf2" ]; report "知らない引数は終了コード 2" $? "code=$code"

echo "合計 FAIL $fails"
[ "$fails" = 0 ]
