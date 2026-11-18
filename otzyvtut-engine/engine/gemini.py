"""Генератор редакционных текстов через Google Gemini (ключ пользователя).
Принцип: тексты пишутся ОТ ИМЕНИ РЕДАКЦИИ на основе фактов (данные карточки,
статистика, темы жалоб из открытых данных). Выдуманные отзывы и авторы не генерируются."""
import requests

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM = (
    "Ты — редактор сайта отзывов OtzyvTut. Пишешь нейтральные редакционные тексты о компаниях "
    "ТОЛЬКО на основе переданных фактов. Запрещено: выдумывать факты, цифры, имена, отзывы и их авторов; "
    "обвинять компанию от имени редакции (претензии передавай как «по словам авторов отзывов»); "
    "копировать чужие тексты. Пиши по-русски, живым деловым языком, без воды и рекламы."
)

def _call(api_key, model, prompt):
    r = requests.post(API.format(model=model), params={"key": api_key}, timeout=120, json={
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.6, "maxOutputTokens": 1200},
    })
    if r.status_code != 200:
        raise RuntimeError(f"Gemini вернул {r.status_code}: {r.text[:300]}")
    data = r.json()
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts).strip()

def make_description(api_key, model, card):
    prompt = (
        f"Составь фактическое описание компании для каталога отзывов (2 абзаца, до 700 знаков).\n"
        f"Название: {card.get('name')}\n"
        f"Известные факты: {card.get('description') or 'только название и сфера из названия'}\n"
        f"Рейтинг на внешней площадке: {card.get('rating')}, отзывов там: {card.get('reviews')}.\n"
        f"Пиши только о том, чем компания занимается и что о ней известно из фактов выше."
    )
    return _call(api_key, model, prompt)

def make_overview(api_key, model, card, site_stats=None):
    stats = ""
    if site_stats:
        stats = (f"\nСтатистика на OtzyvTut: отзывов с оценками: {site_stats.get('rated')}, "
                 f"средний рейтинг: {site_stats.get('avg')}, просмотров карточки: {site_stats.get('views')}.")
    prompt = (
        f"Напиши редакционный обзор компании для её карточки на OtzyvTut (4 абзаца, 900–1300 знаков).\n"
        f"Структура: 1) чем занимается компания; 2) что видно по отзывам и оценкам (поляризация, главные темы жалоб и похвалы — только если они даны в фактах); "
        f"3) что проверить клиенту перед обращением; 4) приглашение оставить отзыв и строка для представителей компании про официальные ответы и страницу https://otzyvtut.com/removing-reviews/.\n"
        f"Название: {card.get('name')}\n"
        f"Факты о компании: {card.get('description') or '—'}\n"
        f"Внешние данные: рейтинг {card.get('rating')}, отзывов {card.get('reviews')}, просмотров у донора {card.get('views')}.{stats}"
    )
    return _call(api_key, model, prompt)
