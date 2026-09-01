import os
import json
import logging
import re
from collections import Counter
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
from vacancy_filters import (
    contains_excluded_company,
    contains_ai_keyword,
    contains_excluded_keyword,
    contains_relevant_keyword,
    deduplicate_company_titles,
    is_excluded_experience,
    is_remote_text,
)

print("Скрипт запустился")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# --- Настройки из секретов GitHub ---
SPREADSHEET_ID = "1qo851AXJysBjgl3L7LhCFt4AK74y3agelflwhTY16gY"
GIGACHAT_KEY = os.environ.get("GIGACHAT_KEY")
GIGACHAT_MODEL = os.environ.get("GIGACHAT_MODEL", "GigaChat-2")
GIGACHAT_SCOPE = os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
MIN_COLLECTED_VACANCIES = int(os.environ.get("MIN_COLLECTED_VACANCIES", "30"))
MAX_HH_FAILURE_RATE = float(os.environ.get("MAX_HH_FAILURE_RATE", "0.35"))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS")


def require_environment_variable(name, value):
    if not value:
        raise RuntimeError(f"Не задана обязательная переменная окружения {name}")


require_environment_variable("GIGACHAT_KEY", GIGACHAT_KEY)
require_environment_variable("GOOGLE_CREDENTIALS", GOOGLE_CREDENTIALS_JSON)

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

headers_row = ["№", "Название", "Компания", "Опыт", "Город", "Удалённо", "Дата", "Оценка", "Вердикт", "Анализ", "Письмо", "Ссылка"]

# --- Selenium ---
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
http = requests.Session()
http.headers.update(headers)


def get_hh_page(url, params=None, attempts=3):
    """Загружает страницу hh.ru с повторами при временной сетевой ошибке."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            response = http.get(url, params=params, timeout=(15, 30))
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            last_error = error
            if attempt == attempts:
                break
            delay = 10 * (2 ** (attempt - 1))
            logger.warning(
                "Ошибка hh.ru, попытка %s/%s: %s. Повтор через %s сек.",
                attempt,
                attempts,
                error,
                delay,
            )
            time.sleep(delay)
    raise last_error


def call_with_retry(operation, description, attempts=4):
    """Повторяет операцию с внешним сервисом при временном сбое."""
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception:
            if attempt == attempts:
                raise
            delay = 5 * (2 ** (attempt - 1))
            logger.warning(
                "%s: временная ошибка, попытка %s/%s. Повтор через %s сек.",
                description,
                attempt,
                attempts,
                delay,
                exc_info=True,
            )
            time.sleep(delay)

analyst_search_queries = [
    "бизнес аналитик",
    "системный аналитик",
    "junior бизнес аналитик",
    "junior системный аналитик",
    "business analyst",
    "system analyst",
]

ai_search_queries = [
    "AI автоматизация бизнес процессов",
    "специалист по автоматизации ИИ",
    "специалист по ИИ",
    "специалист по внедрению ИИ",
    "AI automation specialist",
    "AI engineer",
    "AI агенты",
    "автоматизация n8n",
    "нейросети",
    "LLM",
]

search_queries = [*analyst_search_queries, *ai_search_queries]

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
        resp = get_hh_page(url, attempts=2)
        soup = BeautifulSoup(resp.text, "html.parser")

        company = ""
        company_block = soup.find(attrs={"data-qa": "vacancy-company-name"})
        if company_block:
            company = company_block.get_text(" ", strip=True)

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
        if format_block and is_remote_text(format_block.text):
            remote = True

        return company, experience, city, remote, True
    except Exception:
        logger.exception("Не удалось получить детали вакансии %s", url)
        return "", "", "", False, False


def extract_gigachat_text(response):
    """Извлекает текст из актуального ответа SDK с поддержкой старого контракта."""
    messages = getattr(response, "messages", None)
    if messages:
        content = messages[0].content
        if isinstance(content, str):
            return content
        if content:
            text = getattr(content[0], "text", None)
            if text:
                return text

    choices = getattr(response, "choices", None)
    if choices:
        return choices[0].message.content

    raise RuntimeError("GigaChat вернул ответ в неизвестном формате")


def ask_gigachat(giga, prompt):
    response = giga.chat.create(prompt)
    return extract_gigachat_text(response)


def analyze_vacancy(giga, title, vacancy_text):
    try:
        prompt = ANALYSIS_PROMPT.format(
            profile=CANDIDATE_PROFILE,
            vacancy_text=f"{title}\n\n{vacancy_text}"
        )
        return ask_gigachat(giga, prompt)
    except Exception as e:
        logger.exception("Ошибка анализа вакансии %r", title)
        return f"Ошибка анализа: {e}"


def generate_letter(giga, title, vacancy_text):
    try:
        prompt = LETTER_PROMPT.format(
            profile=CANDIDATE_PROFILE,
            vacancy_title=title,
            vacancy_text=vacancy_text[:2000]
        )
        return ask_gigachat(giga, prompt)
    except Exception as e:
        logger.exception("Ошибка генерации письма для вакансии %r", title)
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
giga = GigaChat(
    credentials=GIGACHAT_KEY,
    scope=GIGACHAT_SCOPE,
    model=GIGACHAT_MODEL,
    verify_ssl_certs=False,
    max_retries=3,
    retry_backoff_factor=1,
)

try:
    available_models = giga.get_models()
    model_ids = {model.id_ for model in available_models.data}
    if GIGACHAT_MODEL not in model_ids:
        raise RuntimeError(
            f"Модель {GIGACHAT_MODEL!r} недоступна для этого ключа. "
            f"Доступные модели: {', '.join(sorted(model_ids))}"
        )
    logger.info(
        "GigaChat подключён, модель для генерации: %s, доступно моделей: %s",
        GIGACHAT_MODEL,
        len(available_models.data),
    )
except Exception:
    logger.exception(
        "Не удалось подключиться к GigaChat. Проверьте GIGACHAT_KEY, "
        "GIGACHAT_SCOPE и доступность модели %s",
        GIGACHAT_MODEL,
    )
    giga.close()
    driver.quit()
    raise

all_vacancies = []
seen_urls = set()
vacancies_by_url = {}
search_pages_attempted = 0
search_pages_succeeded = 0
search_pages_failed = 0
collection_stats = Counter()

for query in search_queries:
    print(f"Ищу: {query}")
    page_limit = 3 if query in ai_search_queries else 5
    for page in range(0, page_limit):
        params = {"text": query, "area": 113, "host": "hh.ru", "page": page}
        search_pages_attempted += 1
        try:
            response = get_hh_page("https://hh.ru/search/vacancy", params=params)
            search_pages_succeeded += 1
        except Exception as e:
            search_pages_failed += 1
            print(f"  Ошибка запроса: {e}")
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        vacancies = soup.find_all("a", attrs={"data-qa": "serp-item__title"})

        print(f"  Страница {page}: {len(vacancies)} вакансий")

        if not vacancies:
            break

        for vacancy in vacancies:
            href = vacancy["href"]
            title = vacancy.text.strip()
            card = vacancy.find_parent(attrs={"data-qa": "vacancy-serp__vacancy"})
            remote_hint = is_remote_text(card.get_text(" ", strip=True)) if card else False
            city_block = card.find(attrs={"data-qa": "vacancy-serp__vacancy-address"}) if card else None
            city_hint = city_block.get_text(" ", strip=True).lower() if city_block else ""
            matched_ai_query = query in ai_search_queries

            if "adsrv.hh.ru" in href:
                collection_stats["реклама"] += 1
                continue
            if not contains_relevant_keyword(title):
                collection_stats["нет релевантных слов"] += 1
                continue
            if contains_excluded_keyword(title):
                collection_stats["стоп-слово"] += 1
                continue

            if href.startswith("http"):
                url = href.split("?")[0]
            else:
                url = "https://hh.ru" + href.split("?")[0]

            if url not in seen_urls:
                seen_urls.add(url)
                item = {
                    "title": title,
                    "url": url,
                    "remote_hint": remote_hint,
                    "city_hint": city_hint,
                    "matched_ai_query": matched_ai_query,
                }
                all_vacancies.append(item)
                vacancies_by_url[url] = item
                collection_stats["собрано"] += 1
            else:
                existing = vacancies_by_url[url]
                existing["remote_hint"] = existing["remote_hint"] or remote_hint
                existing["matched_ai_query"] = existing["matched_ai_query"] or matched_ai_query
                collection_stats["дубликат"] += 1

        time.sleep(1)

print(f"\nНайдено до фильтрации: {len(all_vacancies)}")
failure_rate = search_pages_failed / search_pages_attempted if search_pages_attempted else 1
logger.info(
    "Страницы поиска hh.ru: успешно %s, с ошибкой %s, доля ошибок %.1f%%",
    search_pages_succeeded,
    search_pages_failed,
    failure_rate * 100,
)
logger.info("Первичная фильтрация: %s", dict(collection_stats))
if len(all_vacancies) < MIN_COLLECTED_VACANCIES or failure_rate > MAX_HH_FAILURE_RATE:
    driver.quit()
    giga.close()
    raise RuntimeError(
        "Сбор hh.ru неполный: найдено "
        f"{len(all_vacancies)} вакансий, ошибок страниц {failure_rate:.1%}. "
        "Google Sheets оставлена без изменений."
    )
print("Проверяю каждую вакансию...\n")

# --- Шаг 2: фильтруем и анализируем ---
filtered = []
analysis_candidates = []
analysis_failures = 0
details_attempted = 0
details_failed = 0
filter_stats = Counter()
ai_filter_stats = Counter()
week_ago = datetime.now() - timedelta(days=7)

for i, v in enumerate(all_vacancies):
    is_ai_candidate = v["matched_ai_query"] or contains_ai_keyword(v["title"])
    if is_ai_candidate:
        ai_filter_stats["собрано"] += 1
    details_attempted += 1
    company, experience, city, remote, details_ok = get_vacancy_details(v["url"])
    if not details_ok:
        details_failed += 1
        filter_stats["ошибка деталей"] += 1
        if is_ai_candidate:
            ai_filter_stats["ошибка деталей"] += 1
        continue

    city = city or v["city_hint"]

    if contains_excluded_company(company):
        filter_stats["стоп-компания"] += 1
        if is_ai_candidate:
            ai_filter_stats["стоп-компания"] += 1
        continue

    if is_excluded_experience(experience):
        filter_stats["опыт 3+ лет"] += 1
        if is_ai_candidate:
            ai_filter_stats["опыт 3+ лет"] += 1
        continue

    remote = remote or v["remote_hint"]
    is_local = any(c in city for c in local_cities)
    if not is_local and not remote:
        filter_stats["не удалённо и не локально"] += 1
        if is_ai_candidate:
            ai_filter_stats["не удалённо и не локально"] += 1
        continue

    pub_date, pub_date_str, vacancy_text = get_vacancy_date_and_text(v["url"])

    if pub_date and pub_date < week_ago:
        filter_stats["старше 7 дней"] += 1
        if is_ai_candidate:
            ai_filter_stats["старше 7 дней"] += 1
        continue

    v["experience"] = experience if experience else "не указан"
    v["company"] = company if company else "не указана"
    v["city"] = city if city else "не указан"
    v["remote"] = remote
    v["published_at"] = pub_date_str
    v["pub_date"] = pub_date
    v["vacancy_text"] = vacancy_text
    v["is_ai_candidate"] = is_ai_candidate
    analysis_candidates.append(v)

deduplicated_candidates = deduplicate_company_titles(analysis_candidates)
selected_urls = {vacancy["url"] for vacancy in deduplicated_candidates}
for vacancy in analysis_candidates:
    if vacancy["url"] not in selected_urls:
        filter_stats["дубликат компании и названия"] += 1
        if vacancy["is_ai_candidate"]:
            ai_filter_stats["дубликат компании и названия"] += 1

for i, v in enumerate(deduplicated_candidates):
    print(f"  Анализирую: {v['title']}")

    vacancy_text = v.pop("vacancy_text")
    analysis = analyze_vacancy(giga, v["title"], vacancy_text)
    if analysis.startswith("Ошибка анализа:"):
        analysis_failures += 1
    score, verdict = extract_score_and_verdict(analysis)

    letter = ""
    if verdict == "ДА":
        letter = generate_letter(giga, v["title"], vacancy_text)

    v["score"] = score
    v["verdict"] = verdict
    v["analysis"] = analysis
    v["letter"] = letter
    filtered.append(v)
    filter_stats["передано в анализ"] += 1
    if v.pop("is_ai_candidate"):
        ai_filter_stats["передано в анализ"] += 1

    if (i + 1) % 10 == 0:
        print(f"  Обработано {i + 1}/{len(deduplicated_candidates)}...")

driver.quit()
giga.close()

details_failure_rate = details_failed / details_attempted if details_attempted else 1
logger.info(
    "Детали вакансий hh.ru: успешно %s, с ошибкой %s, доля ошибок %.1f%%",
    details_attempted - details_failed,
    details_failed,
    details_failure_rate * 100,
)
logger.info("Вторичная фильтрация: %s", dict(filter_stats))
logger.info("AI-воронка: %s", dict(ai_filter_stats))
if details_failure_rate > MAX_HH_FAILURE_RATE:
    raise RuntimeError(
        f"Не удалось загрузить детали {details_failure_rate:.1%} вакансий. "
        "Google Sheets оставлена без изменений."
    )

if filtered and analysis_failures == len(filtered):
    raise RuntimeError(
        "GigaChat не смог проанализировать ни одной вакансии. "
        "Google Sheets оставлена без изменений; смотрите ошибки выше."
    )

# --- Шаг 3: сортировка ---
filtered.sort(key=lambda x: x["pub_date"] or datetime.min, reverse=True)

print(f"\nПодходящих вакансий: {len(filtered)}\n")

# --- Шаг 4: сохранение в Google Sheets ---
rows = []
for i, v in enumerate(filtered, 1):
    rows.append([
        i,
        v["title"],
        v["company"],
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

table_values = [headers_row, *rows]
existing_row_count = len(
    call_with_retry(sheet.get_all_values, "Чтение Google Sheets")
)
call_with_retry(
    lambda: sheet.update(
        values=table_values,
        range_name="A1",
        value_input_option="RAW",
    ),
    "Запись Google Sheets",
)

if existing_row_count > len(table_values):
    try:
        call_with_retry(
            lambda: sheet.batch_clear(
                [f"A{len(table_values) + 1}:L{existing_row_count}"]
            ),
            "Очистка старых строк Google Sheets",
        )
    except Exception:
        logger.exception("Новые данные записаны, но старые лишние строки не очищены")

print(f"Сохранено {len(filtered)} вакансий в Google Sheets")

# --- Отправка уведомления в Telegram ---
message = f"✅ Поиск вакансий завершён!\n\nНайдено подходящих: {len(filtered)}\n\nТаблица: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"

try:
    telegram_response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
        timeout=15
    )
    telegram_response.raise_for_status()
    print("Уведомление отправлено в Telegram")
except Exception as e:
    print(f"Не удалось отправить в Telegram: {e}")
