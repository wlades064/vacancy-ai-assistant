import logging
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from vacancy_filters import contains_excluded_keyword, contains_relevant_keyword, is_remote_text


logger = logging.getLogger(__name__)
API_URL = "https://api.superjob.ru/2.0/vacancies/"


def parse_superjob_vacancy(item):
    if not isinstance(item, dict) or item.get("is_archive"):
        return None
    title = item.get("profession") or ""
    url = item.get("link") or ""
    if not title.strip() or not url.startswith("https://"):
        return None
    description = item.get("vacancyRichText") or "\n".join(
        item.get(field) or "" for field in ("work", "candidat", "compensation")
    )
    text = BeautifulSoup(description, "html.parser").get_text(" ", strip=True)
    try:
        published = datetime.fromtimestamp(int(item["date_published"]))
    except (KeyError, ValueError, TypeError, OverflowError, OSError):
        return None
    if not text:
        return None
    place = item.get("place_of_work") or {}
    return {
        "title": title.strip(), "url": url, "source": "SuperJob",
        "company_hint": item.get("firm_name") or (item.get("client") or {}).get("title", ""),
        "experience_hint": (item.get("experience") or {}).get("title", ""),
        "city_hint": (item.get("town") or {}).get("title", ""),
        "remote_hint": str(place.get("id")) == "2" or is_remote_text(place.get("title", "")),
        "published_at_hint": published.strftime("%d.%m.%Y"),
        "pub_date_hint": published,
        "vacancy_text_hint": text[:3000],
    }


def collect_superjob_vacancies(api_key, queries, ai_queries, pages=5, session=None, sleep=time.sleep):
    if not api_key:
        logger.warning("SuperJob пропущен: SUPERJOB_API_KEY не задан")
        return []
    # Pass the key only to the fixed API endpoint, never to shared session headers.
    http = session or requests
    collected = {}
    successful_pages = 0
    failed_pages = 0
    for query in queries:
        for page in range(pages):
            payload = None
            for attempt in range(3):
                try:
                    response = http.get(
                        API_URL,
                        headers={"X-Api-App-Id": api_key},
                        params={"keyword": query, "page": page, "count": 100,
                                "period": 7, "order_field": "date", "order_direction": "desc"},
                        timeout=(15, 30), allow_redirects=False,
                    )
                    if response.status_code in (401, 403):
                        logger.warning("SuperJob: доступ отклонён (HTTP %s), проверьте ключ", response.status_code)
                        return list(collected.values())
                    if response.status_code != 200:
                        raise ValueError("HTTP %s" % response.status_code)
                    payload = response.json()
                    if not isinstance(payload, dict) or not isinstance(payload.get("objects"), list):
                        raise ValueError("неизвестный формат ответа")
                    break
                except (requests.RequestException, ValueError):
                    payload = None
                    if attempt < 2:
                        sleep(5 * (2 ** attempt))
            if payload is None:
                failed_pages += 1
                logger.warning("SuperJob: не удалось загрузить запрос %r, страницу %s", query, page)
                break
            successful_pages += 1
            for item in payload["objects"]:
                try:
                    vacancy = parse_superjob_vacancy(item)
                except (AttributeError, TypeError, ValueError):
                    vacancy = None
                if not vacancy:
                    continue
                title = vacancy["title"]
                if not contains_relevant_keyword(title) or contains_excluded_keyword(title):
                    continue
                vacancy["matched_ai_query"] = query in ai_queries
                existing = collected.get(vacancy["url"])
                if existing:
                    existing["matched_ai_query"] |= vacancy["matched_ai_query"]
                else:
                    collected[vacancy["url"]] = vacancy
            sleep(1)
            if not payload.get("more") or not payload["objects"]:
                break
        else:
            logger.warning("SuperJob: достигнут лимит %s страниц для %r", pages, query)
    logger.info("SuperJob: страниц успешно %s, ошибок %s, собрано %s",
                successful_pages, failed_pages, len(collected))
    return list(collected.values())
