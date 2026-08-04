import os
import json
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from gigachat import GigaChat

print("Скрипт запустился")

# --- Настройки из секретов GitHub ---
SPREADSHEET_ID = "1qo851AXJysBjgl3L7LhCFt4AK74y3agelflwhTY16gY"
GIGACHAT_KEY = os.environ.get("GIGACHAT_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS")

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

CANDIDATE_PROFILE = """
Имя - Владислав
Кандидат: Junior / Junior+ системный аналитик, бизнес-аналитик, AI Automation Specialist.

Технические навыки:
- Бизнес-анализ: сбор требований, User Story, Use Case, BPMN, UML, AS-IS/TO-BE, SDLC
- Системный анализ: REST API, JSON, Swagger, Postman, базовый SOAP, интеграции, микросервисы
- SQL: SELECT, WHERE, JOIN, GROUP BY, ORDER BY
- Инструменты: Jira, Confluence, Miro, Notion, Figma (базово)
- AI: ChatGPT, Claude, Gemini, OpenAI API, Telegram Bot API, Prompt Engineering

Проекты:
- Автоматизация хостела: анализ процессов, AS-IS/TO-BE, требования, BPMN
- Telegram-боты с ИИ: OpenAI API, промпты, логика обработки

Предпочтения:
- Отрасли: FinTech, EdTech, AI, SaaS, ERP, автоматизация, B2B
- Формат: удалёнка, гибрид

Стратегия:
- Соответствие ≥85% — отклик обязательно
- Соответствие 70-84% — отклик обязательно  
- Соответствие 55-69% — отклик если интересна область
- Ниже 55% — пропускать
- Не считать отсутствие коммерческого опыта критичным
- Требование 1-3 года не является критичным для junior
- Повышать оценку на 5-10% если вакансия связана с AI, автоматизацией, API, интеграциями, FinTech, EdTech
"""

ANALYSIS_PROMPT = """Ты AI-ассистент по поиску работы. Проанализируй вакансию по шаблону.

Профиль кандидата:
{profile}

Описание вакансии:
{vacancy_text}

Дай анализ строго по шаблону:

ОБЩАЯ ОЦЕНКА СООТВЕТСТВИЯ: XX%

КАТЕГОРИЯ: (сильное соответствие / стоит откликаться / откликаться если интересна область / пропустить)

ТРЕБОВАНИЯ, КОТОРЫМ СООТВЕТСТВУЕТ:
✓ ...
✓ ...

GAP (чего не хватает):
Критические:
△ ...
Некритические:
△ ...

ПЛЮСЫ ВАКАНСИИ:
- ...

МИНУСЫ ВАКАНСИИ:
- ...

ВЕРДИКТ: ДА / НЕТ
ПРИЧИНА: 2-3 предложения.
ПРИОРИТЕТ: Высокий / Средний / Низкий
"""

LETTER_PROMPT = """Напиши сопроводительное письмо для вакансии.

- Подписывать письмо именем Владислав
- Не использовать [Ваше имя] или placeholder

Профиль кандидата:
{profile}

Вакансия: {vacancy_title}
Описание: {vacancy_text}

Правила:
- Естественный стиль, не шаблонно
- Не писать "я идеально подхожу", "обладаю большим опытом"
- Использовать только реальные факты: проект автоматизации хостела, Telegram-боты с ИИ, SQL, API, BPMN, UML
- Не придумывать опыт которого нет
- Адаптировать письмо под конкретную вакансию
- Длина: 3-4 абзаца

Напиши только текст письма, без пояснений.

Пример письма, которое взять за шаблон:
Здравствуйте!

Меня заинтересовала позиция ... в компании ... . Мне интересно развиваться на стыке бизнес- и системного анализа, участвовать в проектировании решений и работать с требованиями, интеграциями и документацией.

В рамках обучения я выполнял проекты по анализу и моделированию бизнес-процессов, проектировал AS-IS и TO-BE модели, формировал требования к системе и пользовательским ролям. Изучаю BPMN, UML, SQL, REST API, JSON, основы интеграций и жизненный цикл разработки ПО. Для работы с задачами и документацией использовал Jira, Confluence, Miro и Notion. Особенно интересно развиваться как универсальный аналитик, понимающий как бизнес-логику, так и техническую сторону решений.

Буду рад подробнее рассказать о своей подготовке и мотивации на интервью. Спасибо за внимание к моей кандидатуре.
"""

