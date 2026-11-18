"""Хранилище OtzyvTut Engine: настройки, очередь карточек, журнал действий.
Всё лежит локально в папке data/ рядом с программой. Никаких внешних баз."""
import json, os, threading, time, uuid

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
os.makedirs(DATA, exist_ok=True)

_lock = threading.Lock()

def _path(name):
    return os.path.join(DATA, name)

def _load(name, default):
    p = _path(name)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def _save(name, obj):
    with open(_path(name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)

# ---------- настройки ----------
def get_settings():
    s = _load("settings.json", {})
    return {
        "gemini_key": s.get("gemini_key", ""),
        "gemini_model": s.get("gemini_model", "gemini-2.5-flash"),
        "wp_url": s.get("wp_url", "https://otzyvtut.com"),
        "wp_user": s.get("wp_user", ""),
        "wp_password": s.get("wp_password", ""),
    }

def save_settings(new):
    s = get_settings()
    s.update({k: v for k, v in new.items() if v is not None})
    _save("settings.json", s)
    return s

# ---------- очередь ----------
def get_queue():
    return _load("queue.json", [])

def save_queue(q):
    _save("queue.json", q)

def add_items(items):
    """items: список словарей карточек. Дедуп по нормализованному названию."""
    def norm(n):
        return " ".join((n or "").lower().replace("«", "").replace("»", "").split())
    with _lock:
        q = get_queue()
        known = {norm(i["name"]) for i in q}
        added = 0
        for it in items:
            if norm(it["name"]) in known:
                continue
            it.setdefault("id", uuid.uuid4().hex[:10])
            it.setdefault("status", "parsed")
            it.setdefault("overview", "")
            it.setdefault("wp_id", None)
            it.setdefault("note", "")
            q.append(it)
            known.add(norm(it["name"]))
            added += 1
        save_queue(q)
        return added

def update_item(item_id, **fields):
    with _lock:
        q = get_queue()
        for it in q:
            if it["id"] == item_id:
                it.update(fields)
        save_queue(q)

def remove_items(ids):
    with _lock:
        q = [i for i in get_queue() if i["id"] not in set(ids)]
        save_queue(q)

# ---------- журнал ----------
def log(action, detail=""):
    with _lock:
        entries = _load("log.json", [])
        entries.insert(0, {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "action": action, "detail": detail})
        _save("log.json", entries[:200])

def get_log():
    return _load("log.json", [])

# ---------- собранные отзывы из сети ----------
def get_review_sets():
    return _load("reviews.json", [])

def add_review_set(rset):
    with _lock:
        sets = get_review_sets()
        rset.setdefault("id", uuid.uuid4().hex[:10])
        rset.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S"))
        rset.setdefault("gemini_summary", "")
        sets.insert(0, rset)
        _save("reviews.json", sets[:20])
        return rset["id"]

def update_review_set(set_id, **fields):
    with _lock:
        sets = get_review_sets()
        for s in sets:
            if s["id"] == set_id:
                s.update(fields)
        _save("reviews.json", sets)

# ---------- фоновые задания ----------
JOBS = {}

def job_start(kind):
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {"id": jid, "kind": kind, "state": "running", "progress": "", "result": None, "error": ""}
    return jid

def job_update(jid, progress=None, state=None, result=None, error=None):
    j = JOBS.get(jid)
    if not j:
        return
    if progress is not None:
        j["progress"] = progress
    if state is not None:
        j["state"] = state
    if result is not None:
        j["result"] = result
    if error is not None:
        j["error"] = error
