Ты — опытный DevOps/SRE инженер, работающий в крупной компании. Твоя задача — сгенерировать документацию для внутренней базы знаний. 

## Требования к генерации

### Типы документов (выбери случайно):
1. **Troubleshooting playbook** — пошаговое решение известной проблемы
2. **How-to guide** — инструкция по настройке/установке
3. **Architecture decision** — описание архитектурного решения
4. **Runbook** — процедура для on-call инженера
5. **Post-mortem** — разбор инцидента
6. **Migration guide** — руководство по миграции
7. **Security advisory** — описание уязвимости и патча
8. **Performance tuning** — оптимизация производительности
9. **API documentation** — документация эндпоинтов микросервиса
10. **Release notes** — changelog версии

### Сервисы/технологии (выбери 1-3 случайно):
PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch, Cassandra,
Kubernetes, Docker, Podman, Swarm,
Nginx, Apache, Traefik, HAProxy, Envoy,
Prometheus, Grafana, Loki, Jaeger, Datadog,
Kafka, RabbitMQ, NATS, Pulsar,
Terraform, Ansible, Puppet, Chef, SaltStack,
Jenkins, GitLab CI, GitHub Actions, ArgoCD, Flux,
AWS (EC2, S3, RDS, Lambda, EKS), GCP, Azure,
Linux (systemd, cgroups, networking), SSH, TLS/SSL,
Python, Go, Java, Node.js, Rust

### Условия разнообразия (применяй случайно):

**YAML frontmatter:**
- 20% — полный frontmatter (service, title, tags, severity)
- 20% — частичный (только title)
- 60% — без frontmatter вообще

**Язык:**
- 100% — русский
Допускаются английские термины, код и все что с этим связано

**Структура заголовков:**
- Иногда только H1
- Иногда H1 → H2 → H3 (полная иерархия)
- Иногда начинать сразу с H2

**Специальные элементы (включай случайно):**
- Блоки кода (bash, yaml, python, json, sql, go, java)
- Таблицы (markdown tables)
- Nested lists
- Ссылки на другие документы
- Warning/Note блоки (> ⚠️ WARNING: ...)
- Скриншоты-плейсхолдеры: ![описание](path/to/image.png)

**Длина документа:**
- 20% — короткие (500-1000 символов)
- 50% — средние (1500-4000 символов)
- 30% — длинные (5000-12000 символов)

### Сценарии edge-case (генерируй иногда):
- Имя файла НЕ соответствует содержимому (например, `quick-notes.md` про Kubernetes)
- Документ описывает проблему в одном сервисе, а решение в другом
- Устаревшая документация с deprecated командами
- Документ с TODO/FIXME комментариями
- Частично заполненный template
- Документ со stacktrace и логами ошибок

---

## Формат вывода

Сгенерируй ОДИН документ. Выведи:
1. **Рекомендуемое имя файла** (может не соответствовать содержимому)
2. **Содержимое файла** целиком

---

## Пример вывода

**Filename:** `network-troubleshooting.md`

title: "Решение проблем с DNS" service: linux
DNS Resolution Failed
При попытке резолва доменных имён сервис возвращает NXDOMAIN... [остальной контент]


Сгенерируй 10 уникальных документов. 
Для каждого выведи filename и content, разделённые "---NEXT---".
Обеспечь максимальное разнообразие: не повторяй сервисы подряд.