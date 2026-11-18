#!/usr/bin/env python3
"""Vidhuk.ua parser prototype for otzyvtut import (facts only, no review texts).

Reads donor company cards (server HTML), extracts JSON-LD facts:
name, description, aggregate rating, review count, plus page views counter.
Dedupes against existing otzyvtut companies (from the SQL dump).
Outputs ranked candidates JSONL sorted by donor views (demand signal).
"""
import json, re, subprocess, sys, time, random

BASE = "/home/hatch/workspace/goals/goal/hidden_files"
SITEMAP = BASE + "/parser/vidhuk_sitemap_organizations_2026-10-20.xml"
DUMP = BASE + "/db_analysis/otzyvtut.sql"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

def fetch(url, timeout=40):
    r = subprocess.run(["curl", "-s", "--max-time", str(timeout), "-A", UA, url],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""

def descr_block_text(html, name):
    """Full company description from the #descr block (v2)."""
    i = html.find('id="descr"')
    if i < 0:
        return ""
    seg = html[i:i + 9000]
    txt = re.sub(r"<[^>]+>", " ", seg)
    txt = txt.replace("&laquo;", "«").replace("&raquo;", "»").replace("&ndash;", "–")
    txt = txt.replace("&#39;", "'").replace("&quot;", '"').replace("&nbsp;", " ")
    txt = re.sub(r"&[a-z#0-9]+;", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    txt = re.split(r"детальніше|Рейтинг\s*[\d.,]+\s*з\s*5", txt)[0].strip()
    txt = re.sub(r'^id="descr"[^>]*>\s*', "", txt)
    if name and txt.lower().startswith(name.lower()):
        txt = txt[len(name):].strip(" -—:").strip()
    # cut trailing website CTA remnants
    txt = re.split(r"\sПерейти на сайт\b", txt)[0].strip()
    return txt


def parse_card(url, html):
    m = re.search(r'application/ld\+json">(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        ld = json.loads(m.group(1))
    except Exception:
        return None
    if not isinstance(ld, dict) or "name" not in ld:
        return None
    name = ld.get("name", "").strip()
    views = None
    vm = re.search(r'rtngviews">\s*/\s*([\d\s]+)\s*переглядів', html)
    if not vm:
        vm = re.search(r'([\d][\d\s]{2,})\s*переглядів', html)
    if vm:
        views = int(vm.group(1).replace(" ", ""))
    agg = ld.get("aggregateRating") or {}
    desc_ld = re.sub(r"\s+", " ", (ld.get("description") or "")).strip()
    desc_full = descr_block_text(html, name)
    # contamination guard: sidebar "related companies" lists leak into #descr on some cards
    if desc_full.count("Рейтинг:") >= 2 or "Відгуки про роботодавців" in desc_full:
        desc_full = ""
    # JS junk guard: inline chart scripts leak into #descr text on some cards
    if "document.getElementById" in desc_full or "var canvas" in desc_full:
        m2 = re.search(re.escape(name.split('/')[0].strip()) + r"\s+(це|—|-)", desc_full)
        desc_full = desc_full[m2.start():] if m2 else ""
    description = desc_full if len(desc_full) > len(desc_ld) else desc_ld
    if description.count("Рейтинг:") >= 2:
        description = desc_ld if desc_ld.count("Рейтинг:") < 2 else ""
    stub = len(description) < 60
    return {
        "donor_url": url,
        "name": name,
        "description": "" if stub else description,
        "desc_stub": stub,
        "rating": agg.get("ratingValue"),
        "reviews": agg.get("reviewCount"),
        "views": views,
        "site": ld.get("url"),
    }

def norm_name(t):
    t = (t or "").lower()
    t = re.sub(r"отзывы|відгуки|reviews?", "", t)
    t = re.sub(r"[^a-zа-яёіїєґ0-9]+", " ", t)
    return " ".join(t.split())

def existing_companies():
    src = open(BASE + "/db_analysis/analyze.py").read()
    ns = {}
    sys.argv = ["x", DUMP]
    exec(src[:src.find("def main")], ns)
    names, slugs = set(), set()
    for cols, rows in ns["iter_inserts"](DUMP, "wp_posts"):
        idx = {c: i for i, c in enumerate(cols)}
        for r in rows:
            if r[idx["post_type"]] == "companies" and r[idx["post_status"]] in ("publish", "draft"):
                names.add(norm_name(r[idx["post_title"]]))
                slugs.add((r[idx["post_name"]] or "").lower())
    # cards imported after the dump was taken (test batch and later imports)
    import os, glob
    for extra in glob.glob(BASE + "/parser/import_*.txt") + [BASE + "/parser/test_import_25.txt"]:
        if os.path.exists(extra):
            for line in open(extra, encoding="utf-8"):
                t = line.split("|||")[0].strip()
                if t:
                    names.add(norm_name(t))
    return names, slugs

def sitemap_urls():
    xml = open(SITEMAP, encoding="utf-8").read()
    urls = re.findall(r"<loc>(https://www\.vidhuk\.ua/uk/[^<]+/otzyvy-klientov)</loc>", xml)
    return sorted(set(urls))

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "sample"
    urls = sitemap_urls()
    print(f"sitemap client-review urls: {len(urls)}", file=sys.stderr)
    outname = "candidates_raw.jsonl"
    if mode == "sample":
        step = int(sys.argv[2]) if len(sys.argv) > 2 else 180
        pool = urls[::step]
    elif mode == "pool":
        # niche pool: slugs containing any of the keywords in argv[2] (comma-separated)
        keys = sys.argv[2].split(",")
        tag = sys.argv[3] if len(sys.argv) > 3 else "pool"
        pool = [u for u in urls if any(k in u for k in keys)]
        random.shuffle(pool)
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 300
        pool = pool[:limit]
        outname = f"candidates_{tag}.jsonl"
        print(f"pool '{tag}': {len(pool)} urls", file=sys.stderr)
    else:
        pool = urls
    names, slugs = existing_companies()
    print(f"existing companies: {len(names)} names", file=sys.stderr)
    out = open(BASE + "/parser/" + outname, "w", encoding="utf-8")
    stats = {"fetched": 0, "parsed": 0, "dupe_name": 0, "kept": 0}
    for i, url in enumerate(pool):
        html = fetch(url)
        stats["fetched"] += 1
        if not html:
            continue
        card = parse_card(url, html)
        if not card:
            continue
        stats["parsed"] += 1
        card["is_dupe"] = norm_name(card["name"]) in names
        if card["is_dupe"]:
            stats["dupe_name"] += 1
        else:
            stats["kept"] += 1
        out.write(json.dumps(card, ensure_ascii=False) + "\n")
        out.flush()
        if i % 25 == 0:
            print(f"  {i}/{len(pool)} stats={stats}", file=sys.stderr)
        time.sleep(random.uniform(1.2, 2.4))
    out.close()
    print("DONE", stats, file=sys.stderr)
