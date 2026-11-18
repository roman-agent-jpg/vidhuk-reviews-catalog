#!/usr/bin/env python3
"""OtzyvTut Engine — панель управления сайтом отзывов otzyvtut.com.

Запуск:  python app.py   →   открыть http://127.0.0.1:8790
Модули: парсер фактов с сайтов-доноров, генератор редакционных текстов
(Google Gemini, ключ пользователя), публикатор в WordPress, проверка
активности компаний, журнал действий. Всё хранится локально в data/.
"""
import json, os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from engine import store, parser as parser_mod, gemini as gemini_mod, publisher as pub_mod, activity as act_mod, reviews as reviews_mod
from engine.categories import NICHES, CATS

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = 8790

def run_job(jid, fn):
    def _wrap():
        try:
            result = fn(lambda msg: store.job_update(jid, progress=msg))
            store.job_update(jid, state="done", result=result)
        except Exception as e:
            store.job_update(jid, state="error", error=str(e))
    threading.Thread(target=_wrap, daemon=True).start()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = open(os.path.join(BASE, "ui.html"), encoding="utf-8").read()
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/state":
            s = store.get_settings()
            q = store.get_queue()
            self._json({
                "settings": {
                    "gemini_ready": bool(s["gemini_key"]),
                    "wp_ready": bool(s["wp_user"] and s["wp_password"]),
                    "wp_url": s["wp_url"],
                    "gemini_model": s["gemini_model"],
                },
                "queue": q,
                "review_sets": [{**s, "items": s["items"][:300]} for s in store.get_review_sets()],
                "log": store.get_log()[:30],
                "jobs": list(store.JOBS.values()),
                "niches": {k: v["label"] for k, v in NICHES.items()},
                "cats": CATS,
            })
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        b = self._body()
        try:
            if self.path == "/api/settings":
                store.save_settings(b)
                store.log("Настройки сохранены")
                self._json({"ok": True})
            elif self.path == "/api/parse":
                niche = b.get("niche", "finance")
                limit = max(1, min(60, int(b.get("limit", 20))))
                jid = store.job_start("parse")
                def job(progress):
                    cards = parser_mod.parse_niche(niche, limit, progress)
                    added = store.add_items(cards)
                    store.log("Парсер", f"Ниша {niche}: собрано {len(cards)}, новых в очереди {added}")
                    return f"Собрано карточек: {len(cards)}, добавлено новых: {added}"
                run_job(jid, job)
                self._json({"job": jid})
            elif self.path == "/api/generate":
                s = store.get_settings()
                if not s["gemini_key"]:
                    return self._json({"error": "Сначала укажи API-ключ Gemini в настройках"}, 400)
                ids = set(b.get("ids") or [])
                kind = b.get("kind", "overview")
                q = store.get_queue()
                targets = [i for i in q if (not ids or i["id"] in ids) and i["status"] in ("parsed", "text_ready")]
                if not targets:
                    return self._json({"error": "Нет карточек для генерации"}, 400)
                jid = store.job_start("generate")
                def job(progress):
                    done = 0
                    for it in targets:
                        progress(f"Пишу текст: {it['name']} ({done + 1}/{len(targets)})")
                        if kind == "overview":
                            text = gemini_mod.make_overview(s["gemini_key"], s["gemini_model"], it)
                            store.update_item(it["id"], overview=text, status="text_ready")
                        else:
                            text = gemini_mod.make_description(s["gemini_key"], s["gemini_model"], it)
                            store.update_item(it["id"], description=text, status="text_ready")
                        done += 1
                    store.log("Генератор", f"{kind}: готово {done}")
                    return f"Текстов готово: {done}"
                run_job(jid, job)
                self._json({"job": jid})
            elif self.path == "/api/publish":
                s = store.get_settings()
                if not (s["wp_user"] and s["wp_password"]):
                    return self._json({"error": "Сначала укажи логин и пароль админки в настройках"}, 400)
                ids = set(b.get("ids") or [])
                publish_now = bool(b.get("publish"))
                q = store.get_queue()
                targets = [i for i in q if (not ids or i["id"] in ids) and i["status"] in ("parsed", "text_ready")]
                if not targets:
                    return self._json({"error": "Нет карточек для публикации"}, 400)
                jid = store.job_start("publish")
                def job(progress):
                    wp = pub_mod.WP(s["wp_url"], s["wp_user"], s["wp_password"])
                    total_ids = []
                    for k in range(0, len(targets), 40):
                        batch = targets[k:k + 40]
                        progress(f"Импортирую пачку {k // 40 + 1}: {len(batch)} карточек")
                        lines = pub_mod.export_lines(batch)
                        created = wp.import_cards(lines, publish=publish_now)
                        for it, wid in zip(batch, created):
                            store.update_item(it["id"], wp_id=wid,
                                              status="published" if publish_now else "queued")
                        total_ids += created
                    store.log("Публикатор", f"Создано карточек: {len(total_ids)}, опубликовано сразу: {publish_now}")
                    return f"Создано карточек на сайте: {len(total_ids)}"
                run_job(jid, job)
                self._json({"job": jid})
            elif self.path == "/api/publish_ids":
                s = store.get_settings()
                ids = set(b.get("ids") or [])
                q = store.get_queue()
                targets = [i for i in q if i["id"] in ids and i.get("wp_id")]
                if not targets:
                    return self._json({"error": "У выбранных карточек нет ID на сайте"}, 400)
                jid = store.job_start("publish_ids")
                def job(progress):
                    wp = pub_mod.WP(s["wp_url"], s["wp_user"], s["wp_password"])
                    n = wp.publish_posts([i["wp_id"] for i in targets])
                    for i in targets:
                        store.update_item(i["id"], status="published")
                    store.log("Публикатор", f"Опубликовано по списку: {n}")
                    return f"Опубликовано карточек: {n}"
                run_job(jid, job)
                self._json({"job": jid})
            elif self.path == "/api/append_overview":
                s = store.get_settings()
                item_id = b.get("id")
                wp_id = int(b.get("wp_id") or 0)
                q = {i["id"]: i for i in store.get_queue()}
                it = q.get(item_id)
                if not it or not it.get("overview"):
                    return self._json({"error": "Сначала сгенерируй обзор для карточки"}, 400)
                if not wp_id:
                    return self._json({"error": "Укажи ID карточки на сайте"}, 400)
                jid = store.job_start("append")
                def job(progress):
                    wp = pub_mod.WP(s["wp_url"], s["wp_user"], s["wp_password"])
                    ok = wp.append_overview(wp_id, it["overview"])
                    store.log("Публикатор", f"Обзор в карточку {wp_id}: {'добавлен' if ok else 'уже был'}")
                    return "Обзор добавлен в карточку" if ok else "Обзор уже есть в этой карточке"
                run_job(jid, job)
                self._json({"job": jid})
            elif self.path == "/api/export":
                ids = set(b.get("ids") or [])
                q = store.get_queue()
                targets = [i for i in q if not ids or i["id"] in ids]
                lines = pub_mod.export_lines(targets)
                os.makedirs(os.path.join(BASE, "data", "exports"), exist_ok=True)
                path = os.path.join(BASE, "data", "exports", "import_export.txt")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                store.log("Экспорт", f"Строк в файле: {len(lines)}")
                self._json({"ok": True, "count": len(lines), "content": "\n".join(lines)})
            elif self.path == "/api/reviews_collect":
                query = (b.get("query") or "").strip()
                if not query:
                    return self._json({"error": "Укажи название компании или ссылку на её карточку"}, 400)
                pages = max(1, min(15, int(b.get("pages", 5))))
                jid = store.job_start("reviews")
                def job(progress):
                    rset = reviews_mod.collect(query, pages, progress)
                    sid = store.add_review_set(rset)
                    store.log("Отзывы из сети", f"{query}: собрано {len(rset['items'])} с {', '.join(rset['sources']) or '—'}")
                    return f"Собрано отзывов: {len(rset['items'])} (набор {sid})"
                run_job(jid, job)
                self._json({"job": jid})
            elif self.path == "/api/reviews_summary":
                s = store.get_settings()
                if not s["gemini_key"]:
                    return self._json({"error": "Сначала укажи API-ключ Gemini в настройках"}, 400)
                set_id = b.get("set_id")
                sets = {x["id"]: x for x in store.get_review_sets()}
                rset = sets.get(set_id)
                if not rset:
                    return self._json({"error": "Набор не найден"}, 400)
                jid = store.job_start("reviews_summary")
                def job(progress):
                    neg = [i for i in rset["items"] if i.get("rating") and i["rating"] <= 3][:40]
                    sample = "\n---\n".join((i.get("text") or "")[:400] for i in neg)
                    prompt = (
                        f"Компания: {rset['query']}. Ниже — негативные и средние отзывы о ней из открытых источников. "
                        f"Сделай сводку ДЛЯ ВЛАДЕЛЬЦА ПЛОЩАДКИ ОТЗЫВОВ: 1) главные темы жалоб по пунктам с примерной частотой; "
                        f"2) что хвалят (если встречается); 3) признаки заказной активности (всплески, одинаковые формулировки), если видны; "
                        f"4) один абзац — как это выглядит со стороны для потенциальных клиентов компании. Только факты из текстов.\n\n{sample}"
                    )
                    text = gemini_mod._call(s["gemini_key"], s["gemini_model"], prompt)
                    store.update_review_set(set_id, gemini_summary=text)
                    store.log("Отзывы из сети", f"Gemini-сводка по «{rset['query']}» готова")
                    return "Сводка готова"
                run_job(jid, job)
                self._json({"job": jid})
            elif self.path == "/api/remove":
                store.remove_items(b.get("ids") or [])
                store.log("Очередь", "Удалены выбранные карточки")
                self._json({"ok": True})
            elif self.path == "/api/activity":
                urls = [u.strip() for u in (b.get("urls") or "").split("\n") if u.strip()]
                results = [act_mod.check_site(u) for u in urls[:30]]
                store.log("Активность", f"Проверено сайтов: {len(results)}")
                self._json({"results": results})
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

if __name__ == "__main__":
    print(f"OtzyvTut Engine: открой http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
