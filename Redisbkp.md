 Бэкап Redis (основной кэш)

    1. Через RDB-снимок (рекомендуется):

     1 # Создать снимок базы данных
     2 docker exec nakarte-redis redis-cli BGSAVE
     3
     4 # Дождаться завершения и скопировать файл
     5 docker cp nakarte-redis:/data/dump.rdb ./redis-backup-dump.rdb

    2. Через AOF-лог (если нужна полная история):

     1 # Включить AOF (если ещё не включён)
     2 docker exec nakarte-redis redis-cli CONFIG SET appendonly yes
     3
     4 # Скопировать AOF-файл
     5 docker cp nakarte-redis:/data/appendonly.aof ./redis-backup-aof.aof

    3. Полный бэкап тома Docker:

     1 # Остановить контейнер для консистентности
     2 docker compose down
     3
     4 # Скопировать весь том с данными
     5 docker run --rm -v nakarte_redis_data:/data -v $(pwd):/backup alpine tar czf /backup/redis-backup.tar.gz
       /data
     6
     7 # Запустить обратно
     8 docker compose up -d

    Бэкап файлового кэша (если используется)

    Если CACHE_TYPE=file, то кэш хранится в томе cache_data:

     1 docker compose run --rm -v cache_data:/cache alpine tar czf /tmp/cache-backup.tar.gz /cache
     2 docker cp $(docker compose ps -q bot):/tmp/cache-backup.tar.gz ./cache-backup.tar.gz

    На новом сервере

     1 # Redis: восстановить из RDB
     2 docker cp ./redis-backup-dump.rdb nakarte-redis:/data/dump.rdb
     3 docker compose restart redis

    ---

    Кэш имеет     TTL 86400 секунд (24 часа), поэтому полный бэкап нужен только если хочешь сохранить текущие закешированные
    треки.