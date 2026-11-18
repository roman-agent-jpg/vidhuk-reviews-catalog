#!/usr/bin/env python3
"""Build import batch files (<=40 lines) from parser candidates JSONL.

Usage: build_import.py candidates_x.jsonl TAG [limit]
Selection order: detector-A first (rating>=4.8, reviews>=20), then by views desc.
Output: import_TAG_1.txt, import_TAG_2.txt, ... + import_TAG_report.md
Format per line: Title ||| term_id ||| Description (truncated to ~700 chars).
"""
import json, re, sys

TERM = {
    "mfo": 50, "bank": 13, "exchange": 48, "shops": 45, "stores": 24,
    "sites": 44, "it": 47, "delivery": 17, "medicine": 33, "clinics": 34,
    "medcenter": 35, "dentist": 36, "pharmacy": 39, "travel": 21,
    "touragent": 12, "hotel": 22, "transport": 23, "auto": 14,
    "cafe": 57, "tech": 8, "digital": 41, "zoo": 30, "fraud": 51,
    "slimming": 53, "other": 18, "jobs": 42, "beauty": 10,
}

def category(name, desc=""):
    n = (name + " " + (desc or "")).lower()
    nm = name.lower()
    if any(k in nm for k in ["школ", "курс", "академ", "academy", "school", "освіт", "навчал", "тренінг", "тренинг"]):
        return 83  # Курсы и онлайн-школы отзывы
    tokens = re.split(r"[^a-zа-яёіїєґ]+", nm)
    if (re.search(r"\bбанк\b|\bbank\b", nm) or "банк (" in nm
            or any(t.endswith("банк") and len(t) > 4 for t in tokens)
            or any(t in ("bank", "forward") for t in tokens) and "bank" in nm):
        return TERM["bank"]
    if "кредит" in nm or any(k in n for k in ["мікрозайм", "микрозайм", "кредит онлайн", "займ онлайн", "мфо", "moneyveo", "creditplus", "miloan", "швидкогроші", "кредитн", "автокредит", "лізинг", "лизинг", "credit 365", "автомані", "automoney"]):
        return TERM["mfo"]
    if any(k in n for k in ["брокер", "біржа", "биржа", "forex", "форекс", "крипто", "crypto", "трейдинг", "інвест", "инвест"]):
        return TERM["exchange"]
    if "стоматолог" in n:
        return TERM["dentist"]
    if "клінік" in n or "клиник" in n:
        return TERM["clinics"]
    if "медичн" in n or "медицин" in n:
        return TERM["medcenter"]
    if "аптек" in n:
        return TERM["pharmacy"]
    if "доставк" in n or "пошта" in n or "почта" in n:
        return TERM["delivery"]
    if "подорож" in n or "тур" in n and "оператор" in n:
        return TERM["travel"]
    if "корм" in n or "зоо" in n:
        return TERM["zoo"]
    if "похуд" in n:
        return TERM["slimming"]
    if "інтернет-магазин" in n or "интернет-магазин" in n or "інтернет магазин" in n or "интернет магазин" in n:
        return TERM["shops"]
    if "магазин" in n:
        return TERM["stores"]
    if any(k in n for k in [".com.ua", ".net", "проксі", "прокси", "сервіс онлайн", "онлайн-сервис", "платформа"]):
        return TERM["sites"]
    return TERM["other"]

def clean_desc(d, limit=700):
    d = re.sub(r"\s+", " ", (d or "")).strip().replace("|||", " ")
    if len(d) > limit:
        cut = d[:limit]
        d = cut[:cut.rfind(".") + 1] if "." in cut else cut
    return d

