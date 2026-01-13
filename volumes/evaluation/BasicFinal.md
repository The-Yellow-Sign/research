# RAG Evaluation Report (RAGAS)

**Дата:** 2026-01-11T17:13:21.689958
**RAG Model:** qwen/qwen3-32b
**Evaluator:** RAGAS

## Общая сводка

| Метрика | Значение |
|---------|----------|
| Всего вопросов | 162 |
| Успешно | 162 |
| Ошибок | 0 |
| **Context Recall** | 95.3% |
| **Context Precision** | 81.6% |
| **Faithfulness** | 86.2% |
| **Answer Relevancy** | 0.0% |
| Avg RAG latency | 14.19s |

## По категориям

| Категория | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| debugging | 1 | 100 | 78 | 62 | 0 |
| troubleshooting | 34 | 95 | 84 | 91 | 0 |
| development | 1 | 80 | 100 | 100 | 0 |
| tuning | 11 | 100 | 85 | 94 | 0 |
| cross_document | 1 | 67 | 33 | 81 | 0 |
| api | 6 | 92 | 85 | 77 | 0 |
| architecture | 22 | 93 | 84 | 88 | 0 |
| legacy | 5 | 80 | 77 | 59 | 0 |
| reasoning | 14 | 82 | 72 | 83 | 0 |
| migration | 2 | 100 | 39 | 100 | 0 |
| monitoring | 7 | 100 | 71 | 96 | 0 |
| infrastructure | 1 | 100 | 80 | 91 | 0 |
| cloud | 1 | 100 | 60 | 60 | 0 |
| post-mortem | 2 | 100 | 70 | 92 | 0 |
| standards | 2 | 100 | 100 | 73 | 0 |
| operations | 6 | 100 | 75 | 86 | 0 |
| general | 4 | 100 | 86 | 83 | 0 |
| security | 12 | 100 | 82 | 84 | 0 |
| ci/cd | 3 | 100 | 80 | 69 | 0 |
| iac | 3 | 100 | 89 | 91 | 0 |
| configuration | 19 | 100 | 87 | 85 | 0 |
| database | 5 | 100 | 90 | 93 | 0 |

## По сложности

| Сложность | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| medium | 69 | 95 | 82 | 86 | 0 |
| simple | 47 | 95 | 80 | 83 | 0 |
| hard | 46 | 96 | 82 | 90 | 0 |
