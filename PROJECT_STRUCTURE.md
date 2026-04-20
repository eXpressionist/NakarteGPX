# Структура проекта

## Обзор файлов

### 📁 Корневая директория

| Файл | Назначение | Важность |
|------|-----------|----------|
| [`README.md`](README.md:1) | Основная документация проекта | ⭐⭐⭐ |
| [`QUICKSTART.md`](QUICKSTART.md:1) | Быстрый старт за 5 минут | ⭐⭐⭐ |
| [`TESTING.md`](TESTING.md:1) | Руководство по тестированию | ⭐⭐ |
| [`NAKARTE_API.md`](NAKARTE_API.md:1) | Документация API nakarte.me | ⭐⭐ |
| [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md:1) | Этот файл - описание структуры | ⭐ |

### 🐳 Docker файлы

| Файл | Назначение | Важность |
|------|-----------|----------|
| [`Dockerfile`](Dockerfile:1) | Multi-stage образ для бота | ⭐⭐⭐ |
| [`docker-compose.yml.example`](docker-compose.yml.example:1) | Шаблон оркестрации сервиса bot с файловым кешем | ⭐⭐⭐ |
| [`.dockerignore`](.dockerignore:1) | Исключения для Docker build | ⭐ |

### ⚙️ Конфигурация

| Файл | Назначение | Важность |
|------|-----------|----------|
| [`.env.example`](.env.example:1) | Шаблон переменных окружения | ⭐⭐⭐ |
| `.env` | Ваша конфигурация (создается вручную) | ⭐⭐⭐ |
| [`requirements.txt`](requirements.txt:1) | Python зависимости | ⭐⭐⭐ |
| [`.gitignore`](.gitignore:1) | Исключения для Git | ⭐⭐ |

### 🧪 Тестирование

| Файл | Назначение | Важность |
|------|-----------|----------|
| [`test_nakarte.py`](test_nakarte.py:1) | Standalone скрипт для тестирования GPX | ⭐⭐ |

---

## 📦 Директория `src/`

### Основные файлы

| Файл | Назначение | Строк кода |
|------|-----------|------------|
| [`src/__init__.py`](src/__init__.py:1) | Инициализация пакета | ~3 |
| [`src/main.py`](src/main.py:1) | Точка входа приложения | ~180 |

#### [`src/main.py`](src/main.py:1) - Главный модуль

**Ключевые компоненты:**
- `Application` класс - основной класс приложения
- `setup()` - инициализация сервисов
- `start()` - запуск бота
- `shutdown()` - graceful shutdown
- Signal handlers для SIGTERM/SIGINT

**Зависимости:**
- aiogram (Bot, Dispatcher)
- dotenv (загрузка .env)
- asyncio (async/await)

---

### 📁 `src/bot/` - Telegram бот

| Файл | Назначение | Строк кода |
|------|-----------|------------|
| [`src/bot/__init__.py`](src/bot/__init__.py:1) | Инициализация пакета | ~1 |
| [`src/bot/handlers.py`](src/bot/handlers.py:1) | Обработчики сообщений | ~220 |

#### [`src/bot/handlers.py`](src/bot/handlers.py:1) - Обработчики

**Класс `BotHandlers`:**
- `cmd_start()` - команда `/start`
- `cmd_help()` - команда `/help`
- `handle_url()` - обработка URL nakarte.me

**Функциональность:**
- Валидация URL
- Проверка кеша
- Загрузка GPX через NakarteService
- Отправка файла пользователю
- Обработка ошибок с понятными сообщениями на русском

**Логирование:**
- `url_received` - получен URL
- `cache_hit` / `cache_miss` - статус кеша
- `gpx_sent` - файл отправлен
- Все ошибки с деталями

---

### 📁 `src/services/` - Бизнес-логика

| Файл | Назначение | Строк кода |
|------|-----------|------------|
| [`src/services/__init__.py`](src/services/__init__.py:1) | Инициализация пакета | ~1 |
| [`src/services/nakarte_service.py`](src/services/nakarte_service.py:1) | Извлечение GPX из nakarte.me | ~200 |
| [`src/services/cache_service.py`](src/services/cache_service.py:1) | Абстракция кеширования | ~200 |

