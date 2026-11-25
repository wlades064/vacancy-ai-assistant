import re
import hashlib
import json
from urllib.parse import urlsplit

from vacancy_filters import normalize_for_matching


def hh_vacancy_id(url):
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not (host == "hh.ru" or host.endswith(".hh.ru")):
        return None
    match = re.fullmatch(r"/vacancy/([0-9]+)/?", parsed.path)
    return match[1] if match else None


def vacancy_history_key(url):
    # Keep numeric hh.ru keys compatible with the existing history sheet.
    hh_id = hh_vacancy_id(url)
    if hh_id:
        return hh_id
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    path = parsed.path.rstrip("/")
    for domain, pattern in (
        ("career.habr.com", r"/vacancies/([0-9]+)"),
        ("superjob.ru", r"/vakansii/(?:[^/]*-)?([0-9]+)\.html"),
        ("arbihunter.com", r"/[a-z]{2}/jobs/(?:[^/]*-)?([0-9]+)"),
        ("raberu.ru", r"/(?:[^/]+/)?vacancy/([0-9a-f-]{36})"),
    ):
        if host in {domain, "www." + domain}:
            match = re.fullmatch(pattern, path, re.IGNORECASE)
            return f"{domain}:{(match[1] if match else path).lower()}"
    return None


def vacancy_history_keys(url, title="", company=""):
    keys = set()
    if key := vacancy_history_key(url):
        keys.add(key)
    title = normalize_for_matching(title)
    company = normalize_for_matching(company)
    if title and company not in {"", "не указана", "nda", "не указан"}:
        pair = json.dumps([company, title], ensure_ascii=False).encode("utf-8")
        keys.add("company-title:" + hashlib.sha256(pair).hexdigest())
    return keys


def exclude_seen_vacancies(vacancies, shown_ids):
    seen_ids = set()
    selected = []
    for vacancy in vacancies:
        url = vacancy["url"]
        keys = vacancy_history_keys(url, vacancy.get("title"), vacancy.get("company"))
        vacancy_id = vacancy_history_key(url)
        if keys & shown_ids or (vacancy_id and vacancy_id in seen_ids):
            continue
        if vacancy_id:
            seen_ids.add(vacancy_id)
        selected.append(vacancy)
    return selected
