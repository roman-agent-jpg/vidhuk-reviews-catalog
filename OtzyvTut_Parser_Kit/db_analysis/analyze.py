#!/usr/bin/env python3
"""Read-only analysis of otzyvtut.sql dump: companies, categories, reviews, duplicates."""
import re, sys, json
from collections import Counter, defaultdict

PATH = sys.argv[1]

def parse_values(text):
    """Parse MySQL VALUES tuples from an INSERT statement body."""
    rows = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == '(':
            row = []
            i += 1
            while i < n:
                c = text[i]
                if c == "'":
                    # string
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
                elif c == ' ' or c == '\n' or c == '\t' or c == '\r':
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
    """Yield (columns, rows) for each INSERT INTO `table` statement."""
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
                        cols = [c.strip(' `') for c in m.group(1).split(',')]
                        yield cols, parse_values(m.group(2))
                    buf = []
                continue
            if capturing:
                buf.append(line)
                if line.rstrip().endswith(';'):
                    capturing = False
                    m = pat.search(''.join(buf))
                    if m:
                        cols = [c.strip(' `') for c in m.group(1).split(',')]
                        yield cols, parse_values(m.group(2))
                    buf = []

out = {}

# --- posts ---
posts = {}
for cols, rows in iter_inserts(PATH, 'wp_posts'):
    idx = {c: k for k, c in enumerate(cols)}
    for r in rows:
        posts[r[idx['ID']]] = {
            'title': r[idx['post_title']], 'status': r[idx['post_status']],
            'type': r[idx['post_type']], 'name': r[idx['post_name']],
            'date': r[idx['post_date']], 'modified': r[idx['post_modified']],
            'content_len': len(r[idx['post_content']] or ''),
            'comments': r[idx['comment_count']],
        }
by_type_status = Counter((p['type'], p['status']) for p in posts.values())
out['posts_by_type_status'] = {f"{t}/{s}": c for (t, s), c in sorted(by_type_status.items())}
companies = {pid: p for pid, p in posts.items() if p['type'] == 'companies'}
out['companies_total'] = len(companies)

def norm(name):
    n = (name or '').lower().strip()
    n = re.sub(r'[^a-zа-яёїієґ0-9]+', ' ', n)
    return re.sub(r'\s+', ' ', n).strip()

dup_groups = defaultdict(list)
for pid, p in companies.items():
    dup_groups[norm(p['title'])].append((pid, p['status'], p['title']))
dups = {k: v for k, v in dup_groups.items() if len(v) > 1 and k}
out['company_duplicate_groups'] = len(dups)
out['company_duplicate_extra_cards'] = sum(len(v) - 1 for v in dups.values())
out['dup_examples'] = [v for k, v in list(dups.items())[:15]]

drafts = {pid: p for pid, p in companies.items() if p['status'] == 'draft'}
out['drafts_total'] = len(drafts)
out['drafts_no_content'] = sum(1 for p in drafts.values() if p['content_len'] < 50)
out['drafts_modified_max'] = max((p['modified'] for p in drafts.values()), default=None)
pub = {pid: p for pid, p in companies.items() if p['status'] == 'publish'}
out['published_no_content'] = sum(1 for p in pub.values() if p['content_len'] < 50)
out['published_modified_max'] = max((p['modified'] for p in pub.values()), default=None)

# --- terms / taxonomies ---
terms = {}
for cols, rows in iter_inserts(PATH, 'wp_terms'):
    idx = {c: k for k, c in enumerate(cols)}
    for r in rows:
        terms[r[idx['term_id']]] = r[idx['name']]
tt = {}
for cols, rows in iter_inserts(PATH, 'wp_term_taxonomy'):
    idx = {c: k for k, c in enumerate(cols)}
    for r in rows:
        tt[r[idx['term_taxonomy_id']]] = (r[idx['term_id']], r[idx['taxonomy']], r[idx['count']])
cat_names = {tid: terms.get(tid) for tid, (term_id, tax, cnt) in tt.items() if tax == 'company_categories'}
out['company_categories_total'] = len(cat_names)
out['company_categories'] = sorted([terms.get(term_id) for tid, (term_id, tax, cnt) in tt.items() if tax == 'company_categories'])
rel_counts = Counter()
comp_cats = defaultdict(set)
for cols, rows in iter_inserts(PATH, 'wp_term_relationships'):
    idx = {c: k for k, c in enumerate(cols)}
    for r in rows:
        ttid = r[idx['term_taxonomy_id']]
        if ttid in tt and tt[ttid][1] == 'company_categories':
            rel_counts[ttid] += 1
            comp_cats[r[idx['object_id']]].add(tt[ttid][0])
out['companies_without_category'] = sum(1 for pid in companies if pid not in comp_cats)
out['drafts_without_category'] = sum(1 for pid in drafts if pid not in comp_cats)

# --- postmeta keys for companies ---
meta_keys = Counter()
comp_meta = defaultdict(set)
want_ids = set(companies.keys())
for cols, rows in iter_inserts(PATH, 'wp_postmeta'):
    idx = {c: k for k, c in enumerate(cols)}
    for r in rows:
        if r[idx['post_id']] in want_ids:
            meta_keys[r[idx['meta_key']]] += 1
            comp_meta[r[idx['post_id']]].add(r[idx['meta_key']])
out['company_meta_keys'] = meta_keys.most_common(30)

# --- reviews ---
rev_total = 0
rev_by_mod = Counter(); rev_by_rate = Counter(); rev_by_year = Counter()
rev_per_company = Counter(); rev_spam = 0; rev_hidden = 0
rev_latest = ''
for cols, rows in iter_inserts(PATH, 'wp_reviews'):
    idx = {c: k for k, c in enumerate(cols)}
    for r in rows:
        rev_total += 1
        rev_by_mod[r[idx['status_moderation']]] += 1
        rev_by_rate[r[idx['review_rate']]] += 1
        d = r[idx['date_added']] or ''
        rev_by_year[d[:4]] += 1
        if d > rev_latest: rev_latest = d
        rev_per_company[r[idx['company_id']]] += 1
        if r[idx['is_spam']] == '1': rev_spam += 1
        if r[idx['is_hidden']] == '1': rev_hidden += 1
out['reviews_total'] = rev_total
out['reviews_by_moderation'] = dict(rev_by_mod)
out['reviews_by_rate'] = dict(rev_by_rate)
out['reviews_by_year'] = dict(sorted(rev_by_year.items()))
out['reviews_latest'] = rev_latest
out['reviews_spam'] = rev_spam
out['reviews_hidden'] = rev_hidden
out['companies_with_reviews'] = len(rev_per_company)
top = rev_per_company.most_common(15)
out['top_companies_by_reviews'] = [(companies.get(cid, {}).get('title', cid), cnt) for cid, cnt in top]

print(json.dumps(out, ensure_ascii=False, indent=1))
