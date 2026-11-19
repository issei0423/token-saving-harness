# 役の表と、役の選び方

`graph.md` から切り出した（読む合図：「→ 読む：roles.md（役の表と選び方）」）

正は `~/.claude/agents/<係>.md` の頭（`model:`・`tools:`）。この表は説明で、食い違ったら係の文書が正しい。

## 5つの役

| 役 | 係 | 目的 | モデル | 道具 | 書いてよいか |
| :-- | :-- | :-- | :-- | :-- | :-- |
| think | `thinker` | 読み方を決め、案を比べ、点に割る | inherit（頭役と同じ） | Read・Grep・Glob・Bash・WebSearch・WebFetch | 書かない |
| research | `researcher` | 読むだけで調べ、根拠つきで返す | haiku | Read・Glob・Grep | 書かない |
| test | `tester` | 渡されたコマンドを回して数える | haiku | Read・Glob・Grep・Bash | 書かない（一時ファイルのほか） |
| implement | `executor` | 点を1つやり、確かめて報告する | sonnet | Read・Write・Edit・Glob・Grep・Bash | worktree の中 |
| verify | `verifier` | 指摘や報告を原文に当たって確かめる | sonnet | Read・Grep・Glob・Bash・WebSearch・WebFetch・Write | 書き出し先だけ |

モデルは作者が置いた既定。自分の契約と仕事に合わせて、係の文書の `model:` を書き換える。

## 役の選び方

1. **役を決める**：点の中身で選ぶ
   - 読むだけ → research
   - コマンドを回して数えるだけ → test
   - 直す・作る → implement。読み方が1つで判断が要らない作業は、手が多くても thinker を通さず、目標と終わりの条件で implement の係1体に渡す
   - 指摘や報告を確かめる → verify
   - 読み方・設計の判断が要る → think（頭役か `thinker`）
   - 機械的なコピーは係に出さず、頭役が直にやる（渡す説明を書くほうが高くつく）
2. **予算を見る**：`bash ~/.claude/token-harness/core/budget.sh 85 50` の「判断：」の行（`budget.md`）
   - 契約の枠 → 同時4体まで
   - 小さく → 同時2体まで。research・test の点を先に
   - 待つ → 新しい点を出さない
3. **頼みの文を書く**：点の id、やること、終わりの条件、許す操作、作業場所、関係する決定。パスは直に書く。会話の経緯は入れない

## 役を分けるわけ（作者の実測）

- 同じ調べものを、頭役と同じモデルの汎用の係に出すと 61,200 トークン。道具と指示文を絞った `researcher`（haiku）は 29,000 トークンで、ほぼ同じ答え（33 か所のうち 32）を返した
- `researcher` がまだ読み込まれていないセッションで、汎用の係に役の文書を読ませて代わりをさせると 76,134 トークンで、かえって重い。入れた後は**新しいセッション**で出す
- 測り方と表は、リポジトリの `token/measure.md`