#### [`src/services/nakarte_service.py`](src/services/nakarte_service.py:1) - Nakarte сервис

**Класс `NakarteService`:**

**Методы:**
- `validate_url(url)` - валидация URL nakarte.me
- `extract_track_id(url)` - извлечение ID трека
- `download_gpx(url)` - загрузка GPX через Playwright
- `close()` - закрытие браузера

**Процесс загрузки:**
1. Открытие страницы nakarte.me
2. Ожидание инициализации приложения (5 сек)
3. Доступ к `window.app.trackManager`
4. Извлечение треков и полилиний
5. Генерация GPX XML
6. Возврат данных

**Особенности:**
- Использует Playwright для автоматизации браузера
- Headless режим по умолчанию
- Настраиваемый timeout
- Fallback на ручную генерацию GPX

#### [`src/services/cache_service.py`](src/services/cache_service.py:1) - Кеш сервис

**Абстрактный класс `CacheService`:**
- `get(key)` - получение из кеша
- `set(key, value, ttl)` - сохранение в кеш
- `exists(key)` - проверка существования
- `close()` - закрытие соединения

**Реализации:**

1. **`RedisCache`** - Redis кеш
   - Асинхронный клиент redis.asyncio
   - Автоматическое переподключение
   - TTL поддержка

2. **`FileCache`** - Файловый кеш
   - Хранение в директории `./cache`
   - SHA256 хеш для имен файлов
   - Простая реализация без TTL

**Factory функция:**
- `create_cache_service()` - создание нужной реализации

---

### 📁 `src/utils/` - Утилиты

| Файл | Назначение | Строк кода |
|------|-----------|------------|
| [`src/utils/__init__.py`](src/utils/__init__.py:1) | Инициализация пакета | ~1 |
| [`src/utils/logger.py`](src/utils/logger.py:1) | Структурированное логирование | ~70 |

#### [`src/utils/logger.py`](src/utils/logger.py:1) - Логирование

**Функции:**
- `setup_logging(level)` - настройка structlog
- `get_logger(name)` - получение logger instance

**Формат логов:**
```json
{
  "event": "gpx_downloaded",
  "level": "INFO",
  "timestamp": "2024-01-15T12:00:00.000000Z",
  "logger": "src.services.nakarte_service",
  "track_id": "ABC123",
  "size": 12345
}
```

**Процессоры:**
- TimeStamper (ISO 8601)
- StackInfoRenderer
- ExceptionFormatter
- JSONRenderer

---

## 🗂️ Автоматически создаваемые директории

### `cache/`
- Создается автоматически при использовании file cache
- Содержит `.gpx` файлы с хешированными именами
- Можно безопасно удалять для очистки

### `logs/` (опционально)
- Можно примонтировать через docker-compose
- Для сохранения логов на хосте

---

## 📊 Статистика проекта

### Размер кодовой базы

| Категория | Файлов | Строк кода |
|-----------|--------|------------|
| Python код | 8 | ~900 |
| Документация | 5 | ~1500 |
| Конфигурация | 5 | ~200 |
| **Всего** | **18** | **~2600** |

### Зависимости

**Production:**
- aiogram 3.4.1 - Telegram Bot framework
- playwright 1.41.2 - Browser automation
- redis 5.0.1 - Redis client
- structlog 24.1.0 - Structured logging
- python-dotenv 1.0.1 - Environment variables

**Development:**
- pytest (для будущих тестов)
- pytest-asyncio (для async тестов)

---

## 🔄 Поток данных

```
Пользователь отправляет URL
         ↓
    handlers.py
    handle_url()
         ↓
    Проверка валидации
         ↓
    cache_service.py
    get(track_id)
         ↓
    ┌─────────┴─────────┐
    ↓                   ↓
Cache Hit          Cache Miss
    ↓                   ↓
Возврат GPX    nakarte_service.py
    ↓              download_gpx()
    ↓                   ↓
    ↓           Playwright Browser
    ↓                   ↓
    ↓           nakarte.me загрузка
    ↓                   ↓
    ↓           Извлечение данных
    ↓                   ↓
    ↓           Генерация GPX XML
    ↓                   ↓
    ↓           cache_service.py
    ↓              set(track_id)
    ↓                   ↓
    └───────────┬───────┘
                ↓
         Отправка файла
         пользователю
```