# --- Google Sheets ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

headers_row = ["№", "Название", "Опыт", "Город", "Удалённо", "Дата", "Оценка", "Вердикт", "Анализ", "Письмо", "Ссылка"]
sheet.clear()
sheet.append_row(headers_row)

# --- Selenium ---
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

search_queries = [
    "бизнес аналитик",
    "системный аналитик",
    "junior бизнес аналитик",
    "junior системный аналитик",
    "business analyst",
    "system analyst",
    "AI автоматизация бизнес процессов",
    "специалист по автоматизации ИИ",
    "разработчик AI агентов",
    "автоматизация n8n",
    "специалист ИИ автоматизация",
    "нейросети"
]

exclude_keywords = [
    "senior", "сеньор", "lead", "лид", "руководитель",
    "главный", "ведущий", "principal", "head", "архитектор",
    "1с", "внедрени", "хранилищ", "недвижимост",
    "outbound", "crm-аналитик", "первой линии", "второй линии",
    "аналитик данных", "hr-аналитик", "data analyst", "data", "портфельный",
    "финансовый аналитик", "продуктовый аналитик", "Crypto", "Маркетинговый",
    "Инвестиционный", "Дизайн", "Старший", "Специалист 1-я линии поддержки", "спикер","ЭДО",
    "маркетолог", "менеджер по продажам", "продажи", "разработчик", "инженер", 
    "Младший менеджер проектов в стрим стратегической аналитики"
]

relevant_keywords = [
    "аналитик", "analyst", "автоматизац", "automation", "ai-агент", "ии"
]

local_cities = ["саратов", "энгельс"]

months_map = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
}


def parse_ru_date(text):
    try:
        parts = text.strip().split()
        day = int(parts[0])
        month = months_map.get(parts[1].lower(), 0)
        year = int(parts[2]) if len(parts) > 2 else datetime.now().year
        return datetime(year, month, day)
    except Exception:
        return None


def get_vacancy_date_and_text(url):
    try:
        driver.get(url)
        time.sleep(2)

        pub_date = None
        pub_date_str = "не указана"
        months = list(months_map.keys())
        all_elements = driver.find_elements(By.XPATH, "//*[text()]")
        for elem in all_elements:
            text = elem.text.strip()
            if any(m in text.lower() for m in months) and 5 < len(text) < 40:
                if any(char.isdigit() for char in text):
                    for part in text.split():
                        if part.isdigit() and int(part) <= 31:
                            idx = text.split().index(part)
                            date_str = " ".join(text.split()[idx:idx+3])
                            parsed = parse_ru_date(date_str)
                            if parsed:
                                pub_date = parsed
                                pub_date_str = date_str
                                break
                if pub_date:
                    break

        vacancy_text = ""
        try:
            desc = driver.find_element(By.CSS_SELECTOR, "[data-qa='vacancy-description']")
            vacancy_text = desc.text[:3000]
        except Exception:
            vacancy_text = driver.find_element(By.TAG_NAME, "body").text[:3000]

        return pub_date, pub_date_str, vacancy_text
    except Exception:
        return None, "не указана", ""


def get_vacancy_details(url):
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        experience = ""
        exp_block = soup.find(attrs={"data-qa": "vacancy-experience"})
        if exp_block:
            experience = exp_block.text.strip().lower()

        city = ""
        address_block = soup.find(attrs={"data-qa": "vacancy-address-with-map"})
        if address_block:
            city = address_block.text.strip().lower()

        remote = False
        format_block = soup.find(attrs={"data-qa": "work-formats-text"})
        if format_block and "удал" in format_block.text.lower():
            remote = True

        return experience, city, remote
    except Exception:
        return "", "", False


def analyze_vacancy(title, vacancy_text):
    try:
        giga = GigaChat(credentials=GIGACHAT_KEY, verify_ssl_certs=False)
        prompt = ANALYSIS_PROMPT.format(
            profile=CANDIDATE_PROFILE,
            vacancy_text=f"{title}\n\n{vacancy_text}"
        )
        response = giga.chat(prompt)
        giga.close()
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка анализа: {e}"


def generate_letter(title, vacancy_text):
    try:
        giga = GigaChat(credentials=GIGACHAT_KEY, verify_ssl_certs=False)
        prompt = LETTER_PROMPT.format(
            profile=CANDIDATE_PROFILE,
            vacancy_title=title,
            vacancy_text=vacancy_text[:2000]
        )
        response = giga.chat(prompt)
        giga.close()
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка письма: {e}"


