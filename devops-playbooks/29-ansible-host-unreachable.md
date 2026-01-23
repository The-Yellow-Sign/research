---
title: "Ansible: Host Unreachable"
type: known_issue
service: ansible
---

# Ansible: Failed to connect to the host via ssh

## Ошибка

```text
TASK [Gathering Facts] *********************************************************
fatal: [192.168.1.50]: UNREACHABLE! => {
    "changed": false,
    "msg": "Failed to connect to the host via ssh: ssh: connect to host 192.168.1.50 port 22: Connection timed out",
    "unreachable": true
}
fatal: [192.168.1.51]: UNREACHABLE! => {
    "changed": false,
    "msg": "Failed to connect to the host via ssh: user@192.168.1.51: Permission denied (publickey,password).",
    "unreachable": true
}
```

## Причина

Ansible не может подключиться к управляемому хосту. Это может быть вызвано сетевыми проблемами (таймаут), неверными учетными данными SSH или отсутствием Python на целевом хосте.

## Решение

1. Проверьте доступность хоста по SSH вручную:
   ```bash
   ssh user@192.168.1.50
   ```
2. Если проблема в Python, установите его через raw модуль:
   ```bash
   ansible all -i inventory -m raw -a "apt-get install -y python3" --become
   ```
