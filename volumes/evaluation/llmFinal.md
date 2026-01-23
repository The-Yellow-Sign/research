# RAG Evaluation Report (RAGAS)

**Дата:** 2026-01-11T15:01:45.600460
**RAG Model:** qwen/qwen3-32b
**Evaluator:** RAGAS

## Общая сводка

| Метрика | Значение |
|---------|----------|
| Всего вопросов | 162 |
| Успешно | 162 |
| Ошибок | 0 |
| **Context Recall** | 92.0% |
| **Context Precision** | 89.5% |
| **Faithfulness** | 83.6% |
| **Answer Relevancy** | 0.0% |
| Avg RAG latency | 25.44s |

## По категориям

| Категория | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| general | 4 | 100 | 100 | 91 | 0 |
| iac | 3 | 100 | 100 | 76 | 0 |
| troubleshooting | 34 | 93 | 91 | 89 | 0 |
| development | 1 | 80 | 100 | 91 | 0 |
| api | 6 | 75 | 76 | 87 | 0 |
| configuration | 19 | 99 | 89 | 81 | 0 |
| cloud | 1 | 100 | 75 | 67 | 0 |
| operations | 6 | 92 | 90 | 100 | 0 |
| standards | 2 | 100 | 100 | 35 | 0 |
| architecture | 22 | 91 | 89 | 80 | 0 |
| legacy | 5 | 80 | 74 | 60 | 0 |
| security | 12 | 100 | 96 | 83 | 0 |
| infrastructure | 1 | 100 | 87 | 93 | 0 |
| ci/cd | 3 | 100 | 100 | 66 | 0 |
| monitoring | 7 | 95 | 100 | 93 | 0 |
| post-mortem | 2 | 50 | 100 | 92 | 0 |
| reasoning | 14 | 75 | 77 | 82 | 0 |
| migration | 2 | 100 | 67 | 73 | 0 |
| cross_document | 1 | 67 | 25 | 50 | 0 |
| database | 5 | 100 | 93 | 95 | 0 |
| debugging | 1 | 100 | 100 | 100 | 0 |
| tuning | 11 | 100 | 98 | 83 | 0 |

## По сложности

| Сложность | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| hard | 46 | 90 | 89 | 83 | 0 |
| simple | 47 | 89 | 89 | 84 | 0 |
| medium | 69 | 95 | 90 | 84 | 0 |
