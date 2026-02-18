#!/usr/bin/env python3
"""
Скрипт для тестирования извлечения GPX из nakarte.me
Использование: python test_nakarte.py <nakarte_url>
"""

import asyncio
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent))

from src.services.nakarte_service import NakarteService
from src.utils.logger import setup_logging


async def test_download(url: str, headless: bool = True):
    """
    Тестирование загрузки GPX из nakarte.me
    
    Args:
        url: URL трека на nakarte.me
        headless: Запускать браузер в headless режиме
    """
    print(f"\n{'='*60}")
    print(f"Тестирование загрузки GPX из nakarte.me")
    print(f"{'='*60}\n")
    
    # Настройка логирования
    setup_logging("INFO")
    
    # Создание сервиса
    service = NakarteService(headless=headless, timeout=30000)
    
    try:
        # Шаг 1: Валидация URL
        print(f"📋 URL: {url}")
        is_valid = service.validate_url(url)
        print(f"✓ Валидация: {'✅ Успешно' if is_valid else '❌ Ошибка'}")
        
        if not is_valid:
            print("\n❌ URL не прошел валидацию!")
            print("Формат должен быть: https://nakarte.me/#...&nktl=<track_id>")
            return False
        
        # Шаг 2: Извлечение ID трека
        track_id = service.extract_track_id(url)
        print(f"✓ ID трека: {track_id}")
        
        # Шаг 3: Загрузка GPX
        print(f"\n⏳ Загрузка GPX (это может занять 5-15 секунд)...")
        gpx_data = await service.download_gpx(url)
        
        # Шаг 4: Проверка результата
        print(f"✓ Размер GPX: {len(gpx_data)} байт")
        
        # Проверка формата
        gpx_str = gpx_data.decode('utf-8') if isinstance(gpx_data, bytes) else gpx_data
        
        if '<?xml' in gpx_str and '<gpx' in gpx_str:
            print(f"✓ Формат: ✅ Валидный GPX")
        else:
            print(f"✓ Формат: ⚠️ Возможно невалидный GPX")
        
        # Подсчет точек
        trkpt_count = gpx_str.count('<trkpt')
        print(f"✓ Точек трека: {trkpt_count}")
        
        # Проверка высот
        has_elevation = '<ele>' in gpx_str
        print(f"✓ Высоты: {'✅ Есть' if has_elevation else '⚠️ Отсутствуют'}")
        
        # Шаг 5: Сохранение в файл
        output_file = f"test_track_{track_id}.gpx"
        with open(output_file, 'wb' if isinstance(gpx_data, bytes) else 'w') as f:
            f.write(gpx_data)
        
        print(f"\n💾 Файл сохранен: {output_file}")
        
        # Показать превью
        print(f"\n📄 Превью GPX (первые 500 символов):")
        print("-" * 60)
        print(gpx_str[:500])
        print("-" * 60)
        
        print(f"\n✅ Тест успешно завершен!")
        return True
        
    except ValueError as e:
        print(f"\n❌ Ошибка валидации: {e}")
        return False
    except RuntimeError as e:
        print(f"\n❌ Ошибка загрузки: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await service.close()
        print(f"\n🔒 Браузер закрыт")


async def test_multiple_urls():
    """Тестирование нескольких URL"""
    test_urls = [
        "https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=FqYcC2069tzeSG-foUKGsA",
        # Добавьте свои тестовые URL здесь
    ]
    
    results = []
    for i, url in enumerate(test_urls, 1):
        print(f"\n\n{'#'*60}")
        print(f"Тест {i}/{len(test_urls)}")
        print(f"{'#'*60}")
        
        success = await test_download(url)
        results.append((url, success))
        
        if i < len(test_urls):
            print("\n⏸️ Пауза 2 секунды перед следующим тестом...")
            await asyncio.sleep(2)
    
    # Итоги
    print(f"\n\n{'='*60}")
    print(f"ИТОГИ ТЕСТИРОВАНИЯ")
    print(f"{'='*60}")
    
    for url, success in results:
        status = "✅ Успешно" if success else "❌ Ошибка"
        print(f"{status}: {url[:50]}...")
    
    success_count = sum(1 for _, s in results if s)
    print(f"\nУспешно: {success_count}/{len(results)}")


def main():
    """Главная функция"""
    if len(sys.argv) < 2:
        print("Использование:")
        print(f"  python {sys.argv[0]} <nakarte_url>")
        print(f"  python {sys.argv[0]} --test-multiple")
        print(f"  python {sys.argv[0]} <nakarte_url> --no-headless")
        print("\nПример:")
        print(f"  python {sys.argv[0]} 'https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=ABC123'")
        sys.exit(1)
    
    if sys.argv[1] == "--test-multiple":
        asyncio.run(test_multiple_urls())
    else:
        url = sys.argv[1]
        headless = "--no-headless" not in sys.argv
        
        if not headless:
            print("⚠️ Режим с видимым браузером (--no-headless)")
        
        success = asyncio.run(test_download(url, headless=headless))
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
