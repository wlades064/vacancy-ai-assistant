import re
from decimal import Decimal


def extract_score_and_verdict(analysis_text):
    if analysis_text.startswith("Ошибка анализа:"):
        return None, ""
    score = None
    verdict = ""
    for line in analysis_text.splitlines():
        line = line.replace("*", "").strip()
        match = re.search(r"\bобщая оценка(?:\s+соответствия)?\s*[:—–-]?\s*(\d{1,3}(?:[.,]\d+)?)\s*%", line, re.I)
        if match:
            value = Decimal(match[1].replace(",", "."))
            if 0 <= value <= 100:
                score = value
        match = re.search(r"\bвердикт\s*[:—–-]?\s*(да|нет)\b", line, re.I)
        if match:
            verdict = match[1].upper()
    return score, verdict
