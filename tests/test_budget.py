#!/usr/bin/env python3
"""core/budget.py と core/budget.sh の試験。PASS／FAIL を出し、FAIL があれば終了コード 1。

判断の関数（judge）は直に呼ぶ。budget.sh は一時フォルダの statusline-last.json を --file で、時刻を --now で差し込んで回す。
"""
import datetime
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = ROOT / "core" / "budget.sh"
spec = importlib.util.spec_from_file_location("budget", ROOT / "core" / "budget.py")
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)

TZ = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime(2026, 11, 7, 8, 38, tzinfo=TZ)
POLICY = dict(budget.DEFAULT_POLICY)
fails = 0


def report(label, ok, note=""):
    global fails
    fails += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}: {label}{'（' + note + '）' if note and not ok else ''}")


def win(used, left_min, now=NOW):
    """rate_limits の1つの枠（戻るまで left_min 分）"""
    return {"used_percentage": used, "resets_at": int((now + datetime.timedelta(minutes=left_min)).timestamp())}


def j(five_used, five_left, week_used, week_left, mode="pace", five_line=85, week_floor=50):
    """judge を直に呼ぶ"""
    five = budget.window(win(five_used, five_left), NOW)
    week = budget.window(win(week_used, week_left), NOW)
    return budget.judge(five, week, five_line, week_floor, mode, POLICY)


bash = shutil.which("bash")
tmp = Path(tempfile.mkdtemp(prefix="test-budget-"))
env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}  # 画面の文字コードに左右されない


def run(args):
    r = subprocess.run([bash, SH.as_posix(), *args], capture_output=True, text=True, encoding="utf-8", env=env)
    return r.returncode, [x for x in r.stdout.splitlines() if x.strip()], r.stderr


def sh(content, *args):
    """budget.sh を回す。返り値は (終了コード, 空でない行の一覧, stderr)"""
    f = tmp / "statusline-last.json"
    f.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return run([*args, "--file", f.as_posix(), "--now", NOW.isoformat()])


def rl(five, week):
    return {"rate_limits": {"five_hour": five, "seven_day": week}}


