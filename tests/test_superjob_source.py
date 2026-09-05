import unittest
from unittest.mock import Mock

import requests

from superjob_source import collect_superjob_vacancies, parse_superjob_vacancy
from vacancy_filters import deduplicate_company_titles


def fixture(**changes):
    return dict({
        "profession": "Бизнес-аналитик", "link": "https://www.superjob.ru/vakansii/test-123.html",
        "firm_name": "Компания", "date_published": 1788600000,
        "experience": {"id": 2, "title": "От 1 до 3 лет"},
        "town": {"title": "Москва"}, "place_of_work": {"id": 2, "title": "На дому"},
        "vacancyRichText": "<p>Анализировать процессы</p>",
    }, **changes)


class SuperJobTests(unittest.TestCase):
    def test_normalizes_api_fields(self):
        vacancy = parse_superjob_vacancy(fixture())
        self.assertEqual(vacancy["company_hint"], "Компания")
        self.assertEqual(vacancy["experience_hint"], "От 1 до 3 лет")
        self.assertTrue(vacancy["remote_hint"])
        self.assertEqual(vacancy["vacancy_text_hint"], "Анализировать процессы")
        self.assertEqual(vacancy["source"], "SuperJob")
        self.assertIsNotNone(vacancy["pub_date_hint"])

    def test_fallback_description_and_office(self):
        vacancy = parse_superjob_vacancy(fixture(vacancyRichText=None, work="Задачи",
            candidat="Требования", compensation="Условия", firm_name="",
            client={"title": "Работодатель"}, place_of_work={"id": 1, "title": "В офисе"}))
        self.assertFalse(vacancy["remote_hint"])
        self.assertEqual(vacancy["company_hint"], "Работодатель")
        self.assertIn("Требования", vacancy["vacancy_text_hint"])

    def test_skips_archived_missing_date_and_empty_description(self):
        for changes in ({"is_archive": True}, {"date_published": None}, {"vacancyRichText": ""}):
            with self.subTest(changes=changes):
                self.assertIsNone(parse_superjob_vacancy(fixture(**changes)))

    def test_pagination_filters_and_deduplication(self):
        session = Mock()
        session.get.side_effect = [
            Mock(status_code=200, json=lambda: {"objects": [fixture(), fixture(profession="CRM аналитик")], "more": True}),
            Mock(status_code=200, json=lambda: {"objects": [fixture()], "more": False}),
        ]
        vacancies = collect_superjob_vacancies("test-key", ["аналитик"], [], session=session, sleep=lambda _: None)
        self.assertEqual(len(vacancies), 1)
        self.assertEqual(session.get.call_count, 2)
        kwargs = session.get.call_args.kwargs
        self.assertEqual(kwargs["params"]["page"], 1)
        self.assertEqual(kwargs["headers"], {"X-Api-App-Id": "test-key"})
        self.assertFalse(kwargs["allow_redirects"])

    def test_missing_key_and_invalid_key_are_optional(self):
        session = Mock()
        self.assertEqual(collect_superjob_vacancies("", ["аналитик"], [], session=session), [])
        session.get.assert_not_called()
        session.get.return_value.status_code = 401
        self.assertEqual(collect_superjob_vacancies("test", ["a", "b"], [], session=session), [])
        self.assertEqual(session.get.call_count, 1)

    def test_network_failure_retries_without_aborting(self):
        session = Mock()
        session.get.side_effect = requests.Timeout()
        self.assertEqual(collect_superjob_vacancies("test", ["a"], [], session=session, sleep=lambda _: None), [])
        self.assertEqual(session.get.call_count, 3)

    def test_hh_priority_over_superjob_regardless_of_order_and_city(self):
        hh = {"title": "Бизнес-аналитик", "company": "Компания", "source": "hh.ru", "city": "Омск", "url": "hh"}
        sj = {"title": " бизнес–аналитик ", "company": "КОМПАНИЯ", "source": "SuperJob", "city": "Саратов", "url": "sj"}
        for vacancies in ([hh, sj], [sj, hh]):
            self.assertEqual(deduplicate_company_titles(vacancies), [hh])
        self.assertEqual(len(deduplicate_company_titles([hh, dict(sj, company="Другая")])), 2)
        self.assertEqual(len(deduplicate_company_titles([dict(hh, company=""), dict(sj, company="")])), 2)


if __name__ == "__main__":
    unittest.main()
