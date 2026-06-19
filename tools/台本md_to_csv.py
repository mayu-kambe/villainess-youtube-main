#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台本(Markdown) → CSV変換ツール  ［断罪セレナーデ／純愛レクイエム共通］

生成プロンプトが出力する Markdown 台本を、画像生成ツールに渡せる
CSV（A=No. / B=シーン / C=キャラクター / D=セリフ / E=状況 / F=文字数 / G=BGM / H=編集指示）
に変換する。生成プロンプト本体は一切変更しない。

【使い方】
    python3 tools/台本md_to_csv.py "シナリオ/【ルクレツィア①】....md"
    → 同じ場所に「....台本.csv」を書き出す（出力先は第2引数で指定も可）。

【変換ルール】
  - 章見出し ## 🎬 プロローグ → 【導入】 / 第N章 → 【シーンN】 / エピローグ → 【エピローグ】
  - 【場面】場所。時間   → シーン列＝「【ラベル】場所／時間」（。を／に置換）
  - **キャラ**：（演技指示）セリフ  → 1行（キャラ=C / セリフ=D / 演技指示=Eの種）
       ・（独白/モノローグ/心の声…）が付くと キャラ名に「（モノローグ）」を付与
  - 行頭が（…）だけの行（ト書き）       → キャラ・セリフ空欄、状況にその文を入れる
  - 文字数(F)＝セリフの文字数を自動計算
  - BGM(G)・編集指示(H)は空欄（人が後から入れる）
  ※「状況」は構造変換の“たたき台”。絵コンテ品質への作り込みは別途。
"""
import re, csv, sys, os

PAREN = r'[（(][^）)]*[）)]'           # 全角/半角どちらの括弧も拾う
MONO_KW = ('独白', 'モノローグ', '心の声', '心中')
SKIP_SPEAKERS = ('右サムネ', '左サムネ', 'サムネ', 'ジャンル')

def chapter_label(text):
    """章見出しの本文からシーンラベルを決める。対象外章なら None。"""
    if 'プロローグ' in text:
        return '導入'
    m = re.search(r'第\s*([0-9０-９]+)\s*章', text)
    if m:
        n = m.group(1).translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        return f'シーン{n}'
    if 'エピローグ' in text:
        return 'エピローグ'
    return None      # 例：「セリフ文字カウント」等 → そこ以降は対象外

def scene_text(raw):
    """【場面】の後ろの文を整形（最初の『。』を『／』に）。"""
    t = raw.strip()
    # 場所。時間 → 場所／時間（最初の句点のみ。回想等の頭の（）はそのまま残す）
    return t.replace('。', '／', 1).rstrip('。／ ')

def split_directions(rest):
    """セリフ本文から（演技指示）を抜き出す。戻り値=(セリフ, [演技指示文...], モノローグか)"""
    directions = re.findall(PAREN, rest)
    serif = re.sub(PAREN, '', rest).strip()
    is_mono = any(any(k in d for k in MONO_KW) for d in directions)
    sit_parts = []
    for d in directions:
        inner = d.strip('（）()').strip()
        # 種別ワード（独白等）と直後の読点を除去し、残りだけ状況の種に
        inner = re.sub(r'^(独白|モノローグ|心の声|心中)[、，]?\s*', '', inner).strip()
        if inner:
            sit_parts.append(inner)
    return serif, sit_parts, is_mono

def convert(md_path, csv_path=None):
    with open(md_path, encoding='utf-8') as fh:
        lines = fh.read().splitlines()

    rows = [['No.', 'シーン', 'キャラクター', 'セリフ', '状況', '文字数', 'BGM', 'とあ様へ：編集指示']]
    no = 0
    cur_label = None          # 現在の章ラベル（None＝対象外/未開始）
    cur_scene = ''            # 現在のシーン列の値

    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith('## '):
            head = s[3:].strip()
            cur_label = chapter_label(head)
            continue
        if cur_label is None:
            continue          # プロローグ前（タイトル/サムネ）や対象外章はスキップ
        if s.startswith('【場面】'):
            cur_scene = f'【{cur_label}】{scene_text(s[len("【場面】"):])}'
            continue

        m = re.match(r'^\*\*(.+?)\*\*\s*[:：]\s*(.*)$', s)
        if m:
            name, rest = m.group(1).strip(), m.group(2)
            if any(name.startswith(x) for x in SKIP_SPEAKERS):
                continue
            serif, sit_parts, is_mono = split_directions(rest)
            char = name
            if is_mono and '（' not in name and '(' not in name:
                char = f'{name}（モノローグ）'
            no += 1
            rows.append([str(no), cur_scene, char, serif,
                         '／'.join(sit_parts), str(len(serif)) if serif else '', '', ''])
            continue

        # 行頭が（…）だけ＝ト書き行
        if re.match(r'^' + PAREN + r'.*$', s) and (s.startswith('（') or s.startswith('(')):
            inner = s.strip().strip('（）()').strip()
            no += 1
            rows.append([str(no), cur_scene, '', '', inner, '', '', ''])
            continue
        # それ以外（区切り線・地の文など）は無視

    if csv_path is None:
        base = os.path.splitext(md_path)[0]
        csv_path = base + '_台本.csv'
    with open(csv_path, 'w', encoding='utf-8', newline='') as fh:
        csv.writer(fh).writerows(rows)
    return csv_path, len(rows) - 1

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('使い方: python3 tools/台本md_to_csv.py <台本.md> [出力.csv]')
        sys.exit(1)
    out, n = convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f'変換完了: {n}行 → {out}')
