# セリフ文字カウント（完成シナリオ末尾）

完成シナリオの**最後**（エピローグの「ごきげんよう。」の直後）に、参考数値として記載する。

## カウントの定義

| 項目 | 含める | 含めない |
|---|---|---|
| `**キャラ名**：` の行のうち、**先頭の（演技指示）を除いた本文** | ○ |  |
| 独白・心の声 | ○（朗読対象） |  |
| ト書きのみの行 `（ざわめく…）` |  | × |
| `【場面】`・見出し・`---` |  | × |
| メタ行（`**ジャンル**：` `**主人公**：` 等） |  | × |
| サムネ行の `「」` 内 | ○（**別枠**でカウント。本編と二重にしない） |  |

## シナリオ末尾テンプレ

```markdown
---

## 📊 セリフ文字カウント（参考）

- **本編**（`**名前**：` 行・先頭の（演技指示）除く）：**○○○○** 文字
- **サムネ「」内のみ**（任意・本編と別枠）：**○○** 文字
- **合算**（本編＋サムネ）：**○○○○** 文字

※集計方法：`.cursor/skills/villainess-scenario/dialogue-count.md` に準拠。
```

## 機械集計の例（Python）

完成 `.md` のパスを `path` に指定して実行。

```python
import re
path = "（完成シナリオ.md）"
text = open(path, encoding="utf-8").read()
line_pat = re.compile(r"^\*\*([^*]+)\*\*[：:](.*)$", re.MULTILINE)
skip = {"ジャンル", "主人公", "新相手", "元婚約者", "ヒロイン悪役"}

def strip_directions(s):
    s = s.strip()
    while True:
        m = re.match(r"^（[^）]*）", s)
        if not m:
            break
        s = s[m.end():].lstrip()
    return s

total, thumb = 0, 0
for m in line_pat.finditer(text):
    name = m.group(1).strip()
    rest = m.group(2)
    if name in skip:
        continue
    if name.startswith("右サムネ") or name.startswith("左サムネ"):
        thumb += sum(len(q) for q in re.findall(r"「([^」]*)」", rest))
        continue
    body = strip_directions(rest)
    if body:
        total += len(body)
print("本編:", total, "サムネ「」内:", thumb, "合算:", total + thumb)
```

**執筆完了時**：上記で数値を算出し、シナリオ末尾のテンプレに埋める。
