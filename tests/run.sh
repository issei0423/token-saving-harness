#!/usr/bin/env bash
# 全部の試験を回す。使い方：bash tests/run.sh
# 試験ごとに PASS／FAIL の行が出て、最後に合計を出す。FAIL があれば終了コード 1。
# どの試験も一時フォルダの中だけで動き、本物の ~/.claude には触れない。
here=$(cd "$(dirname "$0")/.." && pwd)
py=python3; command -v python3 >/dev/null 2>&1 && python3 -c "" >/dev/null 2>&1 || py=python
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
total=0
run() {
  echo "── $1"
  shift
  "$@"; code=$?
  [ "$code" = 0 ] || total=$((total + 1))
  echo
}
run "文書の点検" "$py" -X utf8 "$here/tests/check_docs.py"
run "予算（budget.py・budget.sh）" "$py" -X utf8 "$here/tests/test_budget.py"
run "ステータスラインの保存（statusline-tee.sh）" bash "$here/tests/test-statusline-tee.sh"
run "入れるスクリプト（install.sh）" bash "$here/tests/test-install.sh"
if [ "$total" = 0 ]; then echo "全部通った"; else echo "落ちた試験のまとまり：$total"; fi
[ "$total" = 0 ]
