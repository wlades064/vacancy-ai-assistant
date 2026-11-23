import json
import logging
import re
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from vacancy_filters import contains_excluded_keyword, contains_relevant_keyword, is_remote_text

BASE_URL = "https://raberu.ru"
CARD_PATH = re.compile(r"/(?:[a-z0-9-]+/)?vacancy/([0-9a-f-]{36})")
logger = logging.getLogger(__name__)


def parse_raberu_page(html, ai_query=False):
    soup = BeautifulSoup(html, "html.parser")
    script = soup.select_one("script#__NUXT_DATA__")
    if script is None:
        raise ValueError("нет данных выдачи Raberu")
    nodes = json.loads(script.get_text())
    if not isinstance(nodes, list):
        raise ValueError("неизвестный формат выдачи Raberu")

    def get(record, key):
        index = record.get(key) if isinstance(record, dict) else None
        return nodes[index] if type(index) is int and 0 <= index < len(nodes) else None

    links = {}
    for link in soup.select("a[href]"):
        path = link["href"].removeprefix(BASE_URL).split("?", 1)[0]
        match = CARD_PATH.fullmatch(path)
        if match:
            links[match[1]] = BASE_URL + path

    records = {}
    for node in nodes:
        vacancy_id = get(node, "id")
        if isinstance(vacancy_id, str) and vacancy_id in links and "publishedAt" in node:
            records[vacancy_id] = node
    if links and not records:
        raise ValueError("не удалось сопоставить ссылки и данные Raberu")

    vacancies = {}
    for vacancy_id, record in records.items():
        if get(record, "status") != "public" or get(record, "archivedAt"):
            continue
        title = get(record, "title")
        if not isinstance(title, str) or not contains_relevant_keyword(title) or contains_excluded_keyword(title):
            continue
        stamp = get(record, "publishedAt")
        experience = get(record, "experience")
        description = get(record, "description")
        if not all(isinstance(value, str) and value.strip() for value in (stamp, experience, description)):
            continue
        try:
            published = datetime.fromisoformat(stamp).astimezone().replace(tzinfo=None)
        except (ValueError, OverflowError, OSError):
            continue
        company = get(get(record, "company"), "title")
        city = get(get(record, "city"), "name")
        schedule = get(record, "schedule")
        vacancies[vacancy_id] = {
            "title": title.strip(), "url": links[vacancy_id], "source": "Raberu",
            "company_hint": company if isinstance(company, str) else "",
            "city_hint": city if isinstance(city, str) else "",
            "experience_hint": experience,
            "remote_hint": isinstance(schedule, str) and is_remote_text(schedule),
            "pub_date_hint": published, "published_at_hint": published.strftime("%d.%m.%Y"),
            "vacancy_text_hint": BeautifulSoup(description, "html.parser").get_text(" ", strip=True)[:3000],
            "matched_ai_query": ai_query,
        }
    return vacancies, set(links)


def collect_raberu_vacancies(queries, ai_queries, *, session=None, pages=2, sleep=time.sleep):
    http = session or requests
    results = {}
    cutoff = datetime.now() - timedelta(days=7)
    for query in queries:
        seen = set()
        for page in range(1, pages + 1):
            try:
                response = http.get(
                    BASE_URL + "/vacancies",
                    params={"search": query, "unset": "city", "page": page},
                    timeout=(8, 15),
                )
                response.raise_for_status()
                vacancies, links = parse_raberu_page(response.text, query in ai_queries)
            except (requests.RequestException, ValueError) as error:
                logger.warning("Raberu: сбор остановлен: %s", error)
                return list(results.values())
            if not links - seen:
                break
            seen.update(links)
            for vacancy_id, vacancy in vacancies.items():
                if vacancy["pub_date_hint"] >= cutoff and vacancy["vacancy_text_hint"]:
                    if vacancy_id in results:
                        results[vacancy_id]["matched_ai_query"] |= vacancy["matched_ai_query"]
                    else:
                        results[vacancy_id] = vacancy
            sleep(1)
    logger.info("Raberu: собрано %s вакансий", len(results))
    return list(results.values())
