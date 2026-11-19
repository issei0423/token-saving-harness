#!/usr/bin/env bash
# ステータスラインに渡る JSON を statusline-last.json に保存する。
# 使用率（rate_limits.five_hour.used_percentage など）を core/budget.sh が読めるようにするため。
#
# 入れ方：~/.claude/settings.json の statusLine.command を、このスクリプトにする（install.sh が文を表示する）
#   "statusLine": { "type": "command", "command": "bash \"<このファイルの絶対パス>\"" }
#
# 保存は、同じフォルダの一時ファイル（<保存先>.tmp.<プロセス番号>）に書いてから mv で置き換える。
# 読む側は、いつ読んでも前の JSON か次の JSON のどちらか丸ごとを見る（直に書くと、書いている途中に読んだとき JSON が切れる）。
#
# もとから使っていたステータスラインのスクリプトがあれば、1つ目の引数で渡す：
#   bash statusline-tee.sh "<もとのスクリプトの絶対パス>"
# 保存したあと、JSON をそのまま渡して表示を任せる。
# 無ければ、このスクリプトが「モデル · 5h 12% · 7d 21% · ctx 34%」の1行を出す。
#
# 差し替え（環境変数）：
#   STATUSLINE_LAST  保存先（既定 ~/.claude/statusline-last.json。CLAUDE_CONFIG_DIR があればその下）
#   STATUSLINE_ORIG  もとのスクリプト（引数が無いときに見る）
conf=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
last=${STATUSLINE_LAST:-$conf/statusline-last.json}
orig=${1:-${STATUSLINE_ORIG:-}}
input=$(cat)
tmp="$last.tmp.$$"
# 保存に失敗しても、ステータスラインの表示は止めない
# 入力が空なら保存先を置き換えない（前の JSON を残す。空のファイルは読む側で読めない）
# 保存先のフォルダが無いときのリダイレクトの失敗は、{ …; } 2>/dev/null で包んで画面に出さない
if [ -n "$input" ]; then
  if { printf '%s' "$input" > "$tmp"; } 2>/dev/null; then
    mv -f "$tmp" "$last" 2>/dev/null || rm -f "$tmp" 2>/dev/null
  else
    rm -f "$tmp" 2>/dev/null
  fi
fi

if [ -n "$orig" ] && [ -f "$orig" ]; then
  printf '%s' "$input" | bash "$orig"
  exit $?
fi

# もとのスクリプトが無いとき：使用率を1行で出す（python が無ければ何も出さない）
py=python3; command -v python3 >/dev/null 2>&1 && python3 -c "" >/dev/null 2>&1 || py=python
command -v "$py" >/dev/null 2>&1 || exit 0
printf '%s' "$input" | "$py" -X utf8 -I -c '
import json, sys

def num(x):
    try:
        return f"{float(x):g}%"
    except (TypeError, ValueError):
        return None

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not isinstance(d, dict):
    sys.exit(0)
parts = []
model = d.get("model")
if isinstance(model, dict) and model.get("display_name"):
    parts.append(str(model["display_name"]))
rl = d.get("rate_limits") if isinstance(d.get("rate_limits"), dict) else {}
for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
    w = rl.get(key)
    v = num(w.get("used_percentage")) if isinstance(w, dict) else None
    if v:
        parts.append(label + " " + v)
ctx = d.get("context_window")
v = num(ctx.get("used_percentage")) if isinstance(ctx, dict) else None
if v:
    parts.append("ctx " + v)
print(" · ".join(parts))
' 2>/dev/null
exit 0
