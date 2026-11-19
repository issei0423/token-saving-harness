#!/usr/bin/env python3
"""予算（Claude Code の契約の枠の使用率）を見て、次の係を出してよいかを決める。core/budget.sh がこれを包む。

使い方：python core/budget.py [5時間枠の線(%)] [7日枠の線の下限(%)] [fixed] [--json] [--now 時刻] [--file パス] [--policy パス]
- 最後の行は GO・STOP・UNKNOWN のどれか。終了コードは GO=0、STOP=1、読めない=2
- 3つ目の引数 fixed で、固定の線（第2引数そのもの）で見る
- --json は、行の代わりに JSON を1つ出す（終了コードは同じ）
- --now・--file・--policy は試験のための差し込み（--now は epoch 秒か ISO 8601）

元データは、ステータスラインに渡る JSON の rate_limits（statusline/statusline-tee.sh が statusline-last.json に保存する）。

7日枠の線（fixed でないとき）：
  経過 ＝ 1 − 残り分 / 10080（窓は戻る時刻の7日前に始まる前提。推測なので、経過を出力に出す）
  線   ＝ (100 − 残す分) × 経過 ＋ 余裕 を、上限 100 − 残す分 で切り、第2引数より下げない
ペース ＝ 使用率 / 経過。pace_small を超えたら「小さく」
判断は3つ：契約の枠／小さく（ここまで GO）／待つ（STOP）
値の正は core/budget-policy.json
"""
import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path

WEEK_MIN = 7 * 24 * 60
HERE = Path(__file__).resolve().parent

# budget-policy.json が読めないときだけ使う。値は budget-policy.json と同じにする（tests/test_budget.py が一致を確かめる）
DEFAULT_POLICY = {
    "reserve_pct": 15,
    "slack_pct": 15,
    "pace_small": 1.3,
}

ROUTES = {
    "contract": "契約の枠",
    "small": "小さく",
    "wait": "待つ",
}


class Unreadable(Exception):
    pass


def read_json(path, tries=3, wait=0.3, sleep=time.sleep):
    """JSON を読む。返り値は (中身, 注意の文 か None)。読めなければ Unreadable。

    書く側（ステータスライン）が書いている途中だと壊れて見えるので、0.3秒おいて3回まで読み直す。
    それでもだめなら、頭から1つ目の JSON だけを読む（後ろに余りがある Extra data のとき）。
    """
    text, err = "", None
    for i in range(tries + 1):
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
        except OSError as e:
            raise Unreadable(f"開けない（{e.__class__.__name__}）")
        try:
            return json.loads(text), None
        except json.JSONDecodeError as e:
            err = e
        if i < tries:
            sleep(wait)
    try:
        obj, _ = json.JSONDecoder().raw_decode(text.lstrip())
    except json.JSONDecodeError:
        raise Unreadable(f"JSON として読めない（{err.msg}、{tries}回読み直した）")
    return obj, f"JSON の後ろに余りがあった（{err.msg}）。頭の1つだけを読んだ"


def load_policy(path):
    """返り値は (policy, 注意の文 か None)。読めない欄は DEFAULT_POLICY の値を使う。"""
    try:
        data, _ = read_json(path, tries=0)
        if not isinstance(data, dict):
            raise Unreadable("中身が表（object）でない")
    except Unreadable as e:
        return dict(DEFAULT_POLICY), f"budget-policy.json を読めない（{e}）。既定の値で見た"
    policy = dict(DEFAULT_POLICY)
    policy.update({k: data[k] for k in DEFAULT_POLICY if k in data})
    return policy, None


