---
title: "Python: ModuleNotFoundError"
type: known_issue
service: python
---

# Python: ModuleNotFoundError: No module named 'requests'

## Ошибка

```text
Traceback (most recent call last):
  File "/app/src/main.py", line 5, in <module>
    import requests
ModuleNotFoundError: No module named 'requests'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/app/src/main.py", line 8, in <module>
    from utils import api_helper
  File "/app/src/utils/api_helper.py", line 3, in <module>
    import requests
ModuleNotFoundError: No module named 'requests'
```

## Причина

Интерпретатор Python не может найти указанную библиотеку в текущем окружении. Скорее всего, пакет не установлен или виртуальное окружение (venv) не активировано.

## Решение

Установите недостающий пакет через pip.

```bash
pip install requests
```

Или, если используется `requirements.txt`:

```bash
pip install -r requirements.txt
```
