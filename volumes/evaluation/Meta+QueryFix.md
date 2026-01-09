# RAG Evaluation Report (RAGAS)

**Дата:** 2026-01-08T13:22:10.696623
**RAG Model:** qwen/qwen3-32b
**Evaluator:** RAGAS

## Общая сводка

| Метрика | Значение |
|---------|----------|
| Всего вопросов | 162 |
| Успешно | 162 |
| Ошибок | 0 |
| **Context Recall** | 88.7% |
| **Context Precision** | 81.0% |
| **Faithfulness** | 76.1% |
| **Answer Relevancy** | 56.9% |
| Avg RAG latency | 12.86s |

## По категориям

| Категория | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| iac | 3 | 100 | 83 | 80 | 75 |
| monitoring | 7 | 86 | 67 | 80 | 58 |
| reasoning | 14 | 75 | 69 | 78 | 62 |
| debugging | 1 | 100 | 100 | 50 | 78 |
| migration | 2 | 50 | 50 | 58 | 37 |
| architecture | 22 | 91 | 88 | 75 | 67 |
| troubleshooting | 34 | 90 | 87 | 84 | 52 |
| cloud | 1 | 50 | 100 | 44 | 55 |
| infrastructure | 1 | 100 | 81 | 69 | 53 |
| development | 1 | 80 | 83 | 100 | 74 |
| standards | 2 | 100 | 100 | 80 | 68 |
| post-mortem | 2 | 50 | 70 | 89 | 50 |
| configuration | 19 | 92 | 84 | 78 | 63 |
| cross_document | 1 | 33 | 0 | 70 | 0 |
| general | 4 | 100 | 80 | 70 | 22 |
| api | 6 | 92 | 82 | 80 | 66 |
| operations | 6 | 92 | 87 | 60 | 70 |
| security | 12 | 100 | 80 | 74 | 53 |
| legacy | 5 | 80 | 66 | 32 | 21 |
| ci/cd | 3 | 100 | 75 | 74 | 75 |
| database | 5 | 80 | 69 | 80 | 49 |
| tuning | 11 | 95 | 88 | 81 | 57 |

## По сложности

| Сложность | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| simple | 47 | 89 | 76 | 74 | 55 |
| hard | 46 | 87 | 83 | 75 | 57 |
| medium | 69 | 90 | 83 | 79 | 58 |
