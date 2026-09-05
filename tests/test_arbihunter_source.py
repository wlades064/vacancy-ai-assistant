import json
import unittest
from datetime import datetime
from unittest.mock import Mock

from arbihunter_source import (
    collect_arbihunter_vacancies, parse_arbihunter_description, parse_arbihunter_search,
)
from vacancy_filters import deduplicate_company_titles


def page(slug="analyst-1", title="Бизнес-аналитик", total=1, **changes):
    data = dict(slug=slug, status="PUBLISHED", format="REMOTE",
                company={"title": "Компания"}, city={"name": "Саратов"},
                order={"publishedAt": "2026-09-05T10:00:00Z"})
    data.update(changes)
    flight = json.dumps({"vacancy": data, "totalPages": total})
    # Next.js can split a JSON object across multiple script chunks.
    scripts = "".join("<script>self.__next_f.push(" + json.dumps([1, part]) + ")</script>"
                      for part in (flight[:40], flight[40:]))
    return ('<a data-track-type="vacancy-track" href="/ru/jobs/' + slug + '"><h2>' + title
            + '</h2><div class="module__TagInfoContainer">Middle 1-3 года Удаленная работа</div></a>' + scripts)


class ArbiHunterTests(unittest.TestCase):
    def test_parse_visible_card_and_split_metadata(self):
        items, total = parse_arbihunter_search(page())
        self.assertEqual(total, 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["city_hint"], "Саратов")
        self.assertEqual(items[0]["experience_hint"], "1-3 года")
        self.assertTrue(items[0]["remote_hint"])
        self.assertEqual(items[0]["source"], "ArbiHunter")

    def test_nda_not_treated_as_shared_company(self):
        items, _ = parse_arbihunter_search(page(company={"title": "NDA", "isNDA": True}))
        self.assertEqual(items[0]["company_hint"], "")

    def test_missing_metadata_and_captcha_are_errors(self):
        for html in ("<h1>Captcha</h1>", page(order={})):
            with self.assertRaises(ValueError):
                parse_arbihunter_search(html)

    def test_description_excludes_surrounding_page(self):
        self.assertEqual(parse_arbihunter_description(
            '<div class="EditorWrapper-module__EditorWrapper other__Html"><p>Задачи</p></div><footer>Реклама</footer>'
        ), "Задачи")
        self.assertEqual(parse_arbihunter_description("<h1>Войдите</h1>"), "")

    def test_pagination_and_filters(self):
        session = Mock()
        session.get.side_effect = [
            Mock(status_code=200, text=page(title="CRM аналитик", total=2)),
            Mock(status_code=200, text=page(slug="analyst-2", total=2)),
            Mock(status_code=200, text='<div class="EditorWrapper test__Html">Описание</div>'),
        ]
        items = collect_arbihunter_vacancies(session=session, sleep=lambda _: None, now=datetime(2026, 9, 6))
        self.assertEqual(len(items), 1)
        self.assertEqual(session.get.call_count, 3)
        self.assertEqual(session.get.call_args_list[1].kwargs["params"], {"page": 1})

    def test_denied_access_stops_without_retry(self):
        session = Mock()
        session.get.return_value.status_code = 403
        self.assertEqual(collect_arbihunter_vacancies(session=session), [])
        self.assertEqual(session.get.call_count, 1)

    def test_old_vacancy_does_not_fetch_description(self):
        session = Mock()
        session.get.return_value = Mock(status_code=200, text=page())
        self.assertEqual(collect_arbihunter_vacancies(session=session, now=datetime(2026, 10, 1)), [])
        self.assertEqual(session.get.call_count, 1)

    def test_hh_wins(self):
        hh = dict(title="Аналитик", company="Компания", source="hh.ru", city="Омск", url="hh")
        arbi = dict(hh, source="ArbiHunter", city="Саратов", url="arbi")
        self.assertEqual(deduplicate_company_titles([arbi, hh]), [hh])


if __name__ == "__main__":
    unittest.main()
