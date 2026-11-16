import re
from urllib.parse import urlsplit


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


def exclude_seen_hh(vacancies, shown_ids):
    seen = set(shown_ids)
    selected = []
    for vacancy in vacancies:
        vacancy_id = hh_vacancy_id(vacancy["url"])
        if vacancy_id is not None:
            if vacancy_id in seen:
                continue
            seen.add(vacancy_id)
        selected.append(vacancy)
    return selected
