#!/usr/bin/env bash
# statusline/statusline-tee.sh の試験。PASS／FAIL を出し、FAIL があれば終了コード 1。
# 保存先・もとのスクリプトは環境変数で一時フォルダへ向ける（本物の ~/.claude には触れない）。
here=$(cd "$(dirname "$0")/.." && pwd)
tee_sh="$here/statusline/statusline-tee.sh"
tmp=$(mktemp -d 2>/dev/null || mktemp -d -t tee)
trap 'rm -rf "$tmp"' EXIT
fails=0
report() { if [ "$2" = 0 ]; then echo "PASS: $1"; else echo "FAIL: $1${3:+（$3）}"; fails=$((fails + 1)); fi; }

json='{"model":{"display_name":"Test Model"},"context_window":{"used_percentage":34},"rate_limits":{"five_hour":{"used_percentage":12,"resets_at":1},"seven_day":{"used_percentage":21.5,"resets_at":2}}}'
last="$tmp/statusline-last.json"

# 1) 保存して、使用率の1行を出す
out=$(printf '%s' "$json" | STATUSLINE_LAST="$last" STATUSLINE_ORIG= bash "$tee_sh" 2>"$tmp/err"); code=$?
[ "$code" = 0 ] && [ "$(cat "$last" 2>/dev/null)" = "$json" ]; report "入力の JSON を保存先にそのまま保存する" $? "code=$code"
case $out in *"Test Model"*"5h 12%"*"7d 21.5%"*"ctx 34%"*) r=0 ;; *) r=1 ;; esac
report "もとのスクリプトが無ければ、モデル・5h・7d・ctx の1行を出す" $r "$out"
[ ! -s "$tmp/err" ]; report "標準エラーに何も出さない" $? "$(cat "$tmp/err")"
[ -z "$(ls "$tmp" | grep '\.tmp\.')" ]; report "一時ファイルを残さない" $?

# 2) 入力が空なら、前の JSON を残す
printf '' | STATUSLINE_LAST="$last" STATUSLINE_ORIG= bash "$tee_sh" >/dev/null 2>&1
[ "$(cat "$last")" = "$json" ]; report "入力が空なら保存先を置き換えない" $?

# 3) もとのスクリプトがあれば、JSON をそのまま渡して表示を任せる
cat > "$tmp/orig.sh" <<'EOF'
input=$(cat)
printf 'ORIG:%s' "${#input}"
EOF
json2='{"rate_limits":{"five_hour":{"used_percentage":50,"resets_at":1}}}'
out=$(printf '%s' "$json2" | STATUSLINE_LAST="$last" STATUSLINE_ORIG="$tmp/orig.sh" bash "$tee_sh" 2>/dev/null)
[ "$out" = "ORIG:${#json2}" ]; report "STATUSLINE_ORIG があれば、その出力をそのまま出す" $? "$out"
[ "$(cat "$last")" = "$json2" ]; report "そのときも保存する" $?
out=$(printf '%s' "$json" | STATUSLINE_LAST="$last" STATUSLINE_ORIG= bash "$tee_sh" "$tmp/orig.sh" 2>/dev/null)
[ "$out" = "ORIG:${#json}" ] && [ "$(cat "$last")" = "$json" ]; report "もとのスクリプトは1つ目の引数でも渡せる" $? "$out"

# 4) 保存先のフォルダが無くても、表示は止めず、エラーも出さない
out=$(printf '%s' "$json" | STATUSLINE_LAST="$tmp/nai/dir/last.json" STATUSLINE_ORIG= bash "$tee_sh" 2>"$tmp/err"); code=$?
case $out in *"5h 12%"*) r=0 ;; *) r=1 ;; esac
[ "$code" = 0 ] && [ "$r" = 0 ] && [ ! -s "$tmp/err" ]; report "保存先のフォルダが無くても表示は出て、エラーを出さない" $? "code=$code out=$out err=$(cat "$tmp/err")"

# 5) 保存先の既定は CLAUDE_CONFIG_DIR の下
mkdir -p "$tmp/conf"
printf '%s' "$json" | CLAUDE_CONFIG_DIR="$tmp/conf" STATUSLINE_LAST= STATUSLINE_ORIG= bash "$tee_sh" >/dev/null 2>&1
[ "$(cat "$tmp/conf/statusline-last.json" 2>/dev/null)" = "$json" ]; report "保存先の既定は CLAUDE_CONFIG_DIR の下" $?

# 6) JSON でない入力でも落ちない
out=$(printf 'not json' | STATUSLINE_LAST="$tmp/x.json" STATUSLINE_ORIG= bash "$tee_sh" 2>"$tmp/err"); code=$?
[ "$code" = 0 ] && [ ! -s "$tmp/err" ]; report "JSON でない入力でも落ちない" $? "code=$code err=$(cat "$tmp/err")"

# 7) rate_limits が無い JSON（API キーで使っているとき）でも1行は出る
out=$(printf '%s' '{"model":{"display_name":"M"}}' | STATUSLINE_LAST="$tmp/y.json" STATUSLINE_ORIG= bash "$tee_sh" 2>/dev/null)
[ "$out" = "M" ]; report "rate_limits が無ければ、あるものだけ出す" $? "$out"

echo "合計 FAIL $fails"
[ "$fails" = 0 ]
