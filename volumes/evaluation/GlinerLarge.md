# RAG Evaluation Report (RAGAS)

**Дата:** 2026-01-09T17:02:20.856136
**RAG Model:** qwen/qwen3-32b
**Evaluator:** RAGAS

## Общая сводка

| Метрика | Значение |
|---------|----------|
| Всего вопросов | 162 |
| Успешно | 162 |
| Ошибок | 0 |
| **Context Recall** | 89.7% |
| **Context Precision** | 88.0% |
| **Faithfulness** | 78.3% |
| **Answer Relevancy** | 59.1% |
| Avg RAG latency | 22.97s |

## По категориям

| Категория | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| debugging | 1 | 0 | 64 | 100 | 75 |
| architecture | 22 | 89 | 83 | 78 | 73 |
| iac | 3 | 100 | 100 | 70 | 73 |
| migration | 2 | 100 | 67 | 93 | 64 |
| security | 12 | 100 | 100 | 89 | 62 |
| ci/cd | 3 | 100 | 94 | 71 | 69 |
| development | 1 | 80 | 83 | 100 | 62 |
| tuning | 11 | 86 | 93 | 76 | 59 |
| monitoring | 7 | 100 | 96 | 81 | 46 |
| operations | 6 | 92 | 84 | 77 | 52 |
| cloud | 1 | 50 | 83 | 100 | 66 |
| api | 6 | 75 | 83 | 84 | 66 |
| general | 4 | 100 | 99 | 62 | 14 |
| database | 5 | 100 | 99 | 86 | 63 |
| configuration | 19 | 95 | 87 | 79 | 67 |
| legacy | 5 | 80 | 74 | 55 | 26 |
| troubleshooting | 34 | 93 | 91 | 82 | 54 |
| cross_document | 1 | 67 | 0 | 55 | 61 |
| post-mortem | 2 | 50 | 100 | 100 | 82 |
| infrastructure | 1 | 100 | 100 | 67 | 41 |
| reasoning | 14 | 75 | 77 | 71 | 56 |
| standards | 2 | 100 | 100 | 40 | 64 |

## По сложности

| Сложность | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| hard | 46 | 87 | 86 | 77 | 59 |
| medium | 69 | 91 | 90 | 78 | 60 |
| simple | 47 | 91 | 87 | 81 | 58 |
