---
service: aws-lambda
title: "Развертывание Serverless функций на Python в AWS"
---

# Создание и деплой AWS Lambda на Python

В данной инструкции мы разберем процесс создания Lambda-функции с использованием Python и boto3.

## Шаг 1: Подготовка кода
Создайте файл `lambda_function.py`.

```python
import json
import boto3

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
```

## Шаг 2: Упаковка зависимостей
Если вашей функции нужны сторонние библиотеки (например, `requests`), их нужно упаковать в ZIP-архив.

### Установка библиотек в папку
```bash
pip install requests -t .
zip -r my_lambda.zip .
```

## Шаг 3: Деплой через AWS CLI
Создайте функцию, указав IAM роль с необходимыми правами.

```bash
aws lambda create-function --function-name MyPythonFunction \
--runtime python3.11 --handler lambda_function.lambda_handler \
--role arn:aws:iam::123456789012:role/service-role/MyRole \
--zip-file fileb://my_lambda.zip
```

### Мониторинг и логи
Все системные вызовы `print()` автоматически попадают в AWS CloudWatch Logs.

> [!TIP]
> Используйте `Lambda Layers` для хранения общих библиотек между несколькими функциями, чтобы уменьшить размер деплоймент пакета.

![Схема работы Lambda](path/to/lambda_architecture.png)
