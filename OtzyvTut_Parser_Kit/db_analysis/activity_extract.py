#!/usr/bin/env python3
"""Activity filter: which companies are alive NOW (per our own DB, dump 2026-10-20).
Signals: last review date, reviews in 2025/2026, card views, paid-hidden history."""
import re, json
from collections import defaultdict

PATH = '/home/hatch/workspace/goals/goal/hidden_files/db_analysis/otzyvtut.sql'

def parse_values(text):
    rows = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == '(':
            row = []
            i += 1
            while i < n:
                c = text[i]
                if c == "'":
                    j = i + 1
                    buf = []
                    while j < n:
                        if text[j] == '\\' and j + 1 < n:
                            buf.append(text[j+1]); j += 2; continue
                        if text[j] == "'":
                            break
                        buf.append(text[j]); j += 1
                    row.append(''.join(buf)); i = j + 1
                elif c in ',)':
                    i += 1
                    if c == ')':
                        break
                elif c in ' \n\t\r':
                    i += 1
                else:
                    j = i
                    while j < n and text[j] not in ',)':
                        j += 1
                    tok = text[i:j].strip()
                    row.append(None if tok.upper() == 'NULL' else tok)
                    i = j
            rows.append(row)
        else:
            i += 1
    return rows

def iter_inserts(path, table):
    pat = re.compile(r"INSERT INTO `" + table + r"` \(([^)]*)\) VALUES\s*(.*?);\s*$", re.S)
    buf = []
    capturing = False
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            if not capturing and line.startswith(f"INSERT INTO `{table}`"):
                capturing = True
                buf = [line]
                if line.rstrip().endswith(';'):
                    capturing = False
                    m = pat.search(''.join(buf))
                    if m:
                        yield [c.strip('` ') for c in m.group(1).split(',')], parse_values(m.group(2))
                    buf = []
                continue
            if capturing:
                buf.append(line)
                if line.rstrip().endswith(';'):
                    capturing = False
                    m = pat.search(''.join(buf))
                    if m:
                        yield [c.strip('` ') for c in m.group(1).split(',')], parse_values(m.group(2))
                    buf = []

companies = {}
for cols, rows in iter_inserts(PATH, 'wp_posts'):
    idx = {c: k for k, c in enumerate(cols)}
    if 'post_title' not in idx:
        continue
    for r in rows:
        if r[idx['post_type']] in ('company', 'companies') and r[idx['post_status']] == 'publish':
            companies[r[idx['ID']]] = {'title': r[idx['post_title']], 'slug': r[idx['post_name']], 'views': 0}

for cols, rows in iter_inserts(PATH, 'wp_postmeta'):
    idx = {c: k for k, c in enumerate(cols)}
    for r in rows:
        pid = r[idx['post_id']]
        if pid in companies and r[idx['meta_key']] == 'views':
            try:
                companies[pid]['views'] = int(r[idx['meta_value']])
            except (TypeError, ValueError):
                pass

act = defaultdict(lambda: {'total': 0, 'last': '', 'y2025': 0, 'y2026': 0, 'hidden_paid': 0, 'neg_now': 0})
for cols, rows in iter_inserts(PATH, 'wp_reviews'):
    idx = {c: k for k, c in enumerate(cols)}
    for r in rows:
        cid = r[idx['company_id']]
        if cid not in companies:
            continue
        a = act[cid]
        if r[idx['is_hidden']] == '1':
            a['hidden_paid'] += 1
            continue
        if r[idx['status_moderation']] not in ('0', '1') or r[idx['is_spam']] == '1':
            continue
        d = r[idx['date_added']] or ''
        a['total'] += 1
        if d > a['last']:
            a['last'] = d
        if d.startswith('2026'):
            a['y2026'] += 1
        elif d.startswith('2025'):
            a['y2025'] += 1
        try:
            rate = int(r[idx['review_rate']])
        except (TypeError, ValueError):
            rate = 0
        if 1 <= rate <= 2:
            a['neg_now'] += 1

rows = []
for cid, c in companies.items():
    a = act[cid]
    fresh = a['y2025'] + a['y2026']
    # activity score: fresh reviews dominate, then recency, then views
    score = fresh * 100 + (a['y2026'] * 50) + min(c['views'], 20000) / 100.0 + (200 if a['hidden_paid'] else 0)
    rows.append({'id': cid, 'title': c['title'][:60], 'slug': c['slug'], 'views': c['views'],
                 'total': a['total'], 'last': a['last'][:10], 'y2025': a['y2025'], 'y2026': a['y2026'],
                 'paid': a['hidden_paid'], 'neg': a['neg_now'], 'score': round(score, 1)})

rows.sort(key=lambda x: -x['score'])
alive = [r for r in rows if r['y2025'] + r['y2026'] > 0 or r['paid'] > 0]
out = ['# Активные компании — фильтр по собственным данным OtzyvTut (дамп 2026-10-20)',
       '',
       f"Всего опубликованных карточек: {len(rows)}. Признаки жизни (отзывы в 2025–2026 или платили за скрытие): {len(alive)}.",
       'Сортировка: свежие отзывы > отзывы 2026 > просмотры > платили раньше.', '',
       '| # | Компания | Просмотры | Отзывов всего | 2025 | 2026 | Последний отзыв | Платили (скрыто) | Негатив 1–2★ |',
       '|---|---|---|---|---|---|---|---|---|']
for i, r in enumerate(alive[:60], 1):
    out.append(f"| {i} | {r['title']} | {r['views']} | {r['total']} | {r['y2025']} | {r['y2026']} | {r['last']} | {r['paid']} | {r['neg']} |")
json.dump(rows, open('/home/hatch/workspace/goals/goal/hidden_files/activity_rows.json', 'w', encoding='utf-8'), ensure_ascii=False)
open('/home/hatch/workspace/goals/goal/hidden_files/active_targets.md', 'w', encoding='utf-8').write('\n'.join(out))
print(json.dumps({'total_cards': len(rows), 'alive': len(alive),
                  'top15': [{'t': r['title'], 'v': r['views'], 'y25': r['y2025'], 'y26': r['y2026'], 'last': r['last'], 'paid': r['paid'], 'neg': r['neg']} for r in alive[:15]]}, ensure_ascii=False))
