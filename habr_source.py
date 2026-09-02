from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from vacancy_filters import is_remote_text


HABR_BASE_URL = "https://career.habr.com"


def _chip_values(card):
    values = {}
    for chip in card.select(".vacancy-meta .basic-chip"):
        icon = chip.find("use")
        text = chip.select_one(".chip-with-icon__text")
        if not icon or not text:
            continue
        icon_ref = icon.get("href") or icon.get("xlink:href") or ""
        values[icon_ref.rsplit("#", 1)[-1]] = text.get_text(" ", strip=True)
    return values


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        return None


def parse_habr_search_page(html):
    soup = BeautifulSoup(html, "html.parser")
    vacancies = []

    for card in soup.select(".vacancy-card"):
        title_link = card.select_one(".vacancy-card__title-link[href]")
        if not title_link:
            continue

        company = card.select_one(".vacancy-card__company a")
        published = card.select_one(".vacancy-card__date time")
        chips = _chip_values(card)
        work_format = chips.get("format", "")
        vacancies.append({
            "title": title_link.get_text(" ", strip=True),
            "url": urljoin(HABR_BASE_URL, title_link["href"]),
            "company_hint": company.get_text(" ", strip=True) if company else "",
            "experience_hint": chips.get("grade", ""),
            "city_hint": chips.get("placemark", ""),
            "remote_hint": is_remote_text(work_format),
            "published_at_hint": published.get_text(" ", strip=True) if published else "не указана",
            "pub_date_hint": _parse_datetime(published.get("datetime")) if published else None,
            "source": "Habr Career",
        })

    return vacancies


def parse_habr_vacancy_text(html):
    soup = BeautifulSoup(html, "html.parser")
    description = soup.select_one(".vacancy-description__text")
    return description.get_text(" ", strip=True) if description else ""
