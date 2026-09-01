import unittest

from vacancy_filters import (
    contains_excluded_company,
    contains_excluded_keyword,
    contains_relevant_keyword,
    deduplicate_company_titles,
    is_excluded_experience,
    is_remote_text,
)


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

    def test_additional_title_exclusions(self):
        excluded_titles = [
            "Контент-менеджер для обучения нейросетей",
            "Business Analyst (Financial Analytics)",
            "Менеджер поддержки / байер в ИИ-стартап",
            "Специалист по контекстной рекламе / Директолог",
            "Специалист по личному бренду",
            "SEO-специалист (AI)",
            "Key Account Manager (AI-платформа)",
            "Разметчик данных для AI / LLM (тувинский язык)",
        ]

        for title in excluded_titles:
            with self.subTest(title=title):
                self.assertTrue(contains_excluded_keyword(title))


class CompanyAndExperienceFilterTests(unittest.TestCase):
    def test_aston_company_is_excluded_case_insensitively(self):
        self.assertTrue(contains_excluded_company("Aston"))
        self.assertTrue(contains_excluded_company("ООО АСТОН"))
        self.assertFalse(contains_excluded_company("Яндекс Крауд"))

    def test_three_to_six_year_experience_variants_are_excluded(self):
        variants = ("3–6 лет", "3-6 лет", "от 3 до 6 лет", "от 3х до 6 лет")

        for experience in variants:
            with self.subTest(experience=experience):
                self.assertTrue(is_excluded_experience(experience))

        self.assertFalse(is_excluded_experience("1–3 года"))


class DuplicateVacancyTests(unittest.TestCase):
    def test_same_company_and_title_prefers_saratov_then_target_timezones(self):
        vacancies = [
            {"title": "Асессор", "company": "Яндекс Крауд", "city": "Омск", "url": "omsk"},
            {"title": "Асессор", "company": "Яндекс Крауд", "city": "Москва", "url": "moscow"},
            {"title": "Асессор", "company": "Яндекс Крауд", "city": "Саратов", "url": "saratov"},
            {"title": "Другая вакансия", "company": "Яндекс Крауд", "city": "Омск", "url": "other"},
        ]

        result = deduplicate_company_titles(vacancies)

        self.assertEqual([vacancy["url"] for vacancy in result], ["saratov", "other"])

    def test_same_title_from_different_companies_is_not_a_duplicate(self):
        vacancies = [
            {"title": "Аналитик", "company": "Компания А", "city": "Самара", "url": "a"},
            {"title": "Аналитик", "company": "Компания Б", "city": "Москва", "url": "b"},
        ]

        result = deduplicate_company_titles(vacancies)

        self.assertEqual([vacancy["url"] for vacancy in result], ["a", "b"])


class RemoteFormatTests(unittest.TestCase):
    def test_remote_markers_from_search_card_and_vacancy_page(self):
        for text in ("Можно удалённо", "Удаленная работа", "Работа из дома"):
            with self.subTest(text=text):
                self.assertTrue(is_remote_text(text))

    def test_office_format_is_not_remote(self):
        self.assertFalse(is_remote_text("На месте работодателя"))


if __name__ == "__main__":
    unittest.main()
