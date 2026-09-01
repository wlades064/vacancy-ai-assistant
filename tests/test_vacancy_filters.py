import unittest

from vacancy_filters import contains_excluded_keyword, contains_relevant_keyword, is_remote_text


class VacancyTitleFilterTests(unittest.TestCase):
    def test_requested_title_exclusions(self):
        excluded_titles = [
            "Системный аналитик (Аналитик ЦФТ)",
            "Специалист по аналитике и контролю качества",
            "Экономист-аналитик",
            "Аналитик Битрикс 24",
            "Аналитик Битрикс24",
            "Риск-аналитик",
            "Бизнес-аналитик со знанием китайского языка",
            "Системный аналитик в команду Smart CRM",
        ]

        for title in excluded_titles:
            with self.subTest(title=title):
                self.assertTrue(contains_excluded_keyword(title))

    def test_ai_titles_remain_relevant(self):
        titles = [
            "Специалист по ИИ",
            "AI Automation Specialist",
            "Инженер по внедрению LLM и AI-агентов",
        ]

        for title in titles:
            with self.subTest(title=title):
                self.assertTrue(contains_relevant_keyword(title))
                self.assertFalse(contains_excluded_keyword(title))


class RemoteFormatTests(unittest.TestCase):
    def test_remote_markers_from_search_card_and_vacancy_page(self):
        for text in ("Можно удалённо", "Удаленная работа", "Работа из дома"):
            with self.subTest(text=text):
                self.assertTrue(is_remote_text(text))

    def test_office_format_is_not_remote(self):
        self.assertFalse(is_remote_text("На месте работодателя"))


if __name__ == "__main__":
    unittest.main()
