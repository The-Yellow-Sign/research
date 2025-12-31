---
title: "Настройка репликации PostgreSQL"
type: guide
service: postgres
---

# Настройка репликации PostgreSQL

## Введение

Репликация PostgreSQL обеспечивает высокую доступность и масштабируемость чтения, позволяя синхронно или асинхронно копировать данные с мастера на реплики. Это критически важно для отказоустойчивых продакшн‑систем, где требуется минимальное время простоя и возможность распределения нагрузки на чтение.

## Требования

- ОС: Linux (Ubuntu 20.04+, CentOS 8+)
- PostgreSQL: версии 12‑15
- Доступ к сети между мастером и репликами (порт 5432)
- Пользователь `replicator` с правом REPLICATION на мастере

## Пошаговая инструкция

### Шаг 1: Подготовка мастера

```bash
# На мастере, от имени postgres
sudo -u postgres psql -c "CREATE ROLE replicator WITH REPLICATION LOGIN ENCRYPTED PASSWORD 'StrongPass123';"
```

```ini
# postgresql.conf (мастер)
wal_level = replica               # включить запись WAL для репликации
max_wal_senders = 10              # количество процессов отправки WAL
wal_keep_segments = 64            # сколько сегментов WAL хранить
hot_standby = on                  # разрешить запросы на реплике
```

```ini
# pg_hba.conf (мастер)
# Разрешить репликацию от реплик
host    replication     replicator      10.0.0.0/24          md5
```

Перезапустите PostgreSQL:

```bash
sudo systemctl restart postgresql
```

### Шаг 2: База данных и базовый бэкап

```bash
# Создайте базу, если её ещё нет
sudo -u postgres createdb myapp

# Сделайте базовый бэкап
sudo -u postgres pg_basebackup -h localhost -D /var/lib/postgresql/15/main/base_backup -U replicator -Fp -Xs -P -R
```

### Шаг 3: Настройка реплики

```bash
# На реплике, скопируйте бэкап
sudo rsync -a --delete /var/lib/postgresql/15/main/base_backup/ /var/lib/postgresql/15/main/
```

```ini
# recovery.conf (или в postgresql.auto.conf для 12+)
standby_mode = 'on'
primary_conninfo = 'host=master_ip port=5432 user=replicator password=StrongPass123'
trigger_file = '/tmp/postgresql.trigger.5432'
```

Перезапустите реплику:

```bash
sudo systemctl start postgresql
```

### Шаг 4: Проверка репликации

```bash
# На реплике
sudo -u postgres psql -c "SELECT pg_is_in_recovery();"
# Ожидается: true
```

```bash
# На мастере
sudo -u postgres psql -c "SELECT client_addr, state FROM pg_stat_replication;"
```

## Проверка (Verification)

1. Выполните `SELECT now();` на реплике – время должно отставать не более нескольких секунд от мастера.
2. Сгенерируйте нагрузку записи на мастере и убедитесь, что изменения появляются на реплике (например, `INSERT INTO test VALUES (1);`).
3. Проверьте отсутствие ошибок в логах `/var/log/postgresql/postgresql-15-main.log`.
4. При необходимости переключите реплику в роль мастера, создав `trigger_file`.
