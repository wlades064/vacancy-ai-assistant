import unittest

from hh_source import parse_hh_details
from vacancy_filters import contains_excluded_company, contains_excluded_keyword, contains_relevant_keyword


class HhDetailsTests(unittest.TestCase):
    def test_old_and_new_markup_excludes_three_to_six(self):
        for selector in ("vacancy-experience", "work-experience-text"):
            html = f'<a data-qa="vacancy-company-name">ASTON</a><div data-qa="{selector}">Опыт работы: <span>3–6</span> <span>лет</span></div>'
            company, experience, _, _, ok = parse_hh_details(html)
            self.assertTrue(ok)
            self.assertTrue(contains_excluded_company(company))
            self.assertEqual(experience, "3-6 лет")

    def test_label_fallback_and_junior_experience(self):
        for value, expected in (("Без опыта", "без опыта"), ("1–3 года", "1-3 лет"), ("3–6 лет", "3-6 лет")):
            html = f'<div data-qa="vacancy-company-name-wrapper">Компания</div><p><span>Опыт работы:</span><span>{value}</span></p>'
            details = parse_hh_details(html)
            self.assertTrue(details[4])
            self.assertEqual(details[1], expected)

    def test_missing_fields_are_not_a_success(self):
        for html in ('<h1>Captcha</h1>', '<a data-qa="vacancy-company-name">ASTON</a>',
                     '<div data-qa="vacancy-experience">Без опыта</div>'):
            self.assertFalse(parse_hh_details(html)[4])

    def test_description_numbers_are_not_experience(self):
        html = '<a data-qa="vacancy-company-name">Компания</a><div data-qa="vacancy-experience">1–3 года</div><div data-qa="vacancy-description">Компания работает 6 лет, команда из 3-6 человек</div>'
        self.assertEqual(parse_hh_details(html)[1], "1-3 лет")

    def test_conflicting_fields_choose_exclusion(self):
        html = '<a data-qa="vacancy-company-name">Компания</a><span data-qa="vacancy-experience">1–3 года</span><p>Опыт работы: 3–6 лет</p>'
        self.assertEqual(parse_hh_details(html)[1], "3-6 лет")

    def test_new_title_exclusions_and_vibe_coder(self):
        for title in ("Automation QA", "Аналитик банка", "Инженер-теплотехник", "AI-визуализатор",
                      "CRM аналитик", "Специалист СРМ и ИИ", "Амбассадор", "Юрист", "Врач", "SMM специалист"):
            self.assertTrue(contains_excluded_keyword(title), title)
        for title in ("Вайбкодер", "Vibe coder", "Vibe-coding specialist"):
            self.assertTrue(contains_relevant_keyword(title), title)
            self.assertFalse(contains_excluded_keyword(title), title)
