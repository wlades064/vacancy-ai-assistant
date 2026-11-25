import unittest
from decimal import Decimal

from vacancy_scoring import extract_score_and_verdict


class VacancyScoringTests(unittest.TestCase):
    def test_threshold_values_and_numbered_markdown(self):
        for value, expected in (("74,9", "74.9"), ("75", "75"), ("100", "100")):
            with self.subTest(value=value):
                reply = f"1. **ОБЩАЯ ОЦЕНКА СООТВЕТСТВИЯ:** {value}%\n**ВЕРДИКТ:** ДА"
                self.assertEqual(extract_score_and_verdict(reply), (Decimal(expected), "ДА"))

    def test_missing_invalid_and_failed_analysis(self):
        for reply in ("Навыки: 90%", "ОБЩАЯ ОЦЕНКА: 101%", "Ошибка анализа: ОБЩАЯ ОЦЕНКА: 90%"):
            with self.subTest(reply=reply):
                self.assertIsNone(extract_score_and_verdict(reply)[0])
