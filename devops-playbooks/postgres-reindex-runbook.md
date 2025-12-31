---
title: Runbook: Реиндексация таблиц PostgreSQL
---

# Процедура обслуживания индексов (Table Reindexing)

Данная процедура выполняется при высоком уровне Bloat (раздувания) индексов, когда `pg_repack` недоступен.

## Диагностика (Prometheus/Grafana)
Сначала проверьте панель "PostgreSQL Bloat Overview". Если процент Bloat > 30% для таблиц более 10ГБ, приступайте к выполнению.

## Пошаговая инструкция

1. **Мониторинг нагрузки**:
   Зайдите в Grafana и убедитесь, что CPU Load на БД < 50%.

2. **Создание индекса "рядом" (CONCURRENTLY)**:
   ```sql
   -- Выполняется без блокировки таблицы на запись
   CREATE INDEX CONCURRENTLY idx_orders_created_at_new 
   ON orders (created_at);
   ```

3. **Замена старого индекса**:
   После завершения создания (проверить через `\d orders`), удалите старый индекс:
   ```sql
   DROP INDEX CONCURRENTLY idx_orders_created_at_old;
   ```

## Возможные проблемы
- **Lock Wait**: Если в системе висит длинная транзакция, `CREATE INDEX CONCURRENTLY` будет ждать её завершения бесконечно.
- **Disk Space**: Убедитесь, что свободного места > 2x от размера текущего индекса.

### Полезные запросы
```sql
SELECT relname, last_vacuum, last_autovacuum 
FROM pg_stat_user_tables 
WHERE relname = 'orders';
```

---
*Связанные документы:*
- [Настройка алертов Prometheus для PG](monitoring/pg-alerts.md)
- [Инструкция по использованию pg_repack](db/pg-repack-manual.md)
