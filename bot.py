import fitz  # PyMuPDF для работы с PDF
import pdfplumber  # для извлечения текста из PDF
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import faiss
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from prometheus_client import start_http_server, Summary
import os
import time

# Замените на ваш токен бота Telegram
TELEGRAM_TOKEN = "7949611063:AAFjuM59gUTco7S8qdG9oeiTCSwnsKbhsW0"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# Инициализация метрики времени ответа для Prometheus
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')

# Шаг 1: Импорт и разбиение данных
def extract_slides_from_pdf(file_path):
    slides = []
    pdf = fitz.open(file_path)
    for page_num in range(pdf.page_count):
        page = pdf[page_num]
        text = page.get_text("text")
        slides.append({"slide_number": page_num, "text": text})
    pdf.close()
    return slides

# Шаг 2: Векторизация текста
def vectorize_slides(slides):
    texts = [slide["text"] for slide in slides]
    vectorizer = TfidfVectorizer(max_df=0.8, min_df=2)  # Настройка параметров
    vectors = vectorizer.fit_transform(texts)
    return vectors, vectorizer

# Шаг 3: Индексирование с использованием FAISS
def create_faiss_index(vectors):
    d = vectors.shape[1]
    index = faiss.IndexFlatIP(d)  # Используем косинусное расстояние
    index.add(vectors.toarray().astype(np.float32))
    return index

# Шаг 4: Поиск по индексу FAISS
def search_faiss_index(query, vectorizer, index, slides, top_k=3):
    query_vector = vectorizer.transform([query]).toarray().astype(np.float32)
    distances, indices = index.search(query_vector, top_k)
    results = [slides[i] for i in indices[0]]
    return results

# Загрузка и обработка данных
slides = []
for file_name in os.listdir("presentation"):
    if file_name.endswith(".pdf"):
        file_path = os.path.join("presentation", file_name)
        slides.extend(extract_slides_from_pdf(file_path))

# Векторизация и создание FAISS индекса
vectors, vectorizer = vectorize_slides(slides)
index = create_faiss_index(vectors)

# Максимальная длина сообщения для Telegram
MAX_MESSAGE_LENGTH = 4000

# Обработчик команды /start
@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    await message.reply("Привет! Я бот для поиска по презентациям. Задайте ваш вопрос, и я постараюсь найти подходящие слайды.")

# Обработчик текстовых сообщений с измерением времени обработки
@dp.message_handler()
@REQUEST_TIME.time()  # Сбор метрики времени выполнения для Prometheus
async def handle_query(message: types.Message):
    query = message.text
    start_time = time.time()  # Время начала обработки запроса

    results = search_faiss_index(query, vectorizer, index, slides)

    response = "Наиболее релевантные слайды:\n"
    for result in results:
        slide_text = f"Слайд {result['slide_number'] + 1}:\n{result['text']}\n\n"
        
        # Проверка, если добавление слайда превысит допустимую длину
        if len(response) + len(slide_text) > MAX_MESSAGE_LENGTH:
            await message.reply(response)
            response = ""  # Начинаем формировать новое сообщение

        response += slide_text

    # Отправляем оставшееся сообщение, если оно не пустое
    if response:
        await message.reply(response)

    # Замер времени ответа
    response_time = time.time() - start_time
    print(f"Время ответа: {response_time:.2f} секунд")

if __name__ == "__main__":
    # Запуск HTTP-сервера для сбора метрик Prometheus
    start_http_server(8000)  # Метрики доступны по адресу http://localhost:8000
    # Запуск бота
    executor.start_polling(dp, skip_updates=True)
