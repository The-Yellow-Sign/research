## Инструкция по настройке S3 Bucket для хранения Terraform State

В данной инструкции описан процесс создания и настройки корзины S3 в AWS для безопасного хранения файлов состояния (tfstate) ваших инфраструктурных проектов.

### Предварительные требования
1. Установленный и настроенный [AWS CLI](https://aws.amazon.com/cli/).
2. Права доступа `AdministratorAccess` или специфические права на S3 и DynamoDB.

### Шаг 1: Создание S3 Bucket
Создайте бакет с уникальным именем. Рекомендуется использовать префикс компании.

```bash
aws s3api create-bucket --bucket my-company-terraform-state --region us-east-1
```

### Шаг 2: Включение версионирования
Это критически важно для возможности восстановления состояния в случае повреждения файла.

```bash
aws s3api put-bucket-versioning --bucket my-company-terraform-state --versioning-configuration Status=Enabled
```

### Шаг 3: Настройка шифрования
Все файлы состояния должны быть зашифрованы в состоянии покоя (at rest).

```bash
aws s3api put-bucket-encryption --bucket my-company-terraform-state --server-side-encryption-configuration '{
  "Rules": [
    {
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }
  ]
}'
```

### Шаг 4: Блокировка публичного доступа
Убедитесь, что бакет закрыт от внешнего мира.

```bash
aws s3api put-public-access-block --bucket my-company-terraform-state --public-access-block-configuration '{
  "BlockPublicAcls": true,
  "IgnorePublicAcls": true,
  "BlockPublicPolicy": true,
  "RestrictPublicBuckets": true
}'
```

### Шаг 5: Создание таблицы DynamoDB для блокировок (Locking)
Для предотвращения одновременного внесения изменений несколькими инженерами необходимо использовать DynamoDB.

```bash
aws dynamodb create-table \
    --table-name terraform-state-lock \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
```

![Настройка в консоли AWS](path/to/s3_console_setup.png)

### Итог
После выполнения этих шагов ваш `backend` блок в Terraform будет выглядеть так:

```hcl
terraform {
  backend "s3" {
    bucket         = "my-company-terraform-state"
    key            = "global/s3/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

> ⚠️ NOTE: Никогда не храните конфиденциальные данные в открытом виде в tfstate, даже если он зашифрован в S3.
