#!/usr/bin/env bash
# 係の定義（core/agents/*.md）を Claude Code の設定フォルダへ写し、手で貼る文を表示する。
#
#   bash install.sh           何をするかを表示するだけ（何も書かない）
#   bash install.sh --apply   写す
#
# - 写す先は ${CLAUDE_CONFIG_DIR:-~/.claude}/agents
# - 同じ名前で中身の違うファイルがあれば、agents-backup/<日時>/ へ退避してから置き換える。消さない
# - CLAUDE.md と settings.json は書き換えない。貼る文を表示するので、自分で貼る
set -u

usage() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; }

apply=0
for a in "$@"; do
  case $a in
    --apply) apply=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "知らない引数：$a"; usage; exit 2 ;;
  esac
done

here=$(cd "$(dirname "$0")" && pwd)
conf=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
dest="$conf/agents"
backup="$conf/agents-backup/$(date +%Y%m%d-%H%M%S)"

# 表示用の絶対パス（Git Bash では C:/… の形にする）
show() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s\n' "$1"; fi; }

if [ "$apply" = 1 ]; then echo "== 写す（--apply）"; else echo "== 計画（何も書かない。写すには --apply）"; fi
echo "写す先：$(show "$dest")"

new=0; same=0; replaced=0; failed=0
for f in "$here"/core/agents/*.md; do
  [ -e "$f" ] || { echo "core/agents に係の文書が無い"; exit 1; }
  name=$(basename "$f")
  if [ ! -e "$dest/$name" ]; then
    echo "  [新しく写す] $name"
    if [ "$apply" = 1 ]; then
      mkdir -p "$dest" && cp "$f" "$dest/$name" || { echo "    失敗した"; failed=$((failed + 1)); continue; }
    fi
    new=$((new + 1))
  elif cmp -s "$f" "$dest/$name"; then
    echo "  [同じ。飛ばす] $name"
    same=$((same + 1))
  else
    echo "  [退避してから置き換える] $name → agents-backup/$(basename "$backup")/"
    if [ "$apply" = 1 ]; then
      mkdir -p "$backup" && cp "$dest/$name" "$backup/$name" && cp "$f" "$dest/$name" || { echo "    失敗した"; failed=$((failed + 1)); continue; }
    fi
    replaced=$((replaced + 1))
  fi
done
echo "合計：新しく $new・同じ $same・置き換え $replaced・失敗 $failed"

want="$HOME/.claude/token-harness"
if [ "$here" != "$want" ]; then
  echo
  echo "注意：このフォルダは $(show "$here") にある。"
  echo "      文書は ~/.claude/token-harness を指しているので、そこへ clone し直すこと。"
fi

cat <<EOF

== このあと、自分で貼るもの（このスクリプトは書き換えない）

1) ~/.claude/CLAUDE.md に、次のファイルの囲みの中を足す
   $(show "$here/core/claude-md-snippet.md")

2) ~/.claude/settings.json に、ステータスラインを足す（使用率を保存するため）
   "statusLine": { "type": "command", "command": "bash \\"$(show "$here/statusline/statusline-tee.sh")\\"" }
   もう statusLine を使っている人は、もとのスクリプトのパスを引数に足す（README の「もうステータスラインがある人」）

3) Claude Code を新しいセッションで始める（係の種類は、セッションの始めに読み込まれる）

4) 1回やり取りしたあと、予算が読めるかを見る
   bash "$(show "$here/core/budget.sh")" 85 50
EOF

[ "$failed" = 0 ] || exit 1
exit 0
