# Nakarte GPX Bot

Telegram бот для скачивания GPX треков с [nakarte.me](https://nakarte.me). Бот принимает ссылки nakarte.me и возвращает пользователям GPX файлы с интеллектуальным кешированием для быстрых ответов.

## Features

- 🚀 **Fast Processing**: Persistent file cache by default, optional Redis backend
- 🤖 **Browser Automation**: Uses Playwright for reliable GPX extraction
- 🐳 **Docker Ready**: Fully containerized with docker-compose
- 📝 **Structured Logging**: Comprehensive logging with request tracing
- 🔒 **Secure**: Runs as non-root user in Docker
- 🌐 **Russian Interface**: User-friendly messages in Russian
- ⚡ **Async/Await**: Built with modern async Python patterns

## Architecture

```
project/
├── docker-compose.yml.example # Docker Compose template
├── Dockerfile              # Multi-stage Docker build
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── test_nakarte.py        # Standalone testing script
├── README.md              # This file
├── TESTING.md             # Testing guide
├── NAKARTE_API.md         # Nakarte.me API documentation
├── src/
│   ├── __init__.py
│   ├── main.py            # Application entry point
│   ├── bot/
│   │   ├── __init__.py
│   │   └── handlers.py    # Telegram bot handlers
│   ├── services/
│   │   ├── __init__.py
│   │   ├── nakarte_service.py  # GPX extraction service
│   │   └── cache_service.py    # Caching abstraction
│   └── utils/
│       ├── __init__.py
│       └── logger.py      # Structured logging setup
└── cache/                 # Cache directory (created automatically)
```

## Prerequisites

- Docker and Docker Compose
- Telegram Bot Token (get from [@BotFather](https://t.me/botfather))

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd NakarteGPX
```

### 2. Configure Environment

Create a `.env` file from the example:

```bash
cp .env.example .env
cp docker-compose.yml.example docker-compose.yml
```

Edit `.env` and set your bot token:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 3. Build and Run

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f bot

# Stop services
docker-compose down
```

## Quick Test

Перед запуском бота можно протестировать извлечение GPX:

```bash
# Установите зависимости
pip install -r requirements.txt
playwright install chromium

# Запустите тест
python test_nakarte.py "https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=YOUR_TRACK_ID"

# Или с видимым браузером (для отладки)
python test_nakarte.py "https://nakarte.me/#..." --no-headless
```

Скрипт покажет:
- ✅ Валидацию URL
- 📋 ID трека
- 📊 Размер и количество точек
- 💾 Сохранит GPX файл локально
- 📄 Покажет превью содержимого

## Configuration

All configuration is done via environment variables in the `.env` file:

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CACHE_TYPE` | Cache backend (`file` or `redis`) | `file` |
| `CACHE_TTL` | Cache time-to-live in seconds; unset file cache stores indefinitely | _(empty)_ |
| `CACHE_DIR` | File cache directory | `./cache` |
| `REDIS_HOST` | Redis hostname, only when `CACHE_TYPE=redis` | `localhost` |
| `REDIS_PORT` | Redis port, only when `CACHE_TYPE=redis` | `6379` |
| `REDIS_DB` | Redis database number, only when `CACHE_TYPE=redis` | `0` |
| `REDIS_PASSWORD` | Redis password, only when `CACHE_TYPE=redis` | _(empty)_ |
| `LOG_LEVEL` | Logging level | `INFO` |
| `BROWSER_HEADLESS` | Run browser in headless mode | `true` |
| `BROWSER_TIMEOUT` | Browser timeout in milliseconds | `30000` |
| `NAKARTE_APP_READY_TIMEOUT` | Early nakarte app readiness wait in milliseconds | `8000` |
| `DOWNLOAD_CONCURRENCY` | Max concurrent uncached GPX downloads | `1` |
| `ADMIN_USER_IDS` | Comma-separated Telegram user IDs allowed to use `/stats` | _(empty)_ |
| `STATS_DB_PATH` | SQLite database path for bot statistics | `./stats/bot_stats.sqlite3` |

## Usage

### Для пользователей

1. Начните чат с ботом в Telegram
2. Отправьте `/start` для приветствия
3. Скопируйте ссылку с nakarte.me (например, `https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=FqYcC2069tzeSG-foUKGsA`)
4. Отправьте ссылку боту
5. Получите GPX файл

### Команды бота

- `/start` - Приветственное сообщение и инструкции
- `/help` - Подробная справка

### Как получить ссылку на трек

1. Откройте [nakarte.me](https://nakarte.me)
2. Создайте или загрузите трек
3. Скопируйте URL из адресной строки браузера
4. Убедитесь, что URL содержит параметр `nktl` (идентификатор трека)

## Development

### Local Development Setup

1. Install Python 3.11+:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Install Playwright browsers:

```bash
playwright install chromium
```

3. Create `.env` file with your configuration

4. Run the bot:

```bash
python -m src.main
```

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests (when implemented)
pytest tests/
```

## Implementation Details

### Извлечение GPX из nakarte.me

Бот использует Playwright для автоматизации браузера и извлечения GPX данных:

1. **Загрузка страницы**: Открывает nakarte.me с URL трека
2. **Ожидание инициализации**: Ждет загрузки JavaScript приложения
3. **Доступ к API**: Получает доступ к `window.app.trackManager`
4. **Извлечение данных**: Получает координаты через `getTrackPolylines()`
5. **Генерация GPX**: Создает XML в формате GPX 1.1
6. **Кеширование**: Сохраняет результат для быстрого повторного доступа

Подробнее см. [`NAKARTE_API.md`](NAKARTE_API.md:1)

### Процесс обработки запроса

```
Пользователь → Telegram Bot Handler
                      ↓
              Проверка кеша
                   ↙    ↘
            Cache Hit   Cache Miss
                ↓           ↓
           Возврат    Playwright Browser
            файла          ↓
                    nakarte.me загрузка
                          ↓
                   Извлечение GPX
                          ↓
                   Сохранение в кеш
                          ↓
                    Возврат файла
```

## Docker Details

### Multi-Stage Build

The Dockerfile uses a multi-stage build to optimize image size:

1. **Builder stage**: Compiles Python dependencies
2. **Runtime stage**: Minimal runtime with only necessary components

### Services

- **bot**: Main application container. Redis is not started by default.

### Volumes

- `cache_data`: Persistent file-based cache storage
- `./logs`: Application logs (optional)

### Resource Limits

Default limits (configurable in docker-compose.yml):
- CPU: 2 cores max, 0.5 cores reserved
- Memory: 2GB max, 512MB reserved

## Monitoring

### Health Checks

The bot includes health checks:

```bash
# Check bot container health
docker-compose ps

# View detailed health status
docker inspect nakarte-bot --format='{{.State.Health.Status}}'
```

### Logs

View structured JSON logs:

```bash
# Follow all logs
docker-compose logs -f

# Follow bot logs only
docker-compose logs -f bot

# View last 100 lines
docker-compose logs --tail=100 bot
```

### Log Fields

Each log entry includes:
- `timestamp`: ISO 8601 timestamp
- `level`: Log level (INFO, WARNING, ERROR)
- `event`: Event type
- `user_id`: Telegram user ID
- `request_id`: Unique request identifier
- Additional context-specific fields

## Troubleshooting

### Бот не запускается

1. Проверьте логи: `docker-compose logs bot`
2. Убедитесь, что токен бота правильный в `.env`
3. Проверьте, что файловый кеш доступен: `docker-compose exec bot ls -la /app/cache`

### Не удается скачать GPX

**Симптомы**: Бот отвечает "Не удалось загрузить трек"

**Решения**:
1. Проверьте доступность nakarte.me в браузере
2. Убедитесь, что URL содержит параметр `nktl`
3. Увеличьте `BROWSER_TIMEOUT` в `.env`
4. Проверьте логи: `docker-compose logs bot | grep error`
5. Протестируйте локально: `python test_nakarte.py "URL"`

**Типичные ошибки**:
```
"No tracks found on the page" - трек не загрузился или удален
"Timeout waiting for condition" - слишком маленький timeout
"Could not find GPX data" - проблема с извлечением данных
```

### Cache Issues

**Default file cache:**
```env
CACHE_TYPE=file
```

The Docker setup stores cached GPX files in the `cache_data` volume indefinitely.

### Memory Issues

If the bot runs out of memory:

1. Increase memory limits in `docker-compose.yml`
2. Reduce `BROWSER_TIMEOUT`
3. Monitor with: `docker stats nakarte-bot`

## Production Deployment

### Security Recommendations

1. **Use secrets management**: Don't commit `.env` to version control
2. **Protect optional Redis**: Set `REDIS_PASSWORD` if you enable Redis separately
3. **Use reverse proxy**: Put behind nginx for additional security
4. **Regular updates**: Keep dependencies updated
5. **Monitor logs**: Set up log aggregation (ELK, Loki, etc.)

### Scaling

For high load:

1. **Horizontal scaling**: Run multiple bot instances
2. **Shared cache**: Use Redis or another shared backend only when running multiple bot instances
3. **Load balancing**: Use Telegram's webhook mode with load balancer

### Backup

Backup important data:

```bash
# Backup file cache
docker run --rm -v nakartegpx_cache_data:/cache -v "$PWD":/backup alpine tar -czf /backup/cache-backup.tar.gz -C /cache .
```

## Testing

Подробное руководство по тестированию см. в [`TESTING.md`](TESTING.md:1)

### Быстрый тест

```bash
# Тест извлечения GPX
python test_nakarte.py "https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=ABC123"

# С видимым браузером (для отладки)
python test_nakarte.py "URL" --no-headless
```

### Проверка логов

```bash
# Следить за логами в реальном времени
docker-compose logs -f bot

# Фильтр по событиям
docker-compose logs bot | grep "gpx_downloaded"
docker-compose logs bot | grep "error"
```

## API Reference

### NakarteService

```python
from src.services.nakarte_service import NakarteService

service = NakarteService(headless=True, timeout=30000)

# Валидация URL
is_valid = service.validate_url(url)

# Извлечение ID трека
track_id = service.extract_track_id(url)

# Скачивание GPX
gpx_data = await service.download_gpx(url)

# Закрытие
await service.close()
```

### CacheService

```python
from src.services.cache_service import create_cache_service

cache = create_cache_service()

# Получение из кеша
data = await cache.get(key)

# Сохранение в кеш
await cache.set(key, value, ttl=86400)

# Проверка существования
exists = await cache.exists(key)

# Закрытие
await cache.close()
```

## Documentation

- [`README.md`](README.md:1) - Основная документация (этот файл)
- [`TESTING.md`](TESTING.md:1) - Руководство по тестированию
- [`NAKARTE_API.md`](NAKARTE_API.md:1) - Документация по API nakarte.me
- [`.env.example`](.env.example:1) - Пример конфигурации

## Contributing

1. Форкните репозиторий
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты (если применимо)
5. Создайте pull request

## License

Проект предоставляется "как есть" для образовательных и личных целей.

## Support

При возникновении проблем:
- Проверьте раздел [Troubleshooting](#troubleshooting)
- Изучите логи для деталей ошибок
- Используйте [`test_nakarte.py`](test_nakarte.py:1) для локального тестирования
- Откройте issue на GitHub

## Acknowledgments

- [nakarte.me](https://nakarte.me) - Отличный картографический сервис
- [aiogram](https://github.com/aiogram/aiogram) - Современный фреймворк для Telegram ботов
- [Playwright](https://playwright.dev/) - Надежная автоматизация браузера

## Roadmap

Планируемые улучшения:
- [ ] Поддержка множественных треков в одном URL
- [ ] Экспорт в другие форматы (KML, GeoJSON)
- [ ] Webhook режим для масштабирования
- [ ] Веб-интерфейс для мониторинга
- [ ] Автоматические тесты (pytest)
- [ ] Метрики и мониторинг (Prometheus)

---

**Примечание**: Этот бот не связан с nakarte.me. Пожалуйста, соблюдайте их условия использования и используйте ответственно.