---

## 🏗️ Архитектурные решения

### 1. Разделение ответственности

- **bot/** - только Telegram взаимодействие
- **services/** - бизнес-логика
- **utils/** - вспомогательные функции

### 2. Абстракции

- `CacheService` - абстрактный класс для кеша
- Легко добавить новые реализации (Memcached, etc.)

### 3. Async/Await

- Полностью асинхронный код
- Эффективное использование ресурсов
- Поддержка множественных запросов

### 4. Конфигурация

- Все настройки через environment variables
- Легко менять без пересборки
- Поддержка разных окружений (dev/prod)

### 5. Логирование

- Структурированные JSON логи
- Request ID для трейсинга
- Разные уровни (DEBUG, INFO, ERROR)

### 6. Docker

- Multi-stage build для оптимизации размера
- Non-root user для безопасности
- Health checks для мониторинга
- Resource limits для стабильности

---

## 🔐 Безопасность

### Реализованные меры

1. **Non-root user в Docker**
   - Бот работает от пользователя `botuser`
   - UID 1000

2. **Environment variables**
   - Токены не в коде
   - `.env` в `.gitignore`

3. **Security options**
   - `no-new-privileges:true` в docker-compose

4. **Input validation**
   - Валидация URL перед обработкой
   - Regex проверка формата

5. **Error handling**
   - Graceful shutdown
   - Обработка всех исключений
   - Понятные сообщения пользователям

---

## 📈 Производительность

### Оптимизации

1. **Кеширование**
   - Файловый кеш по умолчанию; Redis только при явном включении
   - TTL 24 часа по умолчанию
   - Cache hit < 500ms

2. **Browser reuse**
   - Один browser instance
   - Переиспользование между запросами
   - Экономия памяти и времени

3. **Async operations**
   - Неблокирующий I/O
   - Параллельная обработка запросов

4. **Docker optimization**
   - Multi-stage build
   - Минимальный образ
   - Layer caching

---

## 🧪 Тестирование

### Существующие инструменты

1. **[`test_nakarte.py`](test_nakarte.py:1)**
   - Standalone тестирование
   - Без зависимости от бота
   - Детальный вывод

2. **Логирование**
   - Все операции логируются
   - Легко отследить проблемы

3. **Health checks**
   - Docker health checks
   - Мониторинг доступности

### Будущие улучшения

- Unit тесты (pytest)
- Integration тесты
- Load тесты
- CI/CD pipeline

---

## 📚 Документация

### Для пользователей

- [`QUICKSTART.md`](QUICKSTART.md:1) - Быстрый старт
- [`README.md`](README.md:1) - Полная документация

### Для разработчиков

- [`TESTING.md`](TESTING.md:1) - Тестирование
- [`NAKARTE_API.md`](NAKARTE_API.md:1) - API nakarte.me
- [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md:1) - Этот файл

### Inline документация

- Docstrings во всех функциях
- Type hints везде
- Комментарии для сложной логики

---

## 🚀 Развертывание

### Development

```bash
python -m src.main
```

### Production

```bash
docker-compose up -d
```

### Мониторинг

```bash
docker-compose logs -f bot
docker stats nakarte-bot
```

---

## 🔮 Roadmap

### Планируемые улучшения

1. **Функциональность**
   - [ ] Поддержка множественных треков
   - [ ] Экспорт в KML, GeoJSON
   - [ ] Webhook режим

2. **Тестирование**
   - [ ] Unit тесты
   - [ ] Integration тесты
   - [ ] CI/CD

3. **Мониторинг**
   - [ ] Prometheus метрики
   - [ ] Grafana дашборды
   - [ ] Sentry для ошибок

4. **Масштабирование**
   - [ ] Horizontal scaling
   - [ ] Load balancing
   - [ ] Redis cluster

---

## 📞 Контакты и поддержка

При возникновении вопросов:

1. Проверьте документацию
2. Изучите логи
3. Используйте `test_nakarte.py` для отладки
4. Откройте issue на GitHub

---

**Последнее обновление:** 2024-01-15
