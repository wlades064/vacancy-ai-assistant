import json
import logging
import re
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from vacancy_filters import (
    contains_ai_keyword, contains_excluded_keyword, contains_relevant_keyword,
)

logger = logging.getLogger(__name__)
BASE_URL = "https://arbihunter.com"


def parse_arbihunter_search(html):
    soup = BeautifulSoup(html, "html.parser")
    decoder = json.JSONDecoder()
    chunks = []
    for script in soup.find_all("script"):
        text = script.get_text().strip()
        prefix = "self.__next_f.push("
        if not text.startswith(prefix):
            continue
        try:
            chunk = decoder.raw_decode(text[len(prefix):])[0]
            if isinstance(chunk, list) and len(chunk) > 1 and isinstance(chunk[1], str):
                chunks.append(chunk[1])
        except ValueError:
            continue
    flight = "".join(chunks)
    metadata = {}
    for match in re.finditer(r'"vacancy"\s*:\s*', flight):
        try:
            value = decoder.raw_decode(flight[match.end():])[0]
            if isinstance(value, dict) and isinstance(value.get("slug"), str):
                metadata[value["slug"]] = value
        except ValueError:
            continue

    results = []
    cards = soup.select('a[data-track-type="vacancy-track"]')
    for card in cards:
        href = card.get("href", "")
        if not re.fullmatch(r"/ru/jobs/[a-zA-Z0-9_-]+", href):
            continue
        data = metadata.get(href.rsplit("/", 1)[-1], {})
        title = card.find("h2")
        if not title or data.get("status") != "PUBLISHED":
            continue
        try:
            stamp = (data.get("order") or {}).get("publishedAt")
            published = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
        except (TypeError, ValueError, AttributeError):
            continue
        tags = card.select_one('[class*="__TagInfoContainer"]')
        tag_text = tags.get_text(" ", strip=True) if tags else ""
        experience = re.search(r"(?:\d+\s*[-–]\s*\d+\s*(?:года|лет)|6\+\s*лет|Без опыта)", tag_text, re.I)
        experience_text = experience.group() if experience else ""
        if "6+" in experience_text:
            experience_text = "более 6 лет"
        if re.search(r"\b(?:Senior|Lead|Teamlead|Head)\b", tag_text, re.I):
            experience_text = "Senior"
        company = data.get("company") or {}
        results.append({
            "title": title.get_text(" ", strip=True), "url": BASE_URL + href,
            "source": "ArbiHunter",
            "company_hint": "" if company.get("isNDA") else company.get("title", ""),
            "experience_hint": experience_text,
            "city_hint": (data.get("city") or {}).get("name", ""),
            "remote_hint": data.get("format") == "REMOTE",
            "pub_date_hint": published, "published_at_hint": published.strftime("%d.%m.%Y"),
        })
    total = re.search(r'"totalPages"\s*:\s*(\d+)', flight)
    if cards and not results:
        raise ValueError("разметка карточек или даты ArbiHunter не распознаны")
    if not cards and not total:
        raise ValueError("страница выдачи ArbiHunter не распознана")
    return results, int(total.group(1)) if total else None


def parse_arbihunter_description(html):
    soup = BeautifulSoup(html, "html.parser")
    description = soup.select_one('[class*="EditorWrapper"][class*="__Html"]')
    return description.get_text(" ", strip=True)[:3000] if description else ""


def collect_arbihunter_vacancies(session=None, sleep=time.sleep, now=None, max_pages=30):
    http = session or requests
    cutoff = (now or datetime.now()) - timedelta(days=7)
    results = []
    seen = set()
    pages_ok = 0
    failures = 0
    for page in range(max_pages):
        try:
            response = http.get(BASE_URL + "/ru/jobs", params={"page": page}, timeout=(15, 30), allow_redirects=False)
            if response.status_code != 200:
                logger.warning("ArbiHunter: HTTP %s, сбор остановлен", response.status_code)
                break
            vacancies, total_pages = parse_arbihunter_search(response.text)
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            logger.warning("ArbiHunter: ошибка страницы %s, сбор остановлен", page)
            break
        pages_ok += 1
        new_urls = {v["url"] for v in vacancies} - seen
        if vacancies and not new_urls:
            logger.warning("ArbiHunter: выдача повторяется, сбор остановлен")
            break
        for vacancy in vacancies:
            if vacancy["url"] in seen:
                continue
            seen.add(vacancy["url"])
            title = vacancy["title"]
            if (vacancy["pub_date_hint"] < cutoff or not contains_relevant_keyword(title)
                    or contains_excluded_keyword(title)):
                continue
            try:
                sleep(1)
                detail = http.get(vacancy["url"], timeout=(15, 30), allow_redirects=False)
                if detail.status_code in (401, 403, 429):
                    logger.warning("ArbiHunter: HTTP %s на карточке, сбор остановлен", detail.status_code)
                    return results
                detail.raise_for_status()
                text = parse_arbihunter_description(detail.text)
                if not text:
                    raise ValueError("описание отсутствует")
            except (requests.RequestException, ValueError):
                failures += 1
                continue
            vacancy["vacancy_text_hint"] = text
            vacancy["matched_ai_query"] = contains_ai_keyword(title)
            results.append(vacancy)
        if total_pages is not None and page + 1 >= total_pages:
            break
        sleep(1)
    else:
        logger.warning("ArbiHunter: достигнут лимит %s страниц", max_pages)
    logger.info("ArbiHunter: страниц %s, просмотрено %s, ошибок карточек %s, собрано %s",
                pages_ok, len(seen), failures, len(results))
    return results