def extract_score_and_verdict(analysis_text):
    score = ""
    verdict = ""
    for line in analysis_text.split("\n"):
        if "ОБЩАЯ ОЦЕНКА" in line.upper() and "%" in line:
            import re
            nums = re.findall(r'\d+', line)
            if nums:
                score = nums[0] + "%"
        if "ВЕРДИКТ" in line.upper():
            if "ДА" in line.upper():
                verdict = "ДА"
            elif "НЕТ" in line.upper():
                verdict = "НЕТ"
    return score, verdict


# --- Шаг 1: собираем вакансии ---
all_vacancies = []
seen_urls = set()

for query in search_queries:
    print(f"Ищу: {query}")
    for page in range(0, 5):
        params = {"text": query, "area": 113, "host": "hh.ru", "page": page}
        try:
            response = requests.get("https://hh.ru/search/vacancy", headers=headers, params=params, timeout=15)
        except Exception as e:
            print(f"  Ошибка запроса: {e}")
            time.sleep(10)
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        vacancies = soup.find_all("a", attrs={"data-qa": "serp-item__title"})

        print(f"  Страница {page}: {len(vacancies)} вакансий")

        if not vacancies:
            break

        for vacancy in vacancies:
            href = vacancy["href"]
            title = vacancy.text.strip()
            title_lower = title.lower()

            if "adsrv.hh.ru" in href:
                continue
            if not any(kw in title_lower for kw in relevant_keywords):
                continue
            if any(kw in title_lower for kw in exclude_keywords):
                continue

            if href.startswith("http"):
                url = href.split("?")[0]
            else:
                url = "https://hh.ru" + href.split("?")[0]

            if url not in seen_urls:
                seen_urls.add(url)
                all_vacancies.append({"title": title, "url": url})

        time.sleep(1)

print(f"\nНайдено до фильтрации: {len(all_vacancies)}")
print("Проверяю каждую вакансию...\n")

# --- Шаг 2: фильтруем и анализируем ---
filtered = []
week_ago = datetime.now() - timedelta(days=7)

for i, v in enumerate(all_vacancies):
    experience, city, remote = get_vacancy_details(v["url"])

    if "3–6" in experience or "6 лет" in experience or "более 6" in experience:
        continue

    is_local = any(c in city for c in local_cities)
    if not is_local and not remote:
        continue

    pub_date, pub_date_str, vacancy_text = get_vacancy_date_and_text(v["url"])

    if pub_date and pub_date < week_ago:
        continue

    print(f"  Анализирую: {v['title']}")

    analysis = analyze_vacancy(v["title"], vacancy_text)
    score, verdict = extract_score_and_verdict(analysis)

    letter = ""
    if verdict == "ДА":
        letter = generate_letter(v["title"], vacancy_text)

    v["experience"] = experience if experience else "не указан"
    v["city"] = city if city else "не указан"
    v["remote"] = remote
    v["published_at"] = pub_date_str
    v["pub_date"] = pub_date
    v["score"] = score
    v["verdict"] = verdict
    v["analysis"] = analysis
    v["letter"] = letter
    filtered.append(v)

    if (i + 1) % 10 == 0:
        print(f"  Обработано {i + 1}/{len(all_vacancies)}...")

driver.quit()

# --- Шаг 3: сортировка ---
filtered.sort(key=lambda x: x["pub_date"] or datetime.min, reverse=True)

print(f"\nПодходящих вакансий: {len(filtered)}\n")

# --- Шаг 4: сохранение в Google Sheets ---
rows = []
for i, v in enumerate(filtered, 1):
    rows.append([
        i,
        v["title"],
        v["experience"],
        v["city"],
        "да" if v["remote"] else "нет",
        v["published_at"],
        v["score"],
        v["verdict"],
        v["analysis"],
        v["letter"],
        v["url"]
    ])

if rows:
    sheet.append_rows(rows)

print(f"Сохранено {len(filtered)} вакансий в Google Sheets")

# --- Отправка уведомления в Telegram ---
message = f"✅ Поиск вакансий завершён!\n\nНайдено подходящих: {len(filtered)}\n\nТаблица: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"

try:
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
        timeout=15
    )
    print("Уведомление отправлено в Telegram")
except Exception as e:
    print(f"Не удалось отправить в Telegram: {e}")
