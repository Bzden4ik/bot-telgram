# Используем Python
FROM python:3.9

# Копируем файлы и устанавливаем зависимости
WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt

# Запускаем бота
CMD ["python", "bot.py"]
