# RAG Evaluation Report (RAGAS)

**Дата:** 2026-01-08T21:58:55.070948
**RAG Model:** qwen/qwen3-32b
**Evaluator:** RAGAS

## Общая сводка

| Метрика | Значение |
|---------|----------|
| Всего вопросов | 162 |
| Успешно | 162 |
| Ошибок | 0 |
| **Context Recall** | 91.1% |
| **Context Precision** | 88.0% |
| **Faithfulness** | 76.8% |
| **Answer Relevancy** | 56.3% |
| Avg RAG latency | 22.74s |

## По категориям

| Категория | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| debugging | 1 | 100 | 100 | 80 | 78 |
| reasoning | 14 | 71 | 72 | 72 | 56 |
| ci/cd | 3 | 100 | 97 | 74 | 68 |
| monitoring | 7 | 100 | 96 | 77 | 62 |
| api | 6 | 75 | 92 | 78 | 56 |
| operations | 6 | 92 | 96 | 70 | 68 |
| infrastructure | 1 | 100 | 100 | 88 | 53 |
| security | 12 | 100 | 97 | 85 | 53 |
| standards | 2 | 100 | 100 | 50 | 65 |
| cloud | 1 | 50 | 100 | 50 | 55 |
| post-mortem | 2 | 50 | 87 | 85 | 31 |
| database | 5 | 100 | 97 | 90 | 68 |
| iac | 3 | 100 | 100 | 73 | 69 |
| legacy | 5 | 80 | 67 | 57 | 0 |
| development | 1 | 80 | 100 | 100 | 62 |
| tuning | 11 | 100 | 100 | 75 | 51 |
| cross_document | 1 | 100 | 0 | 73 | 0 |
| troubleshooting | 34 | 93 | 91 | 83 | 54 |
| general | 4 | 100 | 98 | 89 | 21 |
| migration | 2 | 100 | 100 | 88 | 70 |
| architecture | 22 | 89 | 91 | 70 | 68 |
| configuration | 19 | 95 | 71 | 74 | 63 |

## По сложности

| Сложность | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| hard | 46 | 89 | 83 | 74 | 53 |
| medium | 69 | 93 | 91 | 79 | 60 |
| simple | 47 | 91 | 89 | 76 | 54 |
