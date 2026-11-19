# token-saving-harness

**日本語** · [English](README.en.md)

Claude Code のトークンを節約するためのハーネスです。中身は、決まりの文書・係（サブエージェント）の定義・使用率の見張りの 3 つ。

賢いモデルには**考えることだけ**をさせ、調べもの・テスト・実装は、役に合わせた小さいモデルの係に回します。

## 何が減るか（作者の PC での実測）

| 変えたこと | 前 | 後 | 差 |
| :-- | --: | --: | --: |
| 毎セッション読み込む決まりの文書を、小さい核＋呼ぶときだけ読む文書に割った | 6,442 | 4,153 | **−36%** |
| 調べものを、頭役と同じモデルの係から、haiku の `researcher` に替えた | 61,200 | 29,000 | **−53%** |

単位はトークン。2 行目は、答えもほぼ同じでした（33 か所のうち 32）。

逆に増えた例もあります。係の定義を入れた直後のセッションで、汎用の係に代わりをさせたら 76,134 トークン（`researcher` の 2.6 倍）でした。

測ったのは作者の PC 1 台、2026 年 10〜11 月、この公開版のもとになった個人版での値です。測り方と、測っていないことは [token/measure.md](token/measure.md) に書いてあります。

## 3 つの原則

1. **常時読み込むものを小さくする。** `CLAUDE.md` に `@` で大きな文書を取り込むと、毎セッション丸ごと入ります
2. **詳しいものは、呼んだときだけ読む。** 核には 1〜3 行の要点と「→ 読む」の合図だけを置きます
3. **係に渡す情報は、その仕事に要るものだけ。** 会話の経緯は渡しません

## まず 1 つだけ試すなら（入れなくてもできる）

- `CLAUDE.md` の `@` 取り込みをやめて、「要るときにこの文書を `Read` で開く」と書く
- 読むだけの調べものは、道具を Read・Glob・Grep に絞った haiku の係に出す（[core/agents/researcher.md](core/agents/researcher.md) を `~/.claude/agents/` に置くだけ）
- セッションの途中でモデル・effort・`CLAUDE.md` を変えない（キャッシュが切れます）

## 入っているもの

| 場所 | 中身 |
| :-- | :-- |
| [core/graph.md](core/graph.md) | 核。頭役（メインのセッション）が読む決まり。3,700 字ほどで、5,000 字を越えないようテストが見張る |
| [core/graph/](core/graph/) | 呼ぶときだけ読む文書（図・役の表・予算・許す操作・留守のとき・状態ファイル） |
| [core/agents/](core/agents/) | 係 5 つ：`thinker`（考える）・`executor`（実行する・sonnet）・`researcher`（調べる・haiku）・`tester`（試す・haiku）・`verifier`（照合する・sonnet） |
| [core/budget.sh](core/budget.sh) | 5 時間枠・7 日枠の使用率を見て、次の係を出してよいかを `GO`／`STOP` で返す |
| [statusline/statusline-tee.sh](statusline/statusline-tee.sh) | ステータスラインに渡る使用率を保存する（`budget.sh` が読む） |
| [token/](token/) | トークン節約の決め（読み込み・振り分け・係への渡し方）と実測 |
| [tests/](tests/) | テスト（`bash tests/run.sh`） |

## 入れ方

要るもの：Claude Code（Pro・Max などの契約でログイン）、bash（Windows は Git Bash）、Python 3。

```bash
git clone https://github.com/issei0423/token-saving-harness ~/.claude/token-harness
cd ~/.claude/token-harness
bash install.sh           # 何をするかを表示するだけ
bash install.sh --apply   # 係の定義を ~/.claude/agents へ写す
```

`install.sh` は係の定義を写すだけです。同じ名前のファイルがあれば、`~/.claude/agents-backup/` に退避してから置き換えます。設定は書き換えないので、次の 2 つは自分で貼ります（貼る文は `install.sh` が、その PC のパスで表示します）。

