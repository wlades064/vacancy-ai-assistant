import re

from bs4 import BeautifulSoup

from vacancy_filters import is_excluded_experience, is_remote_text, normalize_for_matching


def normalize_hh_experience(text):
    text = normalize_for_matching(text)
    if re.search(r"без\s*опыта|не\s*требуется", text):
        return "без опыта"
    match = re.search(r"(?:от\s*)?([136])\s*(?:-|до)\s*([36])\s*(?:лет|года|год)", text)
    if match and (match[1], match[2]) in {("1", "3"), ("3", "6")}:
        return f"{match[1]}-{match[2]} лет"
    if re.search(r"(?:более|от)\s*6\s*лет|6\s*\+\s*лет", text):
        return "более 6 лет"
    return ""


def parse_hh_details(html):
    soup = BeautifulSoup(html, "html.parser")
    company_node = soup.select_one('[data-qa="vacancy-company-name"], [data-qa="vacancy-company-name-wrapper"]')
    company = company_node.get_text(" ", strip=True) if company_node else ""
    if not company:
        company_node = soup.select_one('[data-qa="vacancy-company"] a[href*="/employer/"]')
        company = company_node.get_text(" ", strip=True) if company_node else ""
    experiences = []
    for node in soup.select('[data-qa="vacancy-experience"], [data-qa="work-experience-text"]'):
        experiences.append(normalize_hh_experience(node.get_text(" ", strip=True)))
    # Only labelled experience fields, never arbitrary numbers in the description.
    for node in soup.find_all(string=re.compile(r"Опыт\s+работы", re.I)):
        parent = node.parent
        if parent.name in {"script", "style"}:
            continue
        text = parent.get_text(" ", strip=True)
        if len(text) < 150:
            experiences.append(normalize_hh_experience(text))
        if not normalize_hh_experience(text) and parent.parent:
            text = parent.parent.get_text(" ", strip=True)
            if len(text) < 150:
                experiences.append(normalize_hh_experience(text))
    experience = next((value for value in experiences if value and is_excluded_experience(value)), "")
    experience = experience or next((value for value in experiences if value), "")
    address = soup.select_one('[data-qa="vacancy-address-with-map"], [data-qa="vacancy-view-raw-address"]')
    city = address.get_text(" ", strip=True).lower() if address else ""
    work_format = soup.select_one('[data-qa="work-formats-text"]')
    remote = bool(work_format and is_remote_text(work_format.get_text(" ", strip=True)))
    return company, experience, city, remote, bool(company and experience)
