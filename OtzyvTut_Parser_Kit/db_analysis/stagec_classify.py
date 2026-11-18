#!/usr/bin/env python3
"""Stage C: classify draft companies from the SQL dump (read-only)."""
import sys, re, json
sys.argv = ["x", "/home/hatch/workspace/goals/goal/hidden_files/db_analysis/otzyvtut.sql"]
src = open("/home/hatch/workspace/goals/goal/hidden_files/db_analysis/analyze.py").read()
ns = {}
exec(src[:src.find("def main")], ns)
iter_inserts = ns['iter_inserts']
PATH = sys.argv[1]
from collections import Counter, defaultdict

posts = {}
for cols, rows in iter_inserts(PATH, 'wp_posts'):
    idx = {c: i for i, c in enumerate(cols)}
    for r in rows:
        if r[idx['post_type']] == 'companies':
            posts[int(r[idx['ID']])] = {
                'title': r[idx['post_title']], 'status': r[idx['post_status']],
                'content_len': len(re.sub('<[^>]+>', '', r[idx['post_content']] or '').strip())}

terms, tt = {}, {}
for cols, rows in iter_inserts(PATH, 'wp_terms'):
    idx = {c: i for i, c in enumerate(cols)}
    for r in rows: terms[int(r[idx['term_id']])] = r[idx['name']]
for cols, rows in iter_inserts(PATH, 'wp_term_taxonomy'):
    idx = {c: i for i, c in enumerate(cols)}
    for r in rows: tt[int(r[idx['term_taxonomy_id']])] = (int(r[idx['term_id']]), r[idx['taxonomy']])
cats = defaultdict(list)
for cols, rows in iter_inserts(PATH, 'wp_term_relationships'):
    idx = {c: i for i, c in enumerate(cols)}
    for r in rows:
        t = tt.get(int(r[idx['term_taxonomy_id']]))
        if t and t[1] == 'company_categories':
            cats[int(r[idx['object_id']])].append(terms.get(t[0], '?'))

revcount = Counter()
for cols, rows in iter_inserts(PATH, 'wp_reviews'):
    idx = {c: i for i, c in enumerate(cols)}
    for r in rows:
        if r[idx['status_moderation']] == '1':
            revcount[int(r[idx['company_id']])] += 1

def norm(t):
    t = t.lower()
    t = re.sub(r'отзывы|відгуки|reviews?', '', t)
    t = re.sub(r'[^a-zа-яёіїєґ0-9]+', ' ', t)
    return ' '.join(t.split())

published_norm = defaultdict(list)
for pid, p in posts.items():
    if p['status'] == 'publish':
        published_norm[norm(p['title'])].append(pid)

drafts = {pid: p for pid, p in posts.items() if p['status'] == 'draft'}
out = {'total': len(drafts), 'empty_no_reviews': [], 'dup_of_published': [],
       'dup_of_draft': [], 'publishable': [], 'draft_with_reviews_unique': []}
seen_draft_norm = {}
for pid, p in sorted(drafts.items()):
    n = norm(p['title'])
    e = {'id': pid, 'title': p['title'][:90], 'len': p['content_len'],
         'reviews': revcount.get(pid, 0), 'cats': cats.get(pid, [])}
    if n in published_norm:
        e['published_ids'] = published_norm[n]
        out['dup_of_published'].append(e)
    elif n in seen_draft_norm:
        e['first_draft_id'] = seen_draft_norm[n]
        out['dup_of_draft'].append(e)
    elif p['content_len'] < 50 and revcount.get(pid, 0) == 0:
        out['empty_no_reviews'].append(e)
    elif revcount.get(pid, 0) > 0:
        out['draft_with_reviews_unique'].append(e)
    else:
        out['publishable'].append(e)
    seen_draft_norm.setdefault(n, pid)

with open('/home/hatch/workspace/goals/goal/hidden_files/db_analysis/stagec_result.json', 'w') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
for k, v in out.items():
    print(k, len(v) if isinstance(v, list) else v)