1. `~/.claude/CLAUDE.md` に、[core/claude-md-snippet.md](core/claude-md-snippet.md) の囲みの中を足す
2. `~/.claude/settings.json` に `statusLine` を足す

   ```json
   "statusLine": { "type": "command", "command": "bash \"<絶対パス>/statusline/statusline-tee.sh\"" }
   ```

そのあと、Claude Code を**新しいセッション**で始めます（係の種類は、セッションの始めに読み込まれます）。

### もうステータスラインがある人

いまの `statusLine.command` の中身をスクリプトのファイルに写し、そのパスを 1 つ目の引数で渡します。使用率を保存したあと、表示はもとのスクリプトに任せます。

```json
"statusLine": { "type": "command", "command": "bash \"<絶対パス>/statusline/statusline-tee.sh\" \"<もとのスクリプトの絶対パス>\"" }
```

## 使い方

ふつうに頼むだけです。頭役が依頼を仕分けます。

- 小さく、読み方が 1 つの依頼 → 頭役がそのままやる
- 手は多いが判断の要らない依頼 → `executor` に目標で渡す
- 読み方が割れる・設計の判断がある依頼 → `thinker` が考えて、実行の点に割る
- 係の報告はそのまま信じず、頭役が差分とテストを自分で見る

使用率は、いつでも見られます。

```console
$ bash ~/.claude/token-harness/core/budget.sh 85 50
いま 11-07 09:36 +0900（statusline-last.json は 0 分前のもの）
5時間枠：18%（線 85% をまだ）／11-07 13:20 に戻る（あと 3時間43分）
7日枠：58%（線 85% をまだ）／11-07 23:00 に戻る（あと 13時間23分）
…
判断：契約の枠（線の手前。契約の枠で出す）
GO
```

7 日枠の線は、週の残り日数に合わせて動きます（週の初めは 50%、終わりは 85%）。式は [core/graph/budget.md](core/graph/budget.md)。

## 自分用に変える所

| 変えたいこと | 場所 |
| :-- | :-- |
| 係のモデル・道具 | `~/.claude/agents/<係>.md` の頭（`model:`・`tools:`） |
| 係に使わせたくない道具（メール送信・チャット投稿の MCP など） | `executor.md` の `disallowedTools:` に足す |
| 聞かずにしてよい操作・しない操作 | `core/graph.md` の「許す操作」 |
| マージを任せるリポジトリ | `core/graph/permissions.md` |
| 予算の線（85%・50%） | 頭役に言う（「90% まで」）か、`core/graph.md` の「予算」 |
| 週の終わりに残す分・ペース | `core/budget-policy.json` |

文書は日本語です。係への指示も日本語で書いてありますが、Claude はどの言語の依頼にも応えます。

## 戻し方

- `~/.claude/CLAUDE.md` から、足した囲みの中身を消す
- `~/.claude/settings.json` の `statusLine` を、もとに戻す
- `~/.claude/agents/` の 5 つ（`thinker.md`・`executor.md`・`researcher.md`・`tester.md`・`verifier.md`）を消す。退避したものは `~/.claude/agents-backup/` にある
- `~/.claude/token-harness/` を消す

## 確かめたこと・確かめていないこと

確かめたこと：

- テスト（`bash tests/run.sh`）が、Ubuntu・macOS・Windows の GitHub Actions で通る
- もとになった個人版は、作者の PC（Windows・Claude Code 2.1）で使っている

確かめていないこと：

- この公開版を、まっさらな Claude Code に入れて使い続けたこと（個人版から個人の事情を落として書き直した直後です）
- macOS・Linux で実際に Claude Code と組み合わせたこと（テストだけ）
- 使用率（`rate_limits`）は、契約でログインした Claude Code のステータスラインに出ます。API キーで使っているとき・版が古いときは出ず、`budget.sh` は `UNKNOWN` を返します

おかしな所は [Issue](https://github.com/issei0423/token-saving-harness/issues) で教えてください。

## ライセンス

[MIT](LICENSE)
