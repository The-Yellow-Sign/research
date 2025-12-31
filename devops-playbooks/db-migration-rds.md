---
service: mysql
title: "Миграция БД из On-premise MySQL в AWS RDS (PostgreSQL)"
tags: [migration, aws, mysql, postgres]
severity: medium
---

# Руководство по миграции MySQL -> PostgreSQL через AWS DMS

Данный документ описывает процесс миграции критически важной базы данных "Orders" из локального дата-центра в облако AWS с изменением движка БД.

## Предварительные условия
- Развернут инстанс AWS RDS PostgreSQL (Target).
- Доступен AWS DMS Replication Instance.
- Установлен [pgloader](https://github.com/dimitri/pgloader) для сложной трансформации схем.

## Этапы миграции

### 1. Подготовка схемы
Поскольку типы данных MySQL и PostgreSQL различаются, необходимо заранее подготовить схему в целевой БД.

```sql
-- Пример неявного преобразования типов в pgloader
LOAD DATABASE
     FROM mysql://user:pass@source-host/dbname
     INTO postgresql://user:pass@target-host/dbname

 CAST type datetime to timestamptz,
      type tinyint to boolean;
```

### 2. Настройка AWS DMS
1. Создайте **Source Endpoint** (MySQL).
2. Создайте **Target Endpoint** (RDS PostgreSQL).
3. Создайте **Replication Task** с типом `Full load and ongoing replication`.

### 3. Проверка целостности (Validation)
После завершения Full Load необходимо сравнить количество строк в таблицах.

| Таблица | MySQL (Count) | PostgreSQL (Count) | Статус |
| :--- | :--- | :--- | :--- |
| `users` | 1,240,551 | 1,240,551 | OK |
| `orders` | 8,912,440 | 8,912,440 | OK |

## Особенности (Edge cases)
- **Индексы**: Полная копия индексов может замедлить миграцию. Рекомендуется создавать индексы ПОСЛЕ завершения переноса данных.
- **Внешние ключи**: Отключите `Foreign Key Checks` на время заливки.

> [!IMPORTANT]
> Время простоя (downtime) планируется на воскресенье 02:00. В это время необходимо переключить `DB_HOST` в конфигах микросервисов.

## Полезные ссылки
- [AWS DMS Documentation](https://aws.amazon.com/dms/)
- [PostgreSQL Tuning Guide](es-tuning.md)
