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
