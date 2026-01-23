# Quickstart Guide

Руководство по запуску и работе с RAG-сервисом (The Yellow Sign).

---

## Предварительные требования

1.  **Python 3.13+**
2.  **[uv](https://docs.astral.sh/uv/)** — современный менеджер пакетов:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
3.  **Docker & Docker Compose**

---

## Установка

### 1. Зависимости

```bash
uv sync
```

### 2. Конфигурация

```bash
cp .env.example .env
```

**Ключевые переменные в `.env`:**

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `OPENROUTER_BASE_URL` | URL API (OpenRouter или аналог) | `https://openrouter.ai/api/v1` |
| `OPENROUTER_API_KEY` | Ключ API (Обязателен) | - |
| `RAG_MODE` | Режим: `basic`, `llm_rerank`, `full` | `basic` |

---

## Инфраструктура

```bash
# Запуск основных сервисов
docker compose up -d

# Запуск GUI
docker compose --profile gui up -d

# Проверка статуса
docker compose ps
```

### Доступные сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| **Milvus** | `19530` | Векторная БД |
| **OpenSearch** | `9200` | Поисковый движок |
| **Prometheus** | `9090` | Сбор метрик |
| **Grafana** | `3000` | Визуализация (admin/admin) |
| **Attu** | `8000` | GUI для Milvus (требует `--profile gui`) |
| **OpenSearch Dashboards** | `5601` | GUI для OpenSearch (требует `--profile gui`) |

---

## Индексация документов

Поместите `.md` файлы в `devops-playbooks/`, затем:

```bash
# Инкрементальная индексация (только новое)
uv run python -m src.interfaces.cli ingest

# Полная переиндексация (очистка и загрузка)
uv run python -m src.interfaces.cli ingest --force
```

---

## Запуск приложения

### CLI Chat (Terminal UI)

```bash
uv run python -m src.interfaces.cli
```

### API Server (FastAPI)

```bash
uv run uvicorn src.interfaces.api.app:app --host 0.0.0.0 --port 8000
```


**Основные Endpoints:**

| URL | Описание |
|-----|----------|
| `/docs` | Swagger UI |
| `/metrics` | Метрики для Prometheus |
| `/health/ready` | Проверка готовности (БД + LLM) |
| `/api/v1/search` | Поиск и ответ RAG |

---

## Мониторинг

1. В приложении реализована отдача метрик на эндпоинт `/metrics`.
2. **Prometheus** автоматически скрейпит этот эндпоинт.
3. В **Grafana** ([http://localhost:3000](http://localhost:3000)) настроен автоматический датасорс.
   - Зайдите в **Explore**, выберите **Prometheus**.
   - Попробуйте метрику `rag_requests_total`.

### 📊 Справочник метрик

| Метрика | Тип | Описание | Labels | Buckets (сек) |
|---------|-----|----------|--------|---------------|
| `rag_requests_total` | Counter | Общее кол-во запросов к API | `endpoint`, `status` | - |
| `rag_request_latency_seconds` | Histogram | Латентность HTTP запросов | `endpoint` | 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0 |
| `rag_llm_latency_seconds` | Histogram | Латентность вызовов LLM | `model` | 0.5, 1.0, 2.0, 5.0, 10.0, 30.0 |
| `rag_agent_steps_total` | Counter | Кол-во шагов ReAct агента | `action` | - |
| `rag_agent_step_latency_seconds` | Histogram | Время выполнения шага агента | `action` | 0.1, 0.25, 0.5, 1.0, 2.0, 5.0 |
| `rag_tool_calls_total` | Counter | Кол-во вызовов инструментов | `tool_name`, `status` | - |
| `rag_active_sessions` | Gauge | Текущее кол-во активных чатов | - | - |
| `rag_cache_size` | Gauge | Количеcтво записей в кэше | `cache_type` | - |

---

## Evaluation

```bash
# Запуск оценки (по умолчанию Agent mode)
uv run python -m src.evaluation.run

# Опции
uv run python -m src.evaluation.run --mode rag --sample 5
```

### Опции

| Флаг | Описание |
|------|----------|
| `--mode` | `rag`, `agent`, `both` |
| `--dataset` | Путь к JSON с тестами |
| `--sample N` | Взять N первых вопросов |
| `--ragas` | Включить RAGAS метрики |
| `--resume` | Продолжить с чекпоинта |
| `--output-dir` | Директория для результатов |

### RAGAS Метрики

| Метрика | Описание |
|---------|----------|
| **Faithfulness** | Соответствие ответа контексту |
| **Context Recall** | Полнота найденного контекста |
| **Context Precision** | Точность контекста |
| **Agent Goal Accuracy** | Достиг ли агент цели |

---

## Проверка кода

```bash
# Линтинг
uv run ruff check src/

# Автофикс
uv run ruff check --fix src/

# Проверка импортов
uv run python -c "from src.interfaces.api.app import app; print('OK')"
```

---

## Troubleshooting

**1. Ошибка подключения к Milvus/OpenSearch**
```bash
docker compose ps  # Проверить статус
docker compose logs milvus  # Логи
```

**2. LLM не отвечает**
- Проверьте `LLM_BASE_URL` в `.env`
- Для LM Studio: убедитесь что сервер запущен на порту 1234

**3. Module not found**
- Используйте `uv run ...` для всех команд

**4. Health check fails**
```bash
curl http://localhost:8000/health/ready
# Смотрите какой сервис false
```

---

## Архитектура

См. [ARCHITECTURE.md](./ARCHITECTURE.md) для диаграмм и описания компонентов.
