#!/usr/bin/env python3
"""Facts for editorial overviews of top-10 cards: description + our own review stats + samples.
Source: otzyvtut.sql dump 2026-10-20. Visible-now estimate = status 1 or 0 (moderation published ~90% of pending), hidden excluded."""
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
    'EU.RO Group': ['eu.ro'],
    'Europe Service': ['europe service'],
    'Union Job': ['union job'],
    'International Work': ['international work'],
    'Равес': ['равес', 'raves'],
    'Nikoloz-Job': ['nikoloz'],
    'ШвидкоГроші': ['швидкогроші', 'швидко гроші', 'shvydko', 'sgroshi'],
    'Violity': ['violity'],
    'PLC Group': ['plc group'],
    'European Visa': ['european visa'],
}

def match(title):
    t = (title or '').lower()
    for name, keys in TARGETS.items():
        if any(k in t for k in keys):
            return name
    return None

cards = {}
for cols, rows in iter_inserts(PATH, 'wp_posts'):
    idx = {c: k for k, c in enumerate(cols)}
    if 'post_title' not in idx:
        continue
    for r in rows:
        if r[idx['post_type']] not in ('company', 'companies'):
            continue
        if r[idx['post_status']] != 'publish':
            continue
        tgt = match(r[idx['post_title']])
        if tgt and tgt not in cards:
            content = re.sub(r'<[^>]+>', ' ', r[idx['post_content']] or '')
            content = re.sub(r'\s+', ' ', content).strip()
            cards[tgt] = {'id': r[idx['ID']], 'title': r[idx['post_title']], 'slug': r[idx['post_name']],
                          'desc': content[:900]}

id2tgt = {c['id']: t for t, c in cards.items()}
stats = defaultdict(lambda: {'dist': defaultdict(int), 'total': 0, 'samples_neg': [], 'samples_pos': [], 'samples_mid': []})
for cols, rows in iter_inserts(PATH, 'wp_reviews'):
    idx = {c: k for k, c in enumerate(cols)}
    text_col = 'review_text' if 'review_text' in idx else ('text' if 'text' in idx else None)
    for r in rows:
        cid = r[idx['company_id']]
        if cid not in id2tgt:
            continue
        if r[idx['is_hidden']] == '1' or r[idx['is_spam']] == '1':
            continue
        if r[idx['status_moderation']] not in ('0', '1'):
            continue
        tgt = id2tgt[cid]
        s = stats[tgt]
        try:
            rate = int(r[idx['review_rate']])
        except (TypeError, ValueError):
            rate = 0
        s['dist'][rate] += 1
        s['total'] += 1
        if text_col:
            txt = re.sub(r'\s+', ' ', (r[idx[text_col]] or '')).strip()[:280]
            if len(txt) >= 25:
                if rate <= 2 and len(s['samples_neg']) < 6:
                    s['samples_neg'].append(txt)
                elif rate >= 4 and len(s['samples_pos']) < 6:
                    s['samples_pos'].append(txt)
                elif rate == 3 and len(s['samples_mid']) < 3:
                    s['samples_mid'].append(txt)

out = {}
for tgt, c in cards.items():
    s = stats[tgt]
    dist = {str(k): v for k, v in sorted(s['dist'].items())}
    rated = sum(v for k, v in s['dist'].items() if k >= 1)
    avg = round(sum(k * v for k, v in s['dist'].items() if k >= 1) / rated, 2) if rated else None
    out[tgt] = {**c, 'reviews_total': s['total'], 'dist': dist, 'avg': avg,
                'neg': s['samples_neg'], 'pos': s['samples_pos'], 'mid': s['samples_mid']}

json.dump(out, open('/home/hatch/workspace/goals/goal/hidden_files/top10_facts.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({t: {'id': c['id'], 'total': out[t]['reviews_total'], 'avg': out[t]['avg'], 'dist': out[t]['dist']} for t, c in cards.items()}, ensure_ascii=False))
print('missing:', [t for t in TARGETS if t not in cards])
