# Тестирование Nakarte GPX Bot

## Быстрый тест

### 1. Запуск бота

```bash
# Создайте .env файл
cp .env.example .env
cp docker-compose.yml.example docker-compose.yml

# Добавьте токен бота в .env
echo "TELEGRAM_BOT_TOKEN=your_token_here" >> .env

# Запустите через Docker
docker-compose up -d

# Проверьте логи
docker-compose logs -f bot
```

### 2. Тестовые ссылки nakarte.me

Используйте эти примеры для тестирования:

```
https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=FqYcC2069tzeSG-foUKGsA
https://nakarte.me/#m=13/55.75222/37.61556&l=O&nktl=AbCdEf1234567890
```

### 3. Проверка функциональности

1. **Отправьте `/start`** - должно прийти приветствие на русском
2. **Отправьте `/help`** - должна прийти справка
3. **Отправьте корректную ссылку** - должен прийти GPX файл
4. **Отправьте некорректную ссылку** - должно прийти сообщение об ошибке
5. **Отправьте ту же ссылку повторно** - должен сработать кеш (быстрее)

## Отладка

### Проверка логов

```bash
# Все логи
docker-compose logs -f

# Только бот
docker-compose logs -f bot

# Последние 100 строк
docker-compose logs --tail=100 bot
```

### Анализ логов

Ищите следующие события:

```json
{"event": "url_received", "user_id": 123456, "request_id": "uuid", "url": "..."}
{"event": "cache_hit", "track_id": "..."}
{"event": "cache_miss", "track_id": "..."}
{"event": "navigating_to_url", "url": "..."}
{"event": "waiting_for_app_initialization"}
{"event": "gpx_downloaded", "track_id": "...", "size": 1234}
{"event": "gpx_sent", "user_id": 123456, "size": 1234}
```

### Проверка кеша

**File cache:**
```bash
# Посмотрите файлы в кеше
docker-compose exec bot ls -lh /app/cache

# Проверьте содержимое
cat cache/<hash>.gpx
```

## Тестирование без Docker

### Локальный запуск

```bash
# Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Установите зависимости
pip install -r requirements.txt

# Установите браузер Playwright
playwright install chromium

# Создайте .env
cp .env.example .env
cp docker-compose.yml.example docker-compose.yml
# Отредактируйте .env и установите:
# CACHE_TYPE=file уже установлен по умолчанию

# Запустите бота
python -m src.main
```

### Тестирование отдельных компонентов

**Тест NakarteService:**

```python
import asyncio
from src.services.nakarte_service import NakarteService
from src.utils.logger import setup_logging

async def test_nakarte():
    setup_logging("DEBUG")
    service = NakarteService(headless=False, timeout=30000)
    
    url = "https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=FqYcC2069tzeSG-foUKGsA"
    
    # Проверка валидации
    print(f"Valid: {service.validate_url(url)}")
    
    # Извлечение ID
    track_id = service.extract_track_id(url)
    print(f"Track ID: {track_id}")
    
    # Скачивание GPX
    try:
        gpx_data = await service.download_gpx(url)
        print(f"GPX size: {len(gpx_data)} bytes")
        print(f"GPX preview: {gpx_data[:200]}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await service.close()

asyncio.run(test_nakarte())
```

**Тест CacheService:**

```python
import asyncio
from src.services.cache_service import create_cache_service
from src.utils.logger import setup_logging

async def test_cache():
    setup_logging("DEBUG")
    
    # Тест file cache
    cache = create_cache_service(cache_type='file', cache_dir='./test_cache')
    
    # Запись
    await cache.set('test_key', b'test_value', ttl=60)
    
    # Чтение
    value = await cache.get('test_key')
    print(f"Cached value: {value}")
    
    # Проверка существования
    exists = await cache.exists('test_key')
    print(f"Exists: {exists}")
    
    await cache.close()

asyncio.run(test_cache())
```

## Известные проблемы и решения

### Проблема: "Could not find GPX data on page"

**Причины:**
- Трек не загрузился полностью
- Неверный формат URL
- Трек был удален с nakarte.me

**Решение:**
1. Увеличьте `BROWSER_TIMEOUT` в `.env`
2. Проверьте URL в браузере вручную
3. Попробуйте другой трек

### Проблема: "Timeout while loading page"

**Причины:**
- Медленное интернет-соединение
- Nakarte.me недоступен
- Недостаточный таймаут

**Решение:**
```env
BROWSER_TIMEOUT=60000  # 60 секунд
```

### Проблема: Redis connection failed

**Решение:**
```env
CACHE_TYPE=file
```

Redis не запускается стандартным `docker-compose.yml`; включайте `CACHE_TYPE=redis` только если Redis запущен отдельно.

### Проблема: Browser crashes

**Причины:**
- Недостаточно памяти
- Проблемы с Chromium

**Решение:**
```yaml
# В docker-compose.yml увеличьте лимиты
deploy:
  resources:
    limits:
      memory: 4G
```

## Мониторинг производительности

### Время обработки

Типичные значения:
- **Cache hit**: 100-500ms
- **Cache miss (первая загрузка)**: 5-15 секунд
- **Повторная загрузка**: 100-500ms

### Использование ресурсов

```bash
# Мониторинг в реальном времени
docker stats nakarte-bot

# Проверка памяти
docker-compose exec bot ps aux

# Проверка дискового пространства
docker-compose exec bot df -h
```

## Автоматизированное тестирование

### Создание тестов (будущее улучшение)

```python
# tests/test_nakarte_service.py
import pytest
from src.services.nakarte_service import NakarteService

@pytest.mark.asyncio
async def test_validate_url():
    service = NakarteService()
    
    # Валидные URL
    assert service.validate_url("https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=ABC123")
    
    # Невалидные URL
    assert not service.validate_url("https://google.com")
    assert not service.validate_url("not a url")

@pytest.mark.asyncio
async def test_extract_track_id():
    service = NakarteService()
    url = "https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=ABC123"
    assert service.extract_track_id(url) == "ABC123"
```

Запуск тестов:
```bash
pytest tests/ -v
```

## Производственное тестирование

### Нагрузочное тестирование

```python
# load_test.py
import asyncio
import aiohttp
from time import time

async def send_message(bot_token, chat_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, json={"chat_id": chat_id, "text": text})

async def load_test(bot_token, chat_id, num_requests=10):
    test_url = "https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=TEST123"
    
    start = time()
    tasks = [send_message(bot_token, chat_id, test_url) for _ in range(num_requests)]
    await asyncio.gather(*tasks)
    duration = time() - start
    
    print(f"Sent {num_requests} requests in {duration:.2f}s")
    print(f"Average: {duration/num_requests:.2f}s per request")

# asyncio.run(load_test("YOUR_TOKEN", "YOUR_CHAT_ID", 10))
```

### Мониторинг в продакшене

Рекомендуемые инструменты:
- **Prometheus + Grafana** - метрики
- **ELK Stack** - логи
- **Sentry** - отслеживание ошибок
- **UptimeRobot** - мониторинг доступности

## Чеклист перед деплоем

- [ ] Токен бота установлен в `.env`
- [ ] Файловый кеш работает корректно
- [ ] Логи пишутся и читаются
- [ ] Тестовая ссылка обрабатывается успешно
- [ ] Кеш работает (проверить cache hit)
- [ ] Обработка ошибок работает
- [ ] Ресурсы не превышают лимиты
- [ ] Backup настроен для `cache_data`
- [ ] Мониторинг настроен
- [ ] Документация актуальна
