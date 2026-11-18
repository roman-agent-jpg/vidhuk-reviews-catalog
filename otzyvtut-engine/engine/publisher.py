"""Публикатор: управление otzyvtut.com через админку WordPress.
Использует служебный плагин «Bulk Review Moderation (Otzyvtut)»:
импорт карточек строками, публикация по списку ID, добавление обзоров
в карточки через классический редактор. Доступы берутся из настроек
программы и хранятся только локально."""
import html as htmllib
import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PLUGIN_PAGE = "/wp-admin/admin.php?page=bulk-review-moderation"

class WP:
    def __init__(self, base, user, password):
        self.base = base.rstrip("/")
        self.user = user
        self.password = password
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA})
        self._logged = False

    def login(self):
        if self._logged:
            return
        r = self.s.post(self.base + "/wp-login.php", data={
            "log": self.user, "pwd": self.password,
            "wp-submit": "Войти", "redirect_to": self.base + "/wp-admin/",
            "testcookie": "1",
        }, timeout=60)
        if "wp-admin" not in r.url and "wordpress_logged_in" not in str(self.s.cookies.get_dict()):
            raise RuntimeError("Не удалось войти в админку: проверь логин и пароль в настройках.")
        self._logged = True

    def _nonce(self, page_html, action_hint=""):
        m = re.search(r'name="_wpnonce" value="([a-z0-9]+)"', page_html)
        return m.group(1) if m else None

    def _plugin_page(self):
        self.login()
        r = self.s.get(self.base + PLUGIN_PAGE, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Страница плагина недоступна: {r.status_code}")
        return r.text

    def import_cards(self, lines, publish=False):
        """lines: строки «Название ||| term_id ||| Описание» (до 40).
        Возвращает список созданных ID."""
        page = self._plugin_page()
        # nonce именно формы импорта: ищем форму с brm_import_lines
        forms = re.findall(r'<form method="post">(.*?)</form>', page, re.S)
        nonce = None
        for f in forms:
            if "brm_import_lines" in f:
                m = re.search(r'name="_wpnonce" value="([a-z0-9]+)"', f)
                if m:
                    nonce = m.group(1)
        if not nonce:
            raise RuntimeError("Не нашёл форму импорта плагина (плагин активен?)")
        data = {"_wpnonce": nonce, "_wp_http_referer": PLUGIN_PAGE,
                "brm_import_lines": "\n".join(lines)}
        if publish:
            data["brm_import_publish"] = "1"
        r = self.s.post(self.base + PLUGIN_PAGE, data=data, timeout=120)
        ids = [int(x) for x in re.findall(r"Создано ID (\d+)", r.text)]
        if not ids and "создано 0" not in r.text:
            snippet = re.sub(r"<[^>]+>", " ", r.text)
            snippet = re.sub(r"\s+", " ", snippet)[:300]
            raise RuntimeError(f"Импорт не дал созданных ID. Ответ сайта: {snippet}")
        return ids

    def publish_posts(self, ids):
        page = self._plugin_page()
        forms = re.findall(r'<form method="post">(.*?)</form>', page, re.S)
        nonce = None
        for f in forms:
            if "brm_post_ids" in f:
                m = re.search(r'name="_wpnonce" value="([a-z0-9]+)"', f)
                if m:
                    nonce = m.group(1)
        if not nonce:
            raise RuntimeError("Не нашёл форму действий по карточкам в плагине")
        r = self.s.post(self.base + PLUGIN_PAGE, data={
            "_wpnonce": nonce, "_wp_http_referer": PLUGIN_PAGE,
            "brm_post_ids": ", ".join(str(i) for i in ids),
            "brm_post_action": "publish",
        }, timeout=120)
        m = re.search(r"Компаний обработано \(publish\): (\d+)", r.text)
        return int(m.group(1)) if m else 0

    def append_overview(self, post_id, overview_text):
        """Добавить блок «Обзор редакции OtzyvTut» в конец описания карточки
        через классический редактор. Возвращает True при успехе."""
        self.login()
        edit_url = f"{self.base}/wp-admin/post.php?post={post_id}&action=edit"
        r = self.s.get(edit_url, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Страница редактирования {post_id} недоступна: {r.status_code}")
        page = r.text
        m_nonce = re.search(r'name="_wpnonce" value="([a-z0-9]+)"', page)
        m_content = re.search(r'<textarea[^>]*id="content"[^>]*>(.*?)</textarea>', page, re.S)
        if not m_nonce or not m_content:
            raise RuntimeError("Не нашёл поле контента (редактор не классический?)")
        content = htmllib.unescape(m_content.group(1))
        if "Обзор редакции OtzyvTut" in content:
            return False  # уже есть
        paras = [p.strip() for p in overview_text.split("\n") if p.strip()]
        block = "\n<h2>Обзор редакции OtzyvTut</h2>\n" + "\n".join(f"<p>{htmllib.escape(p)}</p>" for p in paras)
        new_content = content.rstrip() + "\n" + block + "\n"
        m_post = re.search(r'name="post_ID" value="(\d+)"', page)
        data = {
            "_wpnonce": m_nonce.group(1),
            "_wp_http_referer": f"/wp-admin/post.php?post={post_id}&action=edit",
            "post_ID": m_post.group(1) if m_post else str(post_id),
            "action": "editpost",
            "content": new_content,
            "save": "Обновить",
        }
        # заголовок обязателен для editpost — подхватываем из формы
        m_title = re.search(r'id="title"[^>]*value="([^"]*)"', page)
        if m_title:
            data["post_title"] = htmllib.unescape(m_title.group(1))
        r2 = self.s.post(self.base + "/wp-admin/post.php", data=data, timeout=120)
        if r2.status_code not in (200, 302):
            raise RuntimeError(f"Сохранение карточки {post_id} не удалось: {r2.status_code}")
        check = self.s.get(edit_url, timeout=60)
        return "Обзор редакции OtzyvTut" in check.text

def export_lines(items):
    """Строки импорта из очереди (для ручной вставки или публикатора)."""
    out = []
    for it in items:
        desc = (it.get("description") or "").replace("\n", " ")
        out.append(f"{it['name']} ||| {it.get('term_id', 18)} ||| {desc}")
    return out
