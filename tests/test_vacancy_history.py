import unittest

from vacancy_history import exclude_seen_vacancies, vacancy_history_key, vacancy_history_keys


class VacancyHistoryTests(unittest.TestCase):
    def test_previous_report_blocks_republication_but_preserves_other_companies(self):
        previous = vacancy_history_keys("https://hh.ru/vacancy/100", "Бизнес-аналитик", "Компания")
        duplicate = {"url": "https://career.habr.com/vacancies/200",
                     "title": "БИЗНЕС–АНАЛИТИК", "company": "компания"}
        other = dict(duplicate, company="Другой работодатель")
        self.assertEqual(exclude_seen_vacancies([duplicate, other], previous), [other])

    def test_previous_report_blocks_repeat_on_every_source(self):
        pairs = [
            ("https://hh.ru/vacancy/123", "https://saratov.hh.ru/vacancy/123"),
            ("https://career.habr.com/vacancies/123", "https://career.habr.com/vacancies/123/"),
            ("https://www.superjob.ru/vakansii/analitik-123.html",
             "https://superjob.ru/vakansii/new-title-123.html"),
            ("https://arbihunter.com/ru/jobs/analyst-123", "https://arbihunter.com/ru/jobs/new-title-123"),
            ("https://raberu.ru/moscow/vacancy/1f1e1977-90d0-6db4-8028-0d6333cbb7ef",
             "https://raberu.ru/saratov/vacancy/1f1e1977-90d0-6db4-8028-0d6333cbb7ef"),
        ]
        keys = {vacancy_history_key(first) for first, _ in pairs}
        self.assertIn("123", keys)
        self.assertNotIn(None, keys)
        self.assertEqual(len(keys), len(pairs))
        repeats = [{"url": second + "?from=search"} for _, second in pairs]
        new = {"url": "https://hh.ru/vacancy/100"}
        self.assertEqual(exclude_seen_vacancies([*repeats, new], keys), [new])
