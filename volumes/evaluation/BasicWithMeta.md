# RAG Evaluation Report (RAGAS)

**Дата:** 2026-01-07T16:26:41.994852
**RAG Model:** qwen/qwen3-32b
**Evaluator:** RAGAS

## Общая сводка

| Метрика | Значение |
|---------|----------|
| Всего вопросов | 162 |
| Успешно | 162 |
| Ошибок | 0 |
| **Context Recall** | 85.0% |
| **Context Precision** | 82.1% |
| **Faithfulness** | 76.8% |
| **Answer Relevancy** | 59.5% |
| Avg RAG latency | 18.28s |

## По категориям

| Категория | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| operations | 6 | 75 | 64 | 43 | 58 |
| ci/cd | 3 | 100 | 83 | 73 | 69 |
| tuning | 11 | 95 | 89 | 80 | 60 |
| troubleshooting | 34 | 89 | 84 | 80 | 57 |
| reasoning | 14 | 68 | 82 | 67 | 59 |
| infrastructure | 1 | 100 | 100 | 86 | 56 |
| debugging | 1 | 0 | 100 | 100 | 62 |
| cloud | 1 | 50 | 100 | 71 | 57 |
| iac | 3 | 100 | 83 | 81 | 68 |
| post-mortem | 2 | 50 | 87 | 100 | 86 |
| security | 12 | 100 | 91 | 85 | 65 |
| legacy | 5 | 80 | 70 | 43 | 26 |
| database | 5 | 80 | 67 | 68 | 53 |
| migration | 2 | 50 | 46 | 82 | 32 |
| standards | 2 | 100 | 100 | 86 | 62 |
| monitoring | 7 | 100 | 85 | 96 | 67 |
| architecture | 22 | 89 | 83 | 78 | 72 |
| cross_document | 1 | 100 | 0 | 92 | 74 |
| configuration | 19 | 87 | 86 | 81 | 68 |
| general | 4 | 75 | 75 | 47 | 11 |
| development | 1 | 80 | 83 | 100 | 74 |
| api | 6 | 58 | 74 | 84 | 35 |

## По сложности

| Сложность | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| hard | 46 | 82 | 87 | 77 | 60 |
| simple | 47 | 83 | 76 | 73 | 58 |
| medium | 69 | 88 | 83 | 79 | 60 |
