"""Проверка активности компании по её сайту: жив ли, есть ли следы 2025–2026."""
import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

def check_site(url):
    if not url:
        return {"url": url, "verdict": "НЕТ САЙТА", "detail": "URL не указан"}
    if not url.startswith("http"):
        url = "https://" + url
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25, allow_redirects=True)
    except Exception as e:
        return {"url": url, "verdict": "МЁРТВА", "detail": f"Сайт не отвечает: {type(e).__name__}"}
    if r.status_code >= 400:
        return {"url": url, "verdict": "МЁРТВА", "detail": f"HTTP {r.status_code}"}
    text = re.sub(r"<[^>]+>", " ", r.text)
    fresh = []
    for y in ("2026", "2025"):
        if y in text:
            fresh.append(y)
    if fresh:
        return {"url": url, "verdict": "АКТИВНА", "detail": f"Сайт работает, на главной есть следы {', '.join(fresh)}"}
    return {"url": url, "verdict": "СОМНИТЕЛЬНО", "detail": "Сайт работает, но следов 2025–2026 на главной не видно"}
