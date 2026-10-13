import streamlit as st
import pandas as pd
import numpy as np
import joblib

st.set_page_config(
    page_title="Калькулятор цен на б/у ноутбуки (OLX KZ)",
    page_icon="💻",
    layout="wide"
)

# Загрузка обученной модели
@st.cache_resource
def load_model():
    return joblib.load('models/laptop_price_model.pkl')

try:
    model = load_model()
except Exception as e:
    st.error(f"Не удалось загрузить модель 'laptop_price_model.pkl': {e}")
    st.stop()

st.title("💻 LaptopFairPrice KZ: Оценка стоимости б/у ноутбуков")
st.markdown("""
Сервис на базе машинного обучения (**Gradient Boosting**) анализирует рынок вторичных объявлений OLX по Казахстану 
и определяет справедливую рыночную цену устройства с учетом его характеристик и износа.
""")

st.write("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Основные характеристики")
    brand = st.selectbox(
        "Бренд ноутбука",
        ['ASUS', 'Acer', 'Lenovo', 'HP', 'Apple', 'MSI', 'Dell', 'Huawei', 'Gigabyte', 'Honor', 'Xiaomi', 'Samsung', 'Other']
    )
    
    series_options = [
        'Standard/Other', 'ASUS TUF', 'ASUS ROG', 'ASUS VivoBook', 'ASUS ZenBook',
        'Lenovo Legion', 'Lenovo LOQ', 'Lenovo IdeaPad', 'Lenovo ThinkPad',
        'Acer Nitro', 'Acer Predator', 'Acer Aspire', 'Acer Swift',
        'HP Victus', 'HP Omen', 'HP Pavilion', 'HP ProBook', 'HP EliteBook',
        'MacBook Air', 'MacBook Pro', 'MSI Gaming', 'Dell Gaming', 'Dell Latitude'
    ]
    series = st.selectbox("Линейка / Серия", series_options)
    
    cpu_options = [
        'Core i5', 'Core i7', 'Core i3', 'Core i9',
        'I5 Gen 12', 'I5 Gen 13', 'I5 Gen 11', 'I5 Gen 10',
        'I7 Gen 13', 'I7 Gen 12',
        'Ryzen 5', 'Ryzen 7', 'Ryzen 9', 'Ryzen 3',
        'Ryzen 5 7xxx', 'Ryzen 5 5xxx', 'Ryzen 5 4xxx', 'Ryzen 7 7xxx', 'Ryzen 7 5xxx',
        'Apple M1', 'Apple M2', 'Apple M3',
        'Celeron', 'Pentium', 'Other'
    ]
    cpu = st.selectbox("Процессор (CPU)", cpu_options)
    
    gpu_options = [
        'Integrated', 
        'NVIDIA 3050', 'NVIDIA 3060', 'NVIDIA 3070', 'NVIDIA 3080', 'NVIDIA 3050 TI',
        'NVIDIA 4050', 'NVIDIA 4060', 'NVIDIA 4070', 'NVIDIA 4080', 'NVIDIA 4090',
        'NVIDIA 1650', 'NVIDIA 1660', 'NVIDIA 1650 TI', 'NVIDIA 1660 TI',
        'NVIDIA 1050', 'NVIDIA 1060', 'NVIDIA 1070', 'NVIDIA 1080',
        'RTX 30xx', 'RTX 40xx', 'RTX 20xx', 'RTX 50xx', 'GTX 16xx', 'GTX 10xx',
        'NVIDIA Other', 'AMD Radeon'
    ]
    gpu = st.selectbox("Видеокарта (GPU)", gpu_options)

with col2:
    st.subheader("2. Память, экран и состояние")
    ram_gb = st.select_slider("Оперативная память (RAM, ГБ)", options=[4, 8, 12, 16, 20, 24, 32, 40, 48, 64], value=16)
    storage_gb = st.select_slider("Объем накопителя (SSD/HDD, ГБ)", options=[128, 256, 512, 1024, 2048, 4096], value=512)
    hz = st.select_slider("Частота экрана (Hz)", options=[60, 120, 144, 165, 240, 300, 360], value=144)
    city_group = st.selectbox("Город продажи", ['Алматы', 'Астана', 'Шымкент', 'Областные центры', 'Другие регионы'])
    
    condition = st.radio(
        "Состояние ноутбука",
        [
            "Новый / Идеальное состояние (пломбы, коробка, чек)", 
            "Обычное рабочее (б/у без серьезных дефектов)", 
            "Есть видимый дефект / поломка (скол, нет клавиши, трещина)"
        ],
        index=1
    )

is_gaming = 1 if gpu != 'Integrated' or any(k in series.lower() for k in ['tuf', 'rog', 'legion', 'nitro', 'victus', 'omen', 'gaming']) else 0

if "Новый" in condition:
    condition_score = 1
elif "дефект" in condition:
    condition_score = -1
else:
    condition_score = 0

st.write("---")

if st.button("🚀 Рассчитать рыночную стоимость", type="primary", use_container_width=True):
    input_df = pd.DataFrame([{
        'brand': brand,
        'series': series,
        'cpu': cpu,
        'gpu': gpu,
        'city_group': city_group,
        'ram_gb': float(ram_gb),
        'storage_gb': float(storage_gb),
        'hz': float(hz),
        'is_gaming': int(is_gaming),
        'condition_score': int(condition_score)
    }])
    
    pred_log = model.predict(input_df)[0]
    estimated_price = np.expm1(pred_log)
    
    # Округление до сотен тенге
    estimated_price = round(estimated_price / 100) * 100
    price_low = round((estimated_price * 0.90) / 100) * 100   # -10% для быстрой продажи
    price_high = round((estimated_price * 1.10) / 100) * 100  # +10% для выставления объявления с торгом
    
    st.success("✅ Анализ успешно завершен!")
    
    res_col1, res_col2, res_col3 = st.columns(3)
    res_col1.metric("📉 Быстрая продажа (-10%)", f"{price_low:,.0f} ₸".replace(",", " "))
    res_col2.metric("🎯 Справедливая цена", f"{estimated_price:,.0f} ₸".replace(",", " "))
    res_col3.metric("📈 Верхняя планка торга (+10%)", f"{price_high:,.0f} ₸".replace(",", " "))
    
    st.info(f"""
    💡 **Рекомендация для сделки:**
    * **Для быстрой продажи (за 2–5 дней):** выставляйте за **~{price_low:,.0f} ₸**.
    * **Для публикации на OLX:** ставьте **{price_high:,.0f} ₸** и закладывайте торг до **{estimated_price:,.0f} ₸**.
    """)