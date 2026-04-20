# Бэкап кэша

По умолчанию проект использует файловый кэш. Docker хранит GPX-файлы в volume
`cache_data`; записи не имеют срока истечения и остаются там до ручной очистки
volume.

## Бэкап файлового кэша

```bash
docker run --rm -v nakartegpx_cache_data:/cache -v "%cd%":/backup alpine \
  tar czf /backup/cache-backup.tar.gz -C /cache .
```

Для PowerShell можно использовать текущий путь явно:

```powershell
docker run --rm -v nakartegpx_cache_data:/cache -v ${PWD}:/backup alpine tar czf /backup/cache-backup.tar.gz -C /cache .
```

## Восстановление файлового кэша

```bash
docker run --rm -v nakartegpx_cache_data:/cache -v "%cd%":/backup alpine \
  sh -c "cd /cache && tar xzf /backup/cache-backup.tar.gz"
```

После восстановления перезапустите бота:

```bash
docker-compose restart bot
```

## Redis

Redis больше не запускается стандартным `docker-compose.yml`. Если вы включили
`CACHE_TYPE=redis` и запускаете Redis отдельно, используйте штатные инструменты
этого Redis-инстанса (`BGSAVE`, AOF или снапшоты хостинга). В стандартной
конфигурации бэкап Redis не нужен.