def window(v, now):
    """rate_limits の1つの枠を読む。無い・形が違うときは None。時刻は now と同じ時刻帯で持つ。"""
    if not isinstance(v, dict) or "resets_at" not in v:
        return None
    try:
        used = float(v.get("used_percentage", 0))
        reset = datetime.datetime.fromtimestamp(float(v["resets_at"]), now.tzinfo)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    passed = reset <= now
    left = 0 if passed else int((reset - now).total_seconds() // 60)
    return {"used": used, "reset": reset, "left_min": left, "passed": passed}


def week_line(week, floor, policy, mode):
    """7日枠の線と経過の割合を返す。返り値は (線, 経過 か None)。"""
    if week is None or week["passed"]:
        return floor, None
    elapsed = min(max(1 - week["left_min"] / WEEK_MIN, 0.0), 1.0)
    if mode == "fixed":
        return floor, elapsed
    upper = 100 - policy["reserve_pct"]
    raw = upper * elapsed + policy["slack_pct"]
    return max(floor, min(raw, upper)), elapsed


def judge(five, week, five_line, week_floor, mode, policy):
    """2つの枠から判断を1つ出す。副作用の無い関数（試験はここを直に呼ぶ）。"""
    line, elapsed = week_line(week, week_floor, policy, mode)
    five_stop = bool(five and not five["passed"] and five["used"] >= five_line)
    week_stop = bool(week and not week["passed"] and week["used"] >= line)
    pace = None
    if week is not None:
        if week["passed"]:
            pace = 0.0
        elif elapsed:
            pace = (week["used"] / 100) / elapsed
    if not (five_stop or week_stop):
        if pace is not None and pace > policy["pace_small"]:
            route = "small"
            reason = f"ペース {pace:.2f} が {policy['pace_small']:g} を超えた。同時2体まで、research・test を先に"
        else:
            route, reason = "contract", "線の手前。契約の枠で出す"
    else:
        route = "wait"
        if week_stop and five_stop:
            reason = f"5時間枠も7日枠も線を越えた。7日枠は {hm(week['left_min'])}後に戻る"
        elif week_stop:
            reason = f"7日枠が線を越えた。{hm(week['left_min'])}後に戻る"
        else:
            reason = f"5時間枠が線を越えた。{five['left_min']}分で戻る"
    return {
        "route": route,
        "label": ROUTES[route],
        "reason": reason,
        "verdict": "GO" if route in ("contract", "small") else "STOP",
        "five_stop": five_stop,
        "week_stop": week_stop,
        "week_line": line,
        "elapsed": elapsed,
        "pace": pace,
    }


def parse_now(s):
    """いまの時刻を、時刻帯つきで返す。既定はこの PC の時刻帯（いまのずれで固定。夏時間の切り替えをまたぐ表示は1時間ずれることがある）。"""
    if s is None:
        return datetime.datetime.now().astimezone()
    try:
        return datetime.datetime.fromtimestamp(float(s)).astimezone()
    except ValueError:
        d = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.astimezone()


def pct(x):
    return f"{round(x, 1):g}"


def hm(minutes):
    return f"{minutes // 60}時間{minutes % 60}分"


def default_file():
    conf = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(conf) if conf else Path.home() / ".claude") / "statusline-last.json"


