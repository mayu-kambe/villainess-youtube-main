#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台本(Markdown) → CSV変換ツール  ［断罪セレナーデ／純愛レクイエム共通］

生成プロンプトが出力する Markdown 台本を、画像生成ツールに渡せる
CSV（A=No. / B=シーン / C=キャラクター / D=セリフ / E=状況 / F=文字数 / G=BGM / H=編集指示
      / I=効果音 / J=場面テロップ）に変換する。生成プロンプト本体は一切変更しない。
  ※ I・J列は右端に追加。画像ツールはA〜F列(位置0-5)しか読まないため画像生成に無影響。

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
  - BGM(G)・効果音(I)は空欄（人が後から入れる）
  - 編集指示(H)＝状況・話者から演出メモを自動生成
       （心の声/回想/暗転/怒りの叫び/効果音/テロップ/クロスディゾルブ）
       ・クロスディゾルブ＝別れ・退場・切ない所作の直後に場面が変わる境界だけ（稀に）
  - 場面テロップ(J)＝【場面】の場所が変わった最初の行に「時系列｜場所」を自動付与
       ・時系列は時間語（数日後/翌朝/〜年後 等）がある時だけ上段に。無ければ場所のみ。
  ※「状況」は構造変換の“たたき台”。絵コンテ品質への作り込みは別途。
"""
import re, csv, sys, os

PAREN = r'[（(][^）)]*[）)]'           # 全角/半角どちらの括弧も拾う
MONO_KW = ('独白', 'モノローグ', '心の声', '心中')
SKIP_SPEAKERS = ('右サムネ', '左サムネ', 'サムネ', 'ジャンル')
TIME_JUMP_EXTRACT = re.compile(
    r'(翌朝|翌日|翌晩|翌週|翌年|その夜|その後|後日|数日後|数週間後|数ヶ月後|数年後|数時間後|'
    r'[一二三四五六七八九十百千〇0-9０-９]+\s*(?:年|ヶ月|か月|カ月|週間|日|時間|分)後|'
    r'しばらく後|まもなく|やがて)')


def extract_time_jump(time_str):
    """時間欄の説明文から、時系列ジャンプ語だけを抜き出す（無ければ空）。"""
    m = TIME_JUMP_EXTRACT.search(time_str or '')
    return m.group(1) if m else ''


# 編集指示(H)の自動生成に使う検出セット。状況から拾った演出を人が読める形で要約する。
SE_LABELS = [(r'扉|ドア', '扉'), (r'ガラス|割れ|砕け', 'ガラス'), (r'足音', '足音'),
             (r'雷|稲妻|雷鳴', '雷'), (r'鳥|さえずり', '鳥'),
             (r'衝撃|息を呑|ハッと|驚愕', '衝撃')]
ANGER_RE = re.compile(r'怒鳴|怒号|激昂|憤|苛立|苛々|声を荒げ|声を張り上げ|罵|怒気|逆上|睨みつけ|怒り|どなり|わめ|キレ|喝')
# クロスディゾルブ（マニュアル§5・§7「切ない場面は稀に」）。別れ・退場・切ない所作→場面転換の境界だけ。
PARTING_RE = re.compile(r'背を向け|去ってい|立ち去|歩き去|走り去|見送|遠ざか|消えてい|別れ')
SORROW_RE = re.compile(r'切な|哀し|悲し|儚|胸が締|肩を落と|うつむ')


def build_edit_note(char, serif, sit, telop):
    """状況・話者から、編集者(とあ様)向けの演出メモ(H列)を自動生成する。
    ここに書く語は編集ツールが状況から既に検出する物と一致＝二重検出にならない。"""
    notes = []
    if 'モノローグ' in char or '心の声' in char:
        notes.append('心の声バルーン')
    if '回想' in char:
        notes.append('回想（セピア＋フェード）')
    if '暗転' in sit:
        notes.append('暗転（徐々に）')
    if ANGER_RE.search(f'{sit}{serif}') and ('！' in serif or '!' in serif):
        notes.append('怒りの叫び（ギザギザ吹き出し）')
    for pat, label in SE_LABELS:
        if re.search(pat, sit):
            notes.append(f'効果音：{label}')
            break
    if telop:
        notes.append(f'場面テロップ表示（{telop}）')
    return ' / '.join(notes)


def split_place_time(scene_cell):
    """シーン列「【ラベル】場所／時間」→ (場所, 時間)。ラベル・先頭の（回想）等を除去。"""
    s = re.sub(r'^【.*?】', '', (scene_cell or '').strip()).strip()
    s = re.sub(r'^[（(][^）)]*[）)]\s*', '', s).strip()   # 先頭の（回想）等を除く
    if not s:
        return '', ''
    parts = re.split(r'[／/]', s, maxsplit=1)
    return parts[0].strip(), (parts[1].strip() if len(parts) == 2 else '')

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

    rows = [['No.', 'シーン', 'キャラクター', 'セリフ', '状況', '文字数',
             'BGM', 'とあ様へ：編集指示', '効果音', '場面テロップ']]
    no = 0
    cur_label = None          # 現在の章ラベル（None＝対象外/未開始）
    cur_scene = ''            # 現在のシーン列の値
    prev_place = ''           # 直前シーンの場所（場面テロップ自動判定用）
    pending_telop = ''        # 次に出す行へ付ける場面テロップ（場所が変わった時にセット）
    pending_dissolve = False  # 次に出す行をクロスディゾルブにする（切ない転換）
    last_sit = ''             # 直前に出した行の状況（切ない転換の判定用）

    def emit(char, serif, sit):
        """1行を確定。編集指示(H)を自動生成し、場所が変われば J列(場面テロップ) を付ける。"""
        nonlocal no, pending_telop, pending_dissolve, last_sit
        no += 1
        note = build_edit_note(char, serif, sit, pending_telop)   # H列＝演出メモ
        if pending_dissolve:                                      # 切ない転換→ディゾルブ
            note = 'クロスディゾルブ（切ない転換）' + (' / ' + note if note else '')
            pending_dissolve = False
        rows.append([str(no), cur_scene, char, serif, sit,
                     str(len(serif)) if serif else '', '', note, '', pending_telop])
        pending_telop = ''    # テロップは新場面の先頭1行だけ
        last_sit = sit

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
            place, ptime = split_place_time(cur_scene)
            if place and place != prev_place:        # 場所が変わった→次の行にテロップ
                tl = extract_time_jump(ptime)
                pending_telop = f'{tl}｜{place}' if tl else place
                if PARTING_RE.search(last_sit) or SORROW_RE.search(last_sit):
                    pending_dissolve = True           # 直前が別れ/切ない→この場面へディゾルブ
            if place:
                prev_place = place
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
            emit(char, serif, '／'.join(sit_parts))
            continue

        # 行頭が（…）だけ＝ト書き行
        if re.match(r'^' + PAREN + r'.*$', s) and (s.startswith('（') or s.startswith('(')):
            inner = s.strip().strip('（）()').strip()
            emit('', '', inner)
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
