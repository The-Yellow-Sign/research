---
title: "Настройка репликации MySQL"
type: guide
service: mysql
---

# Настройка репликации MySQL

## Введение

Репликация MySQL позволяет создавать копию данных в режиме реального времени, повышая отказоустойчивость и масштабируемость чтения. В продакшн‑окружении обычно используют асинхронную репликацию с GTID, что упрощает переключения мастера.

## Требования

- ОС: Linux (Ubuntu 20.04+, CentOS 8+)
- MySQL Server 8.0+
- Доступ к сети между мастером и слейвами (порт 3306)
- Пользователь `repl` с правом REPLICATION SLAVE на мастере

## Пошаговая инструкция

### Шаг 1: Настройка мастера

```bash
# На мастере, от имени root MySQL
mysql -u root -p -e "CREATE USER 'repl'@'%' IDENTIFIED BY 'StrongPass123';"
mysql -u root -p -e "GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%';"
mysql -u root -p -e "FLUSH PRIVILEGES;"
```

```ini
# my.cnf (мастер)
[mysqld]
server-id = 1                 # уникальный ID мастера
log_bin = mysql-bin           # включить бинарный лог
binlog_format = ROW          # ROW‑формат для GTID
gtid_mode = ON
enforce_gtid_consistency = ON
log_slave_updates = ON
```

Перезапустите MySQL:

```bash
sudo systemctl restart mysql
```

### Шаг 2: Получите позицию GTID

```bash
mysql -u root -p -e "SELECT @@GLOBAL.gtid_executed;"
```

Запомните значение GTID (например `3E11FA47-71CA-11E1-9E33-C80AA9429562:1-100`).

### Шаг 3: Подготовка слейва

```bash
# На слейве, установите тот же my.cnf, но с другим server-id
sudo cp /etc/mysql/my.cnf /etc/mysql/my.cnf.bak
```

```ini
# my.cnf (слейв)
[mysqld]
server-id = 2                 # уникальный ID слейва
relay_log = /var/log/mysql/mysql-relay-bin.log
log_bin = mysql-bin
binlog_format = ROW
gtid_mode = ON
enforce_gtid_consistency = ON
log_slave_updates = ON
read_only = ON
```

Перезапустите MySQL на слейве:

```bash
sudo systemctl restart mysql
```

### Шаг 4: Подключите слейв к мастеру

```bash
mysql -u root -p -e "CHANGE MASTER TO \
  MASTER_HOST='master_ip', \
  MASTER_USER='repl', \
  MASTER_PASSWORD='StrongPass123', \
  MASTER_AUTO_POSITION=1;"
```

```bash
# Запустите репликацию
mysql -u root -p -e "START SLAVE;"
```

### Шаг 5: Проверка статуса репликации

```bash
mysql -u root -p -e "SHOW SLAVE STATUS\G" | grep -E 'Slave_IO_Running|Slave_SQL_Running|Seconds_Behind_Master'
```

Ожидается `Yes` для обоих и небольшое значение `Seconds_Behind_Master`.

## Проверка (Verification)

1. Выполните `SELECT @@global.gtid_executed;` на мастере и слейве – они должны совпадать после синхронизации.
2. Вставьте тестовую запись на мастере (`INSERT INTO test (msg) VALUES ('replication test');`) и проверьте её наличие на слейве.
3. Убедитесь, что в логах `/var/log/mysql/error.log` нет ошибок `Slave_IO`/`Slave_SQL`.
4. При необходимости выполните `STOP SLAVE;` и `RESET SLAVE ALL;` для переинициализации.
