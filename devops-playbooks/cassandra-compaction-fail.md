# Инцидент #2024-11-20: Проблемы с производительностью Cassandra из-за зависшей компакции

## Краткое описание
20 ноября наблюдался рост задержек при чтении из кластера Cassandra (Keyspace: `user_events`). Выявлено, что одна из нод перестала отвечать из-за бесконечного процесса компакции (compaction), который занял все доступные IOPS диска.

## Хронология
- **20:00** — Рост Read Latency до 500ms на ноде `cassandra-node-5`.
- **20:15** — Нагрузка на диск (I/O Wait) достигла 90%.
- **20:30** — Попытка ручного запуска `nodetool compact` привела к зависанию сессии.
- **21:00** — Остановка процесса и очистка временных файлов.

## Технический анализ (Logs)

### Лог из `system.log`:
```text
ERROR [CompactionExecutor:42] 2024-11-20 20:12:44,123 CassandraDaemon.java:228 - Exception in thread Thread[CompactionExecutor:42,5,main]
java.lang.OutOfMemoryError: Java heap space
    at org.apache.cassandra.db.compaction.CompactionTask.runWith(CompactionTask.java:234)
```

### Состояние ноды:
```text
ID      Address          State   Load          Owns    Token
5       10.0.1.25        Down    1.4 TB        20.1%   ...
```

## Корневая причина
Использование `SizeTieredCompactionStrategy` (STCS) на больших таблицах с частыми обновлениями привело к накоплению огромного количества SSTables, которые система пыталась объединить в один гигантский файл, превышающий лимиты памяти.

## Принятые меры
1. **Смена стратегии**: Переход на `LeveledCompactionStrategy` (LCS) для таблиц с частыми операциями чтения.
2. **Лимиты**: Настроен `concurrent_compactors: 2` для предотвращения захвата всех ресурсов CPU процессом компакции.

> ⚠️ IMPORTANT: Никогда не удаляйте SSTables вручную с диска, даже если вы думаете, что они повреждены. Используйте `nodetool scrub`.
