import os
import random
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.olx.kz"
OUTPUT_FILE = "olx_laptops_expanded.csv"

# Набор категорий и поисковых срезов для охвата 5000-7000+ объявлений
# Включает общий каталог + таргетированные игровые запросы
SEARCH_TARGETS = [
    # 1. Общие категории ноутбуков по РК
    {"name": "Общий каталог", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/", "pages": 40},
    {"name": "Ноутбуки Алматы", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/almaty/", "pages": 25},
    {"name": "Ноутбуки Астана", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/astana/", "pages": 25},
    {"name": "Ноутбуки Шымкент", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/shymkent/", "pages": 15},
    
    # 2. Целевые игровые срезы (для решения проблемы нехватки GPU)
    {"name": "Игровые ноутбуки общие", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/q-игровой-ноутбук/", "pages": 25},
    {"name": "Линейка RTX", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/q-rtx/", "pages": 25},
    {"name": "Линейка GTX", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/q-gtx/", "pages": 15},
    {"name": "Lenovo Legion", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/q-legion/", "pages": 20},
    {"name": "ASUS TUF / ROG", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/q-asus-tuf/", "pages": 20},
    {"name": "ASUS ROG", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/q-asus-rog/", "pages": 20},
    {"name": "Acer Nitro", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/q-nitro/", "pages": 20},
    {"name": "HP Victus / Omen", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/q-victus/", "pages": 15},
    {"name": "MSI Gaming", "url": "https://www.olx.kz/d/elektronika/noutbuki-i-aksesuary/noutbuki/q-msi/", "pages": 20},
]


def extract_city(raw_location: str) -> str:
    if not raw_location:
        return "Не указан"
    parts = re.split(r"[,–-]", raw_location)
    return parts[0].strip() if parts else raw_location.strip()


def run_scraper():
    # Загружаем уже собранные данные, если скрипт перезапускается
    collected_urls = set()
    all_items = []
    
    if os.path.exists(OUTPUT_FILE):
        try:
            existing_df = pd.read_csv(OUTPUT_FILE)
            collected_urls = set(existing_df["url"].dropna().tolist())
            all_items = existing_df.to_dict("records")
            print(f"Загружен существующий файл: {len(all_items)} записей уже в базе.")
        except Exception as e:
            print(f"Не удалось прочитать существующий файл: {e}")

    print("Запуск браузера Chromium с маскировкой под реального пользователя...")

    with sync_playwright() as p:
        # Аргументы против детекции автоматизации
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1366,768",
            ],
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="ru-RU",
            timezone_id="Asia/Almaty",
        )

        page = context.new_page()

        # Скрываем признак автоматизации navigator.webdriver
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        total_scraped_this_run = 0

        for target in SEARCH_TARGETS:
            section_name = target["name"]
            base_target_url = target["url"]
            max_pages = target["pages"]

            print(f"\n=======================================================")
            print(f"Начало сбора среза: [{section_name}] (до {max_pages} стр.)")
            print(f"=======================================================")

            consecutive_empty_pages = 0

            for page_num in range(1, max_pages + 1):
                separator = "&" if "?" in base_target_url else "?"
                page_url = f"{base_target_url}{separator}page={page_num}"
                print(f"[{section_name}] Стр {page_num}/{max_pages} -> Загрузка...")

                try:
                    # Загрузка страницы
                    page.goto(page_url, wait_until="domcontentloaded", timeout=40000)
                    
                    # Легкая эмуляция пользователя (скролл для ленивой подгрузки)
                    page.mouse.wheel(0, random.randint(500, 1000))
                    time.sleep(random.uniform(1.6, 2.8))

                except Exception as e:
                    print(f"  Ошибка загрузки: {e}. Пропуск...")
                    continue

                soup = BeautifulSoup(page.content(), "html.parser")
                cards = soup.find_all("div", {"data-cy": "l-card"})

                if not cards:
                    consecutive_empty_pages += 1
                    print(f"  Карточки не найдены (пустая страница #{consecutive_empty_pages}).")
                    if consecutive_empty_pages >= 2:
                        print("  Достигнут конец пагинации для этого среза. Переход к следующему.")
                        break
                    continue
                else:
                    consecutive_empty_pages = 0

                page_new_count = 0

                for card in cards:
                    # Извлечение ссылки
                    link_el = card.find("a", href=True)
                    if not link_el:
                        continue
                    
                    href = link_el["href"]
                    link = href if href.startswith("http") else BASE_URL + href
                    
                    # Очищаем URL от параметров отслеживания (?reason=, &search=)
                    clean_url = link.split("?")[0]

                    if clean_url in collected_urls:
                        continue

                    # Извлечение заголовка
                    title_el = card.find("h4") or card.find("h6")
                    title = title_el.text.strip() if title_el else None

                    # Извлечение цены
                    price_el = card.find("p", {"data-testid": "ad-price"})
                    price_raw = price_el.text.strip() if price_el else None

                    price = None
                    if price_raw:
                        digits_only = re.sub(r"[^\d]", "", price_raw)
                        if digits_only:
                            price = int(digits_only)

                    # Локация и дата
                    loc_el = card.find("p", {"data-testid": "location-date"})
                    loc_raw = loc_el.text.strip() if loc_el else None
                    city = extract_city(loc_raw) if loc_raw else None

                    # Добавляем только валидные объявления с ценой выше 20 000 тг (отсекаем мусор и запчасти)
                    if title and price and price >= 20000:
                        item = {
                            "title": title,
                            "price_kzt": price,
                            "city": city,
                            "location_date_raw": loc_raw,
                            "url": clean_url,
                            "search_source": section_name,
                        }
                        all_items.append(item)
                        collected_urls.add(clean_url)
                        page_new_count += 1
                        total_scraped_this_run += 1

                print(f"  Успешно добавлено уникальных: +{page_new_count} (Всего в базе: {len(all_items)})")

                # Автосохранение каждые 3 страницы
                if page_num % 3 == 0 and page_new_count > 0:
                    df_temp = pd.DataFrame(all_items)
                    df_temp.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
                    print(f"  [Автосохранение] Сохранено в {OUTPUT_FILE} ({len(df_temp)} строк)")

                # Случайная пауза между страницами для защиты от блокировки по IP
                time.sleep(random.uniform(1.2, 2.4))

        browser.close()

    # Финальное сохранение
    df_final = pd.DataFrame(all_items)
    df_final.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"\n=======================================================")
    print(f"Сбор завершен! Всего уникальных объявлений: {len(df_final)}")
    print(f"Файл сохранен: {OUTPUT_FILE}")
    print(f"=======================================================")


if __name__ == "__main__":
    run_scraper()