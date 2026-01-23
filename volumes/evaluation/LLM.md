# RAG Evaluation Report (RAGAS)

**Дата:** 2026-01-06T02:34:24.652838
**RAG Model:** qwen/qwen3-32b
**Evaluator:** RAGAS

## Общая сводка

| Метрика | Значение |
|---------|----------|
| Всего вопросов | 162 |
| Успешно | 162 |
| Ошибок | 0 |
| **Context Recall** | 90.2% |
| **Context Precision** | 89.2% |
| **Faithfulness** | 79.0% |
| **Answer Relevancy** | 56.3% |
| Avg RAG latency | 33.27s |

## По категориям

| Категория | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| cross_document | 1 | 67 | 0 | 80 | 83 |
| general | 4 | 88 | 77 | 80 | 0 |
| reasoning | 14 | 75 | 81 | 68 | 59 |
| database | 5 | 100 | 94 | 86 | 72 |
| development | 1 | 80 | 100 | 86 | 65 |
| cloud | 1 | 50 | 100 | 100 | 37 |
| api | 6 | 75 | 83 | 62 | 49 |
| infrastructure | 1 | 100 | 100 | 100 | 76 |
| standards | 2 | 100 | 100 | 80 | 60 |
| operations | 6 | 92 | 83 | 97 | 70 |
| troubleshooting | 34 | 94 | 94 | 81 | 55 |
| monitoring | 7 | 93 | 100 | 80 | 63 |
| iac | 3 | 67 | 67 | 80 | 37 |
| security | 12 | 100 | 94 | 79 | 56 |
| tuning | 11 | 95 | 97 | 84 | 54 |
| configuration | 19 | 99 | 89 | 81 | 67 |
| ci/cd | 3 | 100 | 93 | 61 | 68 |
| migration | 2 | 50 | 42 | 80 | 40 |
| post-mortem | 2 | 50 | 100 | 100 | 73 |
| architecture | 22 | 92 | 91 | 82 | 59 |
| debugging | 1 | 100 | 92 | 100 | 72 |
| legacy | 5 | 80 | 80 | 39 | 17 |

## По сложности

| Сложность | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| simple | 47 | 85 | 86 | 80 | 54 |
| hard | 46 | 90 | 91 | 79 | 59 |
| medium | 69 | 94 | 90 | 78 | 57 |
