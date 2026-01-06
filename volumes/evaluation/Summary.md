# RAG Evaluation Report (RAGAS)

**Дата:** 2026-01-06T12:00:25.943483
**RAG Model:** qwen/qwen3-32b
**Evaluator:** RAGAS

## Общая сводка

| Метрика | Значение |
|---------|----------|
| Всего вопросов | 162 |
| Успешно | 162 |
| Ошибок | 0 |
| **Context Recall** | 88.8% |
| **Context Precision** | 90.3% |
| **Faithfulness** | 72.8% |
| **Answer Relevancy** | 55.1% |
| Avg RAG latency | 36.09s |

## По категориям

| Категория | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| general | 4 | 62 | 75 | 0 | 0 |
| api | 6 | 58 | 83 | 78 | 48 |
| debugging | 1 | 100 | 92 | 100 | 72 |
| legacy | 5 | 80 | 80 | 15 | 4 |
| infrastructure | 1 | 100 | 100 | 80 | 57 |
| tuning | 11 | 95 | 100 | 75 | 55 |
| migration | 2 | 50 | 46 | 67 | 32 |
| cloud | 1 | 50 | 100 | 86 | 53 |
| post-mortem | 2 | 50 | 100 | 100 | 77 |
| architecture | 22 | 92 | 93 | 73 | 69 |
| standards | 2 | 100 | 100 | 50 | 33 |
| database | 5 | 100 | 97 | 79 | 68 |
| iac | 3 | 100 | 100 | 95 | 69 |
| security | 12 | 96 | 91 | 80 | 65 |
| monitoring | 7 | 93 | 100 | 68 | 53 |
| development | 1 | 80 | 100 | 100 | 71 |
| configuration | 19 | 99 | 87 | 83 | 63 |
| cross_document | 1 | 67 | 0 | 100 | 77 |
| troubleshooting | 34 | 93 | 94 | 82 | 58 |
| reasoning | 14 | 71 | 83 | 62 | 36 |
| operations | 6 | 92 | 85 | 66 | 55 |
| ci/cd | 3 | 100 | 100 | 60 | 58 |

## По сложности

| Сложность | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| simple | 47 | 84 | 88 | 73 | 53 |
| hard | 46 | 88 | 91 | 75 | 57 |
| medium | 69 | 92 | 91 | 72 | 55 |
