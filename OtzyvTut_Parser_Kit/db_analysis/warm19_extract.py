#!/usr/bin/env python3
"""Warm-19 outreach prep: contacts from card descriptions + visible-negative counts.
Source: otzyvtut.sql dump 2026-10-20 (pre-moderation). Post-moderation estimate:
pending non-hidden reviews were ~90% published on 2026-10-21, so visible negatives now
~ (status=1, hidden=0, rate<=2) + (status=0, hidden=0, rate<=2). Estimate, not live data."""
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

TARGETS = {
    'PLC Group': ['plc group', 'плс груп', 'plc'],
    'Union Job': ['union job'],
    'Gold Work': ['gold work', 'голд ворк', 'goldwork'],
    'Nikoloz-Job': ['nikoloz'],
    'Work Life': ['work life', 'ворк лайф', 'worklife'],
    'Europe Service': ['europe service'],
    'EU.RO Group': ['eu.ro'],
    'Job Inter': ['job inter'],
    'Profi Praca': ['profi praca'],
    'International Work': ['international work'],
    'Denisiuk job': ['denisiuk', 'денисюк'],
    'WAY UP': ['way up'],
    'International Business': ['international business'],
    'Марисюк': ['марисюк', 'marisyuk'],
    'Rozetka': ['rozetka', 'розетка'],
    'European Visa': ['european visa'],
    'Sobiauto': ['sobiauto'],
    'Кириченко': ['кириченко', 'kyrychenko'],
    'Just School': ['just school'],
}

def match_target(title):
    t = (title or '').lower()
    for name, keys in TARGETS.items():
        if any(k in t for k in keys):
            return name
    return None

companies = {}  # target -> list of post dicts
for cols, rows in iter_inserts(PATH, 'wp_posts'):
    idx = {c: k for k, c in enumerate(cols)}
    if 'post_title' not in idx:
        continue
    for r in rows:
        if r[idx['post_type']] not in ('company', 'companies'):
            continue
        tgt = match_target(r[idx['post_title']])
        if tgt:
            companies.setdefault(tgt, []).append({
                'id': r[idx['ID']], 'title': r[idx['post_title']],
                'status': r[idx['post_status']], 'slug': r[idx['post_name']],
                'content': r[idx['post_content']] or '',
            })

id2target = {}
for tgt, posts in companies.items():
    for p in posts:
        id2target[p['id']] = tgt

stats = defaultdict(lambda: {'vis_neg': 0, 'pend_neg': 0, 'hidden': 0, 'total_vis': 0, 'rates': []})
for cols, rows in iter_inserts(PATH, 'wp_reviews'):
    idx = {c: k for k, c in enumerate(cols)}
    for r in rows:
        cid = r[idx['company_id']]
        if cid not in id2target:
            continue
        s = stats[id2target[cid]]
        rate = r[idx['review_rate']]
        try:
            rate_i = int(rate)
        except (TypeError, ValueError):
            rate_i = 0
        hidden = r[idx['is_hidden']] == '1'
        status = r[idx['status_moderation']]
        if hidden:
            s['hidden'] += 1
        elif status == '1':
            s['total_vis'] += 1
            s['rates'].append(rate_i)
            if 1 <= rate_i <= 2:
                s['vis_neg'] += 1
        elif status == '0':
            if 1 <= rate_i <= 2:
                s['pend_neg'] += 1
            s['rates'].append(rate_i)

EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]{2,}')
PHONE = re.compile(r'\+?\d[\d\s()\-]{9,}\d')
URL = re.compile(r'https?://[^\s"\'<>]+|[\w-]+\.(?:com\.ua|ua|com|net|org|eu|pl|de|md|ro)\b')
TG = re.compile(r'(?:t\.me/|@)[A-Za-z0-9_]{4,}')

def contacts(text):
    text = re.sub(r'<[^>]+>', ' ', text or '')
    emails = sorted(set(EMAIL.findall(text)))
    phones = sorted(set(p.strip() for p in PHONE.findall(text) if sum(ch.isdigit() for ch in p) >= 10))
    urls = sorted(set(u.rstrip('.,;)') for u in URL.findall(text)))[:5]
    tgs = sorted(set(TG.findall(text)))[:3]
    return emails, phones[:4], urls, tgs

out = ['# Тёплые 19 — подготовка аутрича (данные дампа 2026-10-20 + оценка после модерации 2026-10-21)',
       '', 'Видимый негатив сейчас ≈ «было видно» + «добавила модерация» (pending не скрытые, ~90% опубликованы).', '']
for tgt in TARGETS:
    posts = companies.get(tgt, [])
    s = stats.get(tgt, {'vis_neg': 0, 'pend_neg': 0, 'hidden': 0, 'total_vis': 0, 'rates': []})
    avg = round(sum(s['rates']) / len(s['rates']), 1) if s['rates'] else None
    out.append(f"## {tgt}")
    for p in posts:
        out.append(f"- Карточка ID {p['id']} ({p['status']}): {p['title']} — https://otzyvtut.com/{p['slug']}/")
        e, ph, u, tg = contacts(p['content'])
        if e: out.append(f"  - Email: {', '.join(e)}")
        if ph: out.append(f"  - Тел: {', '.join(ph)}")
        if u: out.append(f"  - Сайт/ссылки: {', '.join(u)}")
        if tg: out.append(f"  - Telegram: {', '.join(tg)}")
        if not (e or ph or u or tg): out.append('  - Контактов в описании нет')
    out.append(f"- Скрыто оплаченных: {s['hidden']} | Негатив 1–2★: было видно {s['vis_neg']}, модерация добавила ~{s['pend_neg']} | Всего видимых отзывов: {s['total_vis']} | Ср. рейтинг ~{avg}")
    out.append('')

open('/home/hatch/workspace/goals/goal/hidden_files/warm19_sheet.md', 'w', encoding='utf-8').write('\n'.join(out))
print(json.dumps({'companies_found': {k: len(v) for k, v in companies.items()}, 'missing': [t for t in TARGETS if t not in companies]}, ensure_ascii=False))
