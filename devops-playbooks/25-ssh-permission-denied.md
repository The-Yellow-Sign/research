---
title: "SSH: Permission denied (publickey)"
type: known_issue
service: ssh
---

# SSH: Permission denied (publickey)

## Ошибка

```text
user@192.168.1.10: Permission denied (publickey).
ssh: connect to host 192.168.1.10 port 22: Permission denied
kex_exchange_identification: read: Connection reset by peer
Connection reset by 192.168.1.10 port 22
debug1: No more authentication methods to try.
```

## Причина

Сервер отверг подключение, так как не нашел подходящего публичного ключа в `~/.ssh/authorized_keys` для указанного пользователя, либо права доступа на директорию `.ssh` или файл ключей выставлены неверно.

## Решение

1. Убедитесь, что ваш публичный ключ добавлен на сервер:
   ```bash
   ssh-copy-id user@192.168.1.10
   ```
2. Если доступ есть, исправьте права на сервере:
   ```bash
   chmod 700 ~/.ssh
   chmod 600 ~/.ssh/authorized_keys
   ```
