# RAG Evaluation Report (RAGAS)

**Дата:** 2026-01-05T23:54:02.542433
**RAG Model:** qwen/qwen3-32b
**Evaluator:** RAGAS

## Общая сводка

| Метрика | Значение |
|---------|----------|
| Всего вопросов | 162 |
| Успешно | 162 |
| Ошибок | 0 |
| **Context Recall** | 85.4% |
| **Context Precision** | 81.5% |
| **Faithfulness** | 73.9% |
| **Answer Relevancy** | 56.2% |
| Avg RAG latency | 13.13s |

## По категориям

| Категория | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| architecture | 22 | 89 | 86 | 82 | 59 |
| tuning | 11 | 95 | 87 | 83 | 60 |
| general | 4 | 75 | 63 | 55 | 35 |
| iac | 3 | 67 | 50 | 57 | 44 |
| infrastructure | 1 | 100 | 100 | 67 | 77 |
| operations | 6 | 75 | 76 | 60 | 53 |
| monitoring | 7 | 79 | 86 | 75 | 52 |
| database | 5 | 100 | 91 | 85 | 66 |
| migration | 2 | 50 | 46 | 42 | 0 |
| api | 6 | 58 | 75 | 49 | 38 |
| troubleshooting | 34 | 90 | 81 | 77 | 58 |
| cloud | 1 | 50 | 100 | 53 | 69 |
| post-mortem | 2 | 50 | 79 | 100 | 73 |
| ci/cd | 3 | 100 | 98 | 66 | 45 |
| security | 12 | 100 | 87 | 73 | 59 |
| reasoning | 14 | 79 | 81 | 67 | 50 |
| cross_document | 1 | 33 | 0 | 87 | 87 |
| legacy | 5 | 80 | 66 | 68 | 33 |
| configuration | 19 | 92 | 84 | 79 | 69 |
| development | 1 | 80 | 83 | 67 | 68 |
| debugging | 1 | 0 | 100 | 100 | 73 |
| standards | 2 | 100 | 100 | 63 | 65 |

## По сложности

| Сложность | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| medium | 69 | 89 | 82 | 79 | 58 |
| hard | 46 | 85 | 87 | 75 | 61 |
| simple | 47 | 80 | 75 | 66 | 49 |