DENY = [
    "дельта банк", "надра банк", "імексбанк", "имэксбанк", "укрсоцбанк",
    "юникредит", "unicredit", "актив-банк", "ваб банк", "vab bank",
    "платинум банк", "фінансова ініціатива", "банк михайлівський",
    "фідобанк", "фидобанк", "євробанк", "евробанк", "бізнес-експерт",
    "бизнес-эксперт", "кредитка приватбанк", "михайловский", "михайлівський",
    "bilet.pb.ua", "оплата частями", "оплата частинами", "финансовый лицей",
    "фінансовий ліцей", "банк аркада", "банк хрещатик", "фан-бар", "автошкол",
    "автошкіл", "марфин банк", "марфін банк", "втб банк", "университет финансов",
    "університет фінансів", "фінансово-економічний університет",
    "финансово-экономический университет", "институт финансов",
    "кредитная карта \"универсальная\"", "продажа карт", "кріобанк", "криобанк",
    "банкет", "інтернет-магазин національного банку", "дитяча картка",
    "сайт для заработка", "moneycasino", "митний брокер", "автоброкер",
    "ivanka.invest", "ts polygraf",
]
GENERIC = {"платежные", "терминалы", "платіжні", "термінали", "онлайн", "украина",
           "україна", "сервис", "сервіс", "компания", "компанія", "тов", "пао", "пат",
           "net", "ua", "com", "org", "pro", "biz", "info", "in"}

def core_tokens(name):
    t = re.sub(r"[^a-zа-яёіїєґ0-9]+", " ", name.lower().replace(".", " "))
    return {w for w in t.split() if w not in GENERIC and len(w) > 2}

def main():
    src, tag = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 120
    rows = [json.loads(l) for l in open(src, encoding="utf-8")]
    rows = [r for r in rows if not r.get("is_dupe")]
    # drop cards already placed into other import files (previous batches)
    import glob, os
    def norm(t):
        t = re.sub(r"отзывы|відгуки|reviews?", "", t.lower())
        return " ".join(re.sub(r"[^a-zа-яёіїєґ0-9]+", " ", t).split())
    done_names = set()
    for f in glob.glob("/home/hatch/workspace/goals/goal/hidden_files/parser/import_*.txt"):
        if f"import_{tag}_" in os.path.basename(f):
            continue
        for line in open(f, encoding="utf-8"):
            if "|||" in line:
                done_names.add(norm(line.split("|||")[0]))
    rows = [r for r in rows if norm(r["name"]) not in done_names]
    rows = [r for r in rows if not any(d in r["name"].lower() for d in DENY)]
    # sub-brand dedupe: drop a card whose core tokens are a subset of a kept card's
    kept, cores = [], []
    for r in sorted(rows, key=lambda r: -(r.get("reviews") or 0)):
        ct = core_tokens(r["name"])
        if ct and any(ct <= c for c in cores):
            continue
        kept.append(r)
        cores.append(ct)
    rows = kept
    det = [r for r in rows if (r.get("rating") or 0) >= 4.8 and (r.get("reviews") or 0) >= 20]
    det_ids = {id(r) for r in det}
    rest = sorted([r for r in rows if id(r) not in det_ids], key=lambda r: -(r.get("views") or 0))
    det.sort(key=lambda r: -(r.get("reviews") or 0))
    sel = (det + rest)[:limit]
    base = "/home/hatch/workspace/goals/goal/hidden_files/parser/"
    report = [f"# Import batch {tag}: {len(sel)} cards (detector-A: {len([r for r in sel if id(r) in det_ids])})", ""]
    for bi in range(0, len(sel), 40):
        chunk = sel[bi:bi + 40]
        lines = []
        for r in chunk:
            lines.append(f"{r['name']} ||| {category(r['name'], r.get('description'))} ||| {clean_desc(r.get('description'))}")
            mark = " [ДЕТЕКТОР-A]" if id(r) in det_ids else ""
            report.append(f"- views {r.get('views')} | ★{r.get('rating')} | {r.get('reviews')} отз. | {r['name']}{mark}")
        open(base + f"import_{tag}_{bi // 40 + 1}.txt", "w", encoding="utf-8").write("\n".join(lines))
    open(base + f"import_{tag}_report.md", "w", encoding="utf-8").write("\n".join(report))
    print(f"{tag}: selected {len(sel)} cards in {(len(sel) + 39) // 40} file(s); detector-A {len(det)}")

if __name__ == "__main__":
    main()
