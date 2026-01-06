# Quickstart Guide

Этот документ описывает полный процесс запуска и работы с RAG-сервисом (The Yellow Sign).

---

## Предварительные требования

Перед началом убедитесь, что у вас установлены:

1.  **Python 3.13+**
2.  **[uv](https://docs.astral.sh/uv/)** (современный менеджер пакетов для Python)
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
3.  **Docker & Docker Compose**

---

## Установка и Настройка

### 1. Клонирование и зависимости

```bash
# Установка зависимостей проекта (создаст .venv автоматически)
uv sync
```

### 2. Подготовка окружения

Скопируйте пример конфигурации и настройте под себя:

```bash
cp .env.example .env
```

**Ключевые переменные в `.env`:**
-   `LLM_BASE_URL`: URL API LLM (по умолчанию `http://localhost:1234/v1` для LM Studio).
-   `LLM_API_KEY`: Ключ API (для локальных моделей можно оставить заглушку).
-   `OPENROUTER_API_KEY`: Если планируете использовать внешние API (например, для evaluation).

---

## Инфраструктура

Запустите базы данных (Milvus, OpenSearch) и вспомогательные сервисы:

```bash
docker compose up -d
```

Проверьте статус контейнеров (должны быть `healthy`):
```bash
docker compose ps
```

| Сервис | Порт | Описание |
|--------|------|----------|
| **Milvus** | `19530` | Векторная база данных |
| **OpenSearch** | `9200` | Полнотекстовый поиск + хранилище метаданных |

---

## Индексация Документов

Перед использованием систему нужно наполнить данными. Поместите ваши `.md` файлы в директорию `devops-playbooks/` (или другую, указанную в настройках).

### Инкрементальная индексация
Добавляет только новые или изменённые файлы:

```bash
uv run python -m src.interfaces.cli.commands.ingest
```

### Полная переиндексация
Удаляет текущие коллекции и пересоздаёт индекс с нуля (Осторожно!):

```bash
uv run python -m src.interfaces.cli.commands.ingest --force
```

---

## Запуск Приложения

### CLI Чат-бот (Terminal UI)
Основной режим для быстрой проверки и тестов.

```bash
uv run python main.py
```

### API Сервер (FastAPI)
REST API для интеграции с фронтендом или внешними системами.

```bash
uv run uvicorn src.interfaces.api.app:app --host 0.0.0.0 --port 8000 --reload
```

-   **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
-   **Health Check**: [http://localhost:8000/health/ready](http://localhost:8000/health/ready)

---

## Оценка Качества (Evaluation)

Для запуска оценки требуется настроенный `OPENROUTER_API_KEY` (если используется LLM-судья в облаке) или локальная модель-судья.

### Запуск полного цикла оценки
```bash
uv run python -m src.evaluation.run_evaluation --limit 10
```
*`--limit N`: ограничивает количество вопросов (для теста).*

### Конфигурации RAG
Вы можете менять режим работы пайплайна через переменную окружения `RAG_MODE`.

| Режим | Описание |
|-------|----------|
| `basic` | Только векторный поиск (BGE-M3). Быстро, но ниже точность. |
| `llm_rerank` | Векторный поиск + LLM Reranking. Оптимальный баланс (Default). |
| `full` | BGE + LLM Rerank + Summarization. Максимальное качество, высокая задержка. |

Пример запуска конкретной конфигурации:
```bash
RAG_MODE=basic uv run python -m src.evaluation.run_evaluation --sample 20
```

### Другие флаги
-   `--skip-judge`: Запустить только RAG генерацию, без оценки судьёй.
-   `--sample N`: Случайная выборка N вопросов.

---

## Troubleshooting

**1. Ошибка подключения к Milvus/OpenSearch**
-   Убедитесь, что контейнеры запущены: `docker compose ps`.
-   Если порты заняты, проверьте `docker-compose.yaml`.

**2. LLM не отвечает / Connection Refused**
-   Проверьте `LLM_BASE_URL` в `.env`.
-   Если используете LM Studio: убедитесь, что сервер запущен (Start Server) и порт совпадает (обычно 1234).

**3. Ошибки импорта или "Module not found"**
-   Запускайте все команды через `uv run ...`, это гарантирует использование правильного виртуального окружения.