def main(argv=None):
    ap = argparse.ArgumentParser(description="予算を見て、次の係を出してよいかを決める")
    ap.add_argument("five_line", nargs="?", type=float, default=85.0, help="5時間枠の線（%%）")
    ap.add_argument("week_line", nargs="?", type=float, default=50.0, help="7日枠の線の下限（%%）。fixed なら線そのもの")
    ap.add_argument("mode", nargs="?", default="pace", choices=("pace", "fixed"), help="fixed で固定の線")
    ap.add_argument("--json", action="store_true", help="行の代わりに JSON を1つ出す")
    ap.add_argument("--now", help="いまの時刻（epoch 秒か ISO 8601）。試験用")
    ap.add_argument("--file", help="statusline-last.json の場所")
    ap.add_argument("--policy", help="budget-policy.json の場所")
    a = ap.parse_args(argv)

    path = Path(a.file) if a.file else default_file()
    policy, policy_note = load_policy(Path(a.policy) if a.policy else HERE / "budget-policy.json")
    now = parse_now(a.now)
    lines, notes = [], [n for n in (policy_note,) if n]

    def finish(out, code):
        if a.json:
            print(json.dumps(out, ensure_ascii=False, default=str))
        else:
            # 1行目（いま …）は動かさない。注意は最後の行の手前に出す
            print("\n".join(lines + ["注意：" + n for n in notes]))
            print(out["verdict"])
        return code

    def unknown(reason, first_line):
        lines.append(first_line)
        lines.append("判断：読めない")
        return finish({"verdict": "UNKNOWN", "reason": reason, "notes": notes}, 2)

    if not path.is_file():
        return unknown(f"{path.name} が無い", f"{path.name} が無い。予算を読めない（statusline/statusline-tee.sh をステータスラインに入れると作られる）")
    try:
        data, read_note = read_json(path)
        if not isinstance(data, dict):
            raise Unreadable("中身が表（object）でない")
    except Unreadable as e:
        return unknown(str(e), f"{path.name} を読めない：{e}")
    if read_note:
        notes.append(read_note)
    rl = data.get("rate_limits") if isinstance(data.get("rate_limits"), dict) else {}
    five = window(rl.get("five_hour"), now)
    week = window(rl.get("seven_day"), now)
    if five is None and week is None:
        return unknown(
            "rate_limits に枠が無い",
            f"{path.name} の rate_limits に枠が無い。予算を読めない（契約プランでログインしていない・Claude Code の版が古い・まだ1回も返事が返っていない、のどれか）",
        )
    try:
        age = max(int((time.time() - path.stat().st_mtime) / 60), 0)
    except OSError:
        age = 0
    # 1行目は「いま …」（状態ファイルの時刻はここから取る決まり）
    lines.append(f"いま {now:%m-%d %H:%M} {now:%z}（{path.name} は {age} 分前のもの）")

    r = judge(five, week, a.five_line, a.week_line, a.mode, policy)

    for w, label, line in ((five, "5時間枠", a.five_line), (week, "7日枠", r["week_line"])):
        if w is None:
            lines.append(f"{label}：読めない")
        elif w["passed"]:
            # 戻る時刻を過ぎている。ステータスラインが描き直されるまでは古い値が残るので、0% として扱う
            lines.append(f"{label}：{w['reset']:%m-%d %H:%M} に戻った（ファイルの {w['used']:g}% は戻る前の値。0% として扱う）")
        else:
            mark = "越えた" if w["used"] >= line else "まだ"
            lines.append(f"{label}：{w['used']:g}%（線 {pct(line)}% を{mark}）／{w['reset']:%m-%d %H:%M} に戻る（あと {hm(w['left_min'])}）")

    el = r["elapsed"]
    el_txt = "経過 不明" if el is None else f"経過 {el * 100:.1f}%"
    if a.mode == "fixed":
        lines.append(f"7日枠の線：{pct(r['week_line'])}%（fixed：固定の線。{el_txt}）")
    else:
        upper = 100 - policy["reserve_pct"]
        lines.append(
            f"7日枠の線：{pct(r['week_line'])}%（{el_txt}＝1−残り分/10080。"
            f"(100−{policy['reserve_pct']:g})×経過＋{policy['slack_pct']:g} を上限 {upper:g}% で切り、下限 {a.week_line:g}% より下げない。"
            f"窓は戻る時刻の7日前に始まる前提＝推測）"
        )
    if r["pace"] is None:
        lines.append("ペース：出せない（7日枠の経過が分からない）")
    else:
        used_txt = "0%（戻った）" if week["passed"] else f"{week['used']:g}%"
        el_part = "" if el is None else f" ÷ 経過 {el * 100:.1f}%"
        lines.append(f"ペース：{r['pace']:.2f}（使用率 {used_txt}{el_part}。{policy['pace_small']:g} を超えると小さく）")
    lines.append(f"判断：{r['label']}（{r['reason']}）")
    if age > 15:
        lines.append("注意：15分より古い。ステータスラインが描き直されていない。少し待って読み直すか、古いまま判断したと報告に書く")

    def win_out(w, **extra):
        if w is None:
            return None
        return dict({"used": w["used"], "resets_at": w["reset"].isoformat(), "left_min": w["left_min"], "passed": w["passed"]}, **extra)

    out = {
        "now": now.isoformat(),
        "age_min": age,
        "mode": a.mode,
        "five_hour": win_out(five, line=a.five_line, stop=r["five_stop"]),
        "seven_day": win_out(week, line=r["week_line"], elapsed=el, pace=r["pace"], stop=r["week_stop"]),
        "route": r["route"],
        "label": r["label"],
        "reason": r["reason"],
        "verdict": r["verdict"],
        "policy": policy,
        "notes": notes,
    }
    return finish(out, 0 if r["verdict"] == "GO" else 1)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 思わぬ落ち方で終了コード 1（STOP と同じ）にしない。読めない＝2 にする
        print(f"budget.py が落ちた：{e.__class__.__name__}: {e}")
        print("判断：読めない")
        print("UNKNOWN")
        sys.exit(2)
