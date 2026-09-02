import unittest
from datetime import datetime

from habr_source import parse_habr_search_page, parse_habr_vacancy_text


SEARCH_HTML = """
<div class="vacancy-card">
  <div class="vacancy-card__date">
    <time datetime="2026-09-02T12:59:36+03:00">2 сентября</time>
  </div>
  <div class="vacancy-card__company"><a>Компания</a></div>
  <div class="vacancy-card__title">
    <a class="vacancy-card__title-link" href="/vacancies/1001">Бизнес-аналитик</a>
  </div>
  <div class="vacancy-meta">
    <div class="basic-chip"><svg><use xlink:href="#grade"></use></svg><div class="chip-with-icon__text">Middle</div></div>
    <div class="basic-chip"><svg><use href="#format"></use></svg><div class="chip-with-icon__text">Можно удалённо</div></div>
    <div class="basic-chip"><svg><use href="#placemark"></use></svg><div class="chip-with-icon__text">Саратов</div></div>
  </div>
</div>
"""


class HabrSearchParserTests(unittest.TestCase):
    def test_extracts_fields_used_by_the_existing_pipeline(self):
        vacancies = parse_habr_search_page(SEARCH_HTML)

        self.assertEqual(len(vacancies), 1)
        self.assertEqual(vacancies[0]["title"], "Бизнес-аналитик")
        self.assertEqual(vacancies[0]["url"], "https://career.habr.com/vacancies/1001")
        self.assertEqual(vacancies[0]["company_hint"], "Компания")
        self.assertEqual(vacancies[0]["experience_hint"], "Middle")
        self.assertEqual(vacancies[0]["city_hint"], "Саратов")
        self.assertTrue(vacancies[0]["remote_hint"])
        self.assertEqual(vacancies[0]["published_at_hint"], "2 сентября")
        self.assertEqual(vacancies[0]["pub_date_hint"], datetime(2026, 9, 2, 12, 59, 36))
        self.assertEqual(vacancies[0]["source"], "Habr Career")

    def test_skips_malformed_cards_without_a_title_link(self):
        self.assertEqual(parse_habr_search_page('<div class="vacancy-card"></div>'), [])


class HabrVacancyParserTests(unittest.TestCase):
    def test_extracts_only_the_vacancy_description(self):
        html = """
        <div class="vacancy-description__text"><p>Задачи</p><ul><li>Описывать процессы</li></ul></div>
        <div class="company_about">Не должно попасть в описание</div>
        """

        self.assertEqual(parse_habr_vacancy_text(html), "Задачи Описывать процессы")

    def test_returns_empty_text_when_description_is_missing(self):
        self.assertEqual(parse_habr_vacancy_text("<html></html>"), "")


if __name__ == "__main__":
    unittest.main()