try:
    # ── policy の正と、コードの既定がずれていない
    pol = json.loads((ROOT / "core" / "budget-policy.json").read_text(encoding="utf-8"))
    report("budget-policy.json の値が DEFAULT_POLICY と同じ", all(pol.get(k) == v for k, v in POLICY.items()),
           str({k: (pol.get(k), v) for k, v in POLICY.items() if pol.get(k) != v}))

    # ── ① 56%・残り14時間22分 → 契約の枠・GO・0
    r = j(10, 200, 56, 14 * 60 + 22)
    report("① 56%・残り14時間22分 → 契約の枠・GO", r["route"] == "contract" and r["verdict"] == "GO", str(r))
    report("① そのとき線は上限の 85%", abs(r["week_line"] - 85) < 1e-9, str(r["week_line"]))

    # ── ② 経過1日・45% → 小さく・GO
    r = j(10, 200, 45, 6 * 24 * 60)
    report("② 経過1日・45% → 小さく・GO", r["route"] == "small" and r["verdict"] == "GO", str(r))
    report("② 線は下限の 50% より下がらない", abs(r["week_line"] - 50) < 1e-9, str(r["week_line"]))

    # ── ③ 7日枠 90% → 待つ・STOP
    r = j(10, 200, 90, 14 * 60)
    report("③ 7日枠 90% → 待つ・STOP", r["route"] == "wait" and r["verdict"] == "STOP" and r["week_stop"] and not r["five_stop"], str(r))

    # ── ④ 5時間枠 90%・20分後に戻る → 待つ・STOP
    r = j(90, 20, 40, 3 * 24 * 60)
    report("④ 5時間枠 90% → 待つ・STOP（わけに戻るまでの分が出る）",
           r["route"] == "wait" and r["verdict"] == "STOP" and r["five_stop"] and "20分" in r["reason"], str(r))

    # ── 線の性質：第2引数より下げない・上限で切る
    lines_ok = True
    for left in range(0, 10081, 360):
        for floor in (30, 50, 70, 95):
            w = budget.window(win(0, left), NOW)
            ln, _ = budget.week_line(w, floor, POLICY, "pace")
            if ln < floor or (floor <= 85 and ln > 85):
                lines_ok = False
    report("線は第2引数より下がらず、上限 85% を越えない（下限が上限より上なら下限）", lines_ok)

    # ── 読み直し：書いている途中の JSON が、読み直すうちに読めるようになる
    calls = {"n": 0}
    f = tmp / "flaky.json"
    f.write_text("{", encoding="utf-8")

    def fake_sleep(_):
        calls["n"] += 1
        if calls["n"] == 2:
            f.write_text('{"rate_limits": {}}', encoding="utf-8")

    data, note = budget.read_json(f, sleep=fake_sleep)
    report("書いている途中の JSON は読み直して読める", data == {"rate_limits": {}} and note is None and calls["n"] == 2, f"{data} {note} {calls}")

    if bash:
        code, out, err = sh(rl(win(10, 200), win(56, 14 * 60 + 22)), "85", "50")
        report("① budget.sh 85 50 → 最後の行 GO・終了コード 0", code == 0 and out[-1:] == ["GO"], f"{code} {out[-1:]} {err}")
        report("① 1行目は「いま 月-日 時:分 時刻帯」", bool(out) and out[0].startswith("いま 11-07 08:38 +0900"), out[0] if out else "")
        report("① 『判断：契約の枠』の行が最後の行より前にある", any(x.startswith("判断：契約の枠") for x in out[:-1]), str(out))
        report("① 『7日枠の線』に経過の割合が出る", any(x.startswith("7日枠の線：85%（経過 91.4%") for x in out), str(out))
        report("① 『ペース』の行がある", any(x.startswith("ペース：0.61") for x in out), str(out))

        code, out, _ = sh(rl(win(10, 200), win(45, 6 * 24 * 60)), "85", "50")
        report("② budget.sh → GO・0・『判断：小さく』", code == 0 and out[-1] == "GO" and any(x.startswith("判断：小さく") for x in out), str(out))

        code, out, _ = sh(rl(win(10, 200), win(90, 14 * 60)), "85", "50")
        report("③ budget.sh → 『判断：待つ』・STOP・終了コード 1", code == 1 and out[-1] == "STOP" and any(x.startswith("判断：待つ") for x in out), f"{code} {out}")

        code, out, _ = sh(rl(win(90, 20), win(40, 3 * 24 * 60)), "85", "50")
        report("④ budget.sh → 『判断：待つ』・STOP・1", code == 1 and out[-1] == "STOP" and any(x.startswith("判断：待つ") for x in out), str(out))

        # ── ⑤ Extra data の JSON（後ろに余り）→ 読めて判断が出る
        good = json.dumps(rl(win(10, 200), win(56, 14 * 60 + 22)))
        code, out, _ = sh(good + '\n{"rate_limits": {}}', "85", "50")
        report("⑤ Extra data の JSON → 読めて『判断：』が出る・GO・0",
               code == 0 and out[-1] == "GO" and any(x.startswith("判断：契約の枠") for x in out) and any("余り" in x for x in out), str(out))

        # ── ⑥ 壊れた JSON → UNKNOWN・2
        code, out, _ = sh('{"rate_limits": {"five_hour": {"used_perc', "85", "50")
        report("⑥ 壊れた JSON → 最後の行 UNKNOWN・終了コード 2", code == 2 and out[-1:] == ["UNKNOWN"], f"{code} {out}")

        # ── ⑦ fixed → 56% で STOP
        code, out, _ = sh(rl(win(10, 200), win(56, 14 * 60 + 22)), "85", "50", "fixed")
        report("⑦ fixed → 56% で STOP・1", code == 1 and out[-1] == "STOP" and any("fixed" in x for x in out), str(out))

        # ── 無いファイル → UNKNOWN・2
        code, out, _ = run(["85", "50", "--file", (tmp / "nai.json").as_posix()])
        report("無い statusline-last.json → UNKNOWN・2", code == 2 and out[-1:] == ["UNKNOWN"], str(out))

        # ── 枠が1つも無い（API キーで使っている・版が古い）→ GO と言わずに UNKNOWN
        code, out, _ = sh({"model": {"display_name": "x"}}, "85", "50")
        report("rate_limits が無い → UNKNOWN・2（GO と言わない）", code == 2 and out[-1:] == ["UNKNOWN"] and "判断：読めない" in out, f"{code} {out}")
        code, out, _ = sh({"rate_limits": {}}, "85", "50")
        report("rate_limits が空 → UNKNOWN・2", code == 2 and out[-1:] == ["UNKNOWN"], f"{code} {out}")

        # ── 片方の枠だけ無い（戻る前後）→ 読めないと出して、ある方で判断する
        code, out, _ = sh({"rate_limits": {"seven_day": win(30, 3 * 24 * 60)}}, "85", "50")
        report("five_hour だけ無い → 『5時間枠：読めない』・GO", code == 0 and "5時間枠：読めない" in out and out[-1] == "GO", str(out))

        # ── 戻る時刻を過ぎた → 0% として扱う
        code, out, _ = sh(rl(win(95, -10), win(95, -10)), "85", "50")
        report("戻る時刻を過ぎた枠は 0% として扱う → GO", code == 0 and out[-1] == "GO", str(out))

        # ── 保存先の既定は CLAUDE_CONFIG_DIR の下
        conf = tmp / "conf"
        conf.mkdir()
        (conf / "statusline-last.json").write_text(json.dumps(rl(win(10, 200), win(56, 14 * 60 + 22))), encoding="utf-8")
        p = subprocess.run([bash, SH.as_posix(), "85", "50", "--now", NOW.isoformat()], capture_output=True, text=True, encoding="utf-8",
                           env={**env, "CLAUDE_CONFIG_DIR": str(conf)})
        report("--file が無ければ CLAUDE_CONFIG_DIR の下の statusline-last.json を読む",
               p.returncode == 0 and p.stdout.strip().splitlines()[-1:] == ["GO"], p.stdout + p.stderr)

        # ── --json
        f = tmp / "statusline-last.json"
        f.write_text(json.dumps(rl(win(10, 200), win(56, 14 * 60 + 22))), encoding="utf-8")
        p = subprocess.run([bash, SH.as_posix(), "85", "50", "--json", "--file", f.as_posix(), "--now", NOW.isoformat()],
                           capture_output=True, text=True, encoding="utf-8", env=env)
        try:
            d = json.loads(p.stdout)
            ok = p.returncode == 0 and d["verdict"] == "GO" and d["route"] == "contract" and abs(d["seven_day"]["elapsed"] - (1 - 862 / 10080)) < 1e-9
        except (ValueError, KeyError, TypeError):
            ok = False
        report("--json → JSON 1つ・verdict GO・経過の割合", ok, p.stdout[:200])
    else:
        print("確かめていない: budget.sh を回す試験（bash が無い）")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"合計 FAIL {fails}")
sys.exit(1 if fails else 0)
