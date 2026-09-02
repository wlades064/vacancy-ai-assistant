import re
import unicodedata


EXCLUDE_KEYWORDS = [
    "senior", "сеньор", "lead", "лид", "руководитель",
    "главный", "ведущий", "principal", "head", "архитектор",
    "1с", "хранилищ", "недвижимост",
    "outbound", "crm", "первой линии", "второй линии",
    "аналитик данных", "hr-аналитик", "data analyst", "data", "портфельный",
    "финансовый аналитик", "продуктовый аналитик", "crypto", "крипто", "маркетинговый",
    "инвестиционный", "дизайн", "старший", "специалист 1-я линии поддержки", "спикер", "эдо",
    "маркетолог", "менеджер по продажам", "продажи",
    "младший менеджер проектов в стрим стратегической аналитики",
    "цфт", "специалист по аналитике и контролю качества", "экономист",
    "битрикс 24", "битрикс24", "риск", "китайск",
    "контент", "financial", "менеджер поддержки", "директолог",
    "специалист по личному бренду", "seo", "key account manager", "тувинск",
]

EXCLUDE_COMPANIES = ["aston", "астон"]

MOSCOW_OR_SAMARA_TIME_CITIES = [
    "астрахань", "брянск", "великий новгород", "владимир", "волгоград",
    "вологда", "воронеж", "иваново", "ижевск", "калуга", "казань",
    "киров", "кострома", "краснодар", "курск", "липецк", "москва",
    "мурманск", "набережные челны", "нижний новгород", "орел", "орёл",
    "пенза", "петрозаводск", "псков", "ростов-на-дону", "рязань",
    "самара", "санкт-петербург", "саранск", "саратов", "севастополь",
    "смоленск", "сочи", "ставрополь", "тамбов", "тверь", "тула",
    "ульяновск", "чебоксары", "череповец", "ярославль",
]

RELEVANT_KEYWORDS = [
    "аналитик", "analyst", "автоматизац", "automation", "ai-агент", "ии",
]

AI_KEYWORDS = [
    "ai-агент", "ai агент", "ai assistant", "ai specialist", "ai engineer",
    "aiops", "genai", "нейросет", "искусственн интеллект", "llm", "gpt",
    "n8n", "mcp", "rag", "machine learning",
]


def normalize_for_matching(text):
    """Приводит текст к единому виду для надёжного поиска ключевых слов."""
    normalized = unicodedata.normalize("NFKC", text or "").casefold().replace("ё", "е")
    normalized = re.sub(r"[‐‑‒–—−]", "-", normalized)
    return " ".join(normalized.split())


NORMALIZED_EXCLUDE_KEYWORDS = [
    normalize_for_matching(keyword) for keyword in EXCLUDE_KEYWORDS
]


def contains_excluded_keyword(title):
    normalized_title = normalize_for_matching(title)
    return any(keyword in normalized_title for keyword in NORMALIZED_EXCLUDE_KEYWORDS)


def contains_excluded_company(company):
    normalized_company = normalize_for_matching(company)
    return any(
        normalize_for_matching(keyword) in normalized_company
        for keyword in EXCLUDE_COMPANIES
    )


def is_excluded_experience(experience):
    normalized_experience = normalize_for_matching(experience)
    if normalized_experience in {"senior", "lead"}:
        return True
    three_to_six = re.search(
        r"(?:от\s*)?3(?:\s*[-]\s*6|\s*х?\s*до\s*6)\s*(?:лет|года)?",
        normalized_experience,
    )
    return bool(three_to_six) or "более 6" in normalized_experience or "6 лет" in normalized_experience


def preferred_city_rank(city):
    normalized_city = normalize_for_matching(city)
    if "саратов" in normalized_city:
        return 0
    if any(city_name in normalized_city for city_name in MOSCOW_OR_SAMARA_TIME_CITIES):
        return 1
    return 2


def deduplicate_company_titles(vacancies):
    best_index_by_key = {}

    for index, vacancy in enumerate(vacancies):
        title = normalize_for_matching(vacancy.get("title"))
        company = normalize_for_matching(vacancy.get("company"))
        has_company = company and company != "не указана"
        key = (title, company) if has_company else (title, vacancy.get("url", index))
        current_index = best_index_by_key.get(key)
        if current_index is None:
            best_index_by_key[key] = index
            continue
        if preferred_city_rank(vacancy.get("city")) < preferred_city_rank(
            vacancies[current_index].get("city")
        ):
            best_index_by_key[key] = index

    selected_indexes = set(best_index_by_key.values())
    return [vacancy for index, vacancy in enumerate(vacancies) if index in selected_indexes]


def contains_ai_keyword(title):
    normalized_title = normalize_for_matching(title)
    if any(keyword in normalized_title for keyword in AI_KEYWORDS):
        return True
    return bool(re.search(r"(?<![a-zа-я0-9])(?:ai|ml)(?![a-zа-я0-9])", normalized_title))


def contains_relevant_keyword(title):
    normalized_title = normalize_for_matching(title)
    return contains_ai_keyword(title) or any(
        normalize_for_matching(keyword) in normalized_title
        for keyword in RELEVANT_KEYWORDS
    )


def is_remote_text(text):
    normalized_text = normalize_for_matching(text)
    return "удален" in normalized_text or "работа из дома" in normalized_text
