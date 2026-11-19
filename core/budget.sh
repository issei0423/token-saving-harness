#!/usr/bin/env bash
# 予算（Claude Code の契約の枠の使用率）を見る。
# 使い方：bash ~/.claude/token-harness/core/budget.sh [5時間枠の線(%)] [7日枠の線の下限(%)] [fixed] [--json]
# 出力の最後の行が GO なら新しい係を出してよい。STOP なら出さない。終了コードは GO=0、STOP=1、読めない=2
# 最後の行の手前に「7日枠の線」「ペース」「判断：…」の行が出る（判断は 契約の枠／小さく／待つ）
# 7日枠の線は、残り日数に合わせて動く（第2引数は下限）。固定の線で見るときは 3つ目に fixed
# 中身は core/budget.py。ここは包みで、引数・最後の行・終了コードの約束を守る（見張りのループが頼る）
here=$(cd "$(dirname "$0")" && pwd)
py=python3; command -v python3 >/dev/null 2>&1 && python3 -c "" >/dev/null 2>&1 || py=python
if ! command -v "$py" >/dev/null 2>&1; then
  echo "python が無い。予算を読めない"; echo UNKNOWN; exit 2
fi
"$py" -X utf8 -I "$here/budget.py" "$@"
code=$?
# 0・1・2 のほかで終わったら（python が起動できないなど）、読めないとして 2 を返す
case $code in 0|1|2) exit $code ;; *) echo "budget.py が終了コード $code で終わった"; echo UNKNOWN; exit 2 ;; esac
