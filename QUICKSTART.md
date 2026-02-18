# 🚀 Быстрый старт

## За 5 минут до запуска

### 1. Получите токен бота (2 минуты)

1. Откройте Telegram и найдите [@BotFather](https://t.me/botfather)
2. Отправьте команду `/newbot`
3. Следуйте инструкциям (имя и username бота)
4. Скопируйте токен (выглядит как `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Настройте проект (1 минута)

```bash
# Клонируйте или перейдите в директорию проекта
cd NakarteGPX

# Создайте .env файл
cp .env.example .env

# Откройте .env и вставьте токен
# Windows:
notepad .env

# Linux/Mac:
nano .env
```

В файле `.env` замените:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

на ваш токен:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

Сохраните файл.

### 3. Запустите бота (2 минуты)

```bash
# Запустите через Docker Compose
docker-compose up -d

# Проверьте, что все запустилось
docker-compose ps

# Посмотрите логи
docker-compose logs -f bot
```

Вы должны увидеть:
```json
{"event": "application_initialized", ...}
{"event": "application_setup_complete", ...}
{"event": "starting_bot", ...}
```

### 4. Протестируйте бота

1. Найдите вашего бота в Telegram по username
2. Отправьте `/start`
3. Отправьте тестовую ссылку:
   ```
   https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=FqYcC2069tzeSG-foUKGsA
   ```
4. Получите GPX файл!

## Готово! 🎉

Ваш бот работает и готов обрабатывать ссылки с nakarte.me.

---

## Что дальше?

### Остановить бота

```bash
docker-compose down
```

### Перезапустить бота

```bash
docker-compose restart bot
```

### Посмотреть логи

```bash
# Все логи
docker-compose logs -f

# Только последние 100 строк
docker-compose logs --tail=100 bot

# Поиск ошибок
docker-compose logs bot | grep error
```

### Обновить конфигурацию

1. Отредактируйте `.env`
2. Перезапустите: `docker-compose restart bot`

---

## Частые вопросы

### ❓ Бот не отвечает

**Проверьте:**
```bash
# Запущен ли контейнер?
docker-compose ps

# Есть ли ошибки в логах?
docker-compose logs bot | grep -i error

# Правильный ли токен?
cat .env | grep TELEGRAM_BOT_TOKEN
```

### ❓ "Не удалось загрузить трек"

**Причины:**
- Неверный формат URL (должен содержать `nktl=...`)
- Трек удален с nakarte.me
- Медленное соединение

**Решение:**
1. Проверьте URL в браузере
2. Увеличьте timeout в `.env`:
   ```env
   BROWSER_TIMEOUT=60000
   ```
3. Перезапустите: `docker-compose restart bot`

### ❓ Бот работает медленно

**Первая загрузка трека**: 5-15 секунд (нормально)
**Повторная загрузка**: < 1 секунды (из кеша)

Если всегда медленно:
1. Проверьте, работает ли Redis: `docker-compose ps redis`
2. Проверьте кеш: `docker-compose exec redis redis-cli KEYS "*"`

### ❓ Как использовать file cache вместо Redis?

В `.env`:
```env
CACHE_TYPE=file
```

Перезапустите: `docker-compose restart bot`

---

## Тестирование без Docker

Если хотите запустить локально без Docker:

```bash
# 1. Установите Python 3.11+
python --version

# 2. Создайте виртуальное окружение
python -m venv venv

# 3. Активируйте
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Установите зависимости
pip install -r requirements.txt

# 5. Установите браузер
playwright install chromium

# 6. Настройте .env
cp .env.example .env
# Отредактируйте .env:
# - Добавьте токен
# - Установите CACHE_TYPE=file
# - Установите REDIS_HOST=localhost (если Redis не нужен)

# 7. Запустите
python -m src.main
```

---

## Полезные команды

```bash
# Статус сервисов
docker-compose ps

# Логи в реальном времени
docker-compose logs -f bot

# Перезапуск
docker-compose restart bot

# Остановка
docker-compose down

# Полная очистка (удалит кеш!)
docker-compose down -v

# Пересборка образа
docker-compose build --no-cache

# Использование ресурсов
docker stats nakarte-bot

# Подключение к Redis
docker-compose exec redis redis-cli

# Проверка кеша
docker-compose exec redis redis-cli KEYS "*"
```

---

## Структура проекта

```
NakarteGPX/
├── .env                    ← Ваша конфигурация (создайте из .env.example)
├── docker-compose.yml      ← Запуск сервисов
├── src/                    ← Код приложения
├── cache/                  ← Кеш файлов (создается автоматически)
├── README.md               ← Полная документация
├── TESTING.md              ← Руководство по тестированию
├── NAKARTE_API.md          ← Документация API nakarte.me
└── test_nakarte.py         ← Скрипт для тестирования
```

---

## Дополнительная информация

- 📖 **Полная документация**: [`README.md`](README.md)
- 🧪 **Тестирование**: [`TESTING.md`](TESTING.md)
- 🔧 **API nakarte.me**: [`NAKARTE_API.md`](NAKARTE_API.md)

---

## Поддержка

Если что-то не работает:

1. ✅ Проверьте логи: `docker-compose logs bot`
2. ✅ Убедитесь, что токен правильный
3. ✅ Проверьте, что Docker запущен
4. ✅ Попробуйте перезапустить: `docker-compose restart`
5. ✅ Прочитайте раздел Troubleshooting в [`README.md`](README.md#troubleshooting)

---

**Готово!** Ваш бот работает и готов обрабатывать треки с nakarte.me! 🎉
