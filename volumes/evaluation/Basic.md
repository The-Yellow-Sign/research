# RAG Evaluation Report (RAGAS)

**Дата:** 2026-01-06T14:00:58.574496
**RAG Model:** qwen/qwen3-32b
**Evaluator:** RAGAS

## Общая сводка

| Метрика | Значение |
|---------|----------|
| Всего вопросов | 162 |
| Успешно | 162 |
| Ошибок | 0 |
| **Context Recall** | 84.3% |
| **Context Precision** | 81.8% |
| **Faithfulness** | 75.2% |
| **Answer Relevancy** | 57.5% |
| Avg RAG latency | 15.80s |

## По категориям

| Категория | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| tuning | 11 | 95 | 88 | 74 | 60 |
| troubleshooting | 34 | 88 | 82 | 79 | 57 |
| infrastructure | 1 | 100 | 100 | 67 | 78 |
| cloud | 1 | 50 | 100 | 62 | 65 |
| database | 5 | 80 | 81 | 79 | 47 |
| iac | 3 | 67 | 50 | 67 | 47 |
| operations | 6 | 75 | 76 | 52 | 57 |
| architecture | 22 | 89 | 88 | 81 | 64 |
| general | 4 | 75 | 69 | 38 | 11 |
| monitoring | 7 | 79 | 86 | 72 | 52 |
| api | 6 | 58 | 75 | 77 | 56 |
| migration | 2 | 50 | 37 | 94 | 40 |
| standards | 2 | 100 | 100 | 75 | 63 |
| configuration | 19 | 91 | 84 | 84 | 71 |
| ci/cd | 3 | 100 | 98 | 70 | 62 |
| post-mortem | 2 | 50 | 100 | 100 | 68 |
| legacy | 5 | 80 | 66 | 47 | 8 |
| development | 1 | 80 | 83 | 83 | 74 |
| cross_document | 1 | 67 | 0 | 27 | 70 |
| reasoning | 14 | 68 | 80 | 73 | 56 |
| security | 12 | 100 | 86 | 81 | 65 |
| debugging | 1 | 100 | 100 | 89 | 73 |

## По сложности

| Сложность | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| medium | 69 | 88 | 82 | 77 | 62 |
| hard | 46 | 83 | 88 | 75 | 60 |
| simple | 47 | 80 | 75 | 72 | 48 |
