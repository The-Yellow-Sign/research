# RAG Evaluation Report (RAGAS)

**Дата:** 2026-01-07T21:12:23.730025
**RAG Model:** qwen/qwen3-32b
**Evaluator:** RAGAS

## Общая сводка

| Метрика | Значение |
|---------|----------|
| Всего вопросов | 162 |
| Успешно | 162 |
| Ошибок | 0 |
| **Context Recall** | 87.9% |
| **Context Precision** | 80.5% |
| **Faithfulness** | 77.3% |
| **Answer Relevancy** | 54.8% |
| Avg RAG latency | 16.32s |

## По категориям

| Категория | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| monitoring | 7 | 79 | 79 | 92 | 57 |
| migration | 2 | 50 | 37 | 90 | 35 |
| infrastructure | 1 | 100 | 83 | 83 | 52 |
| tuning | 11 | 100 | 88 | 81 | 52 |
| database | 5 | 80 | 69 | 88 | 38 |
| troubleshooting | 34 | 94 | 86 | 86 | 50 |
| debugging | 1 | 100 | 100 | 100 | 79 |
| cloud | 1 | 100 | 70 | 67 | 52 |
| configuration | 19 | 88 | 82 | 78 | 62 |
| post-mortem | 2 | 50 | 87 | 100 | 86 |
| architecture | 22 | 89 | 89 | 76 | 66 |
| iac | 3 | 100 | 83 | 80 | 72 |
| general | 4 | 100 | 66 | 64 | 9 |
| ci/cd | 3 | 100 | 94 | 40 | 67 |
| cross_document | 1 | 67 | 0 | 83 | 83 |
| api | 6 | 75 | 74 | 78 | 44 |
| development | 1 | 80 | 83 | 90 | 72 |
| standards | 2 | 100 | 100 | 90 | 60 |
| security | 12 | 92 | 77 | 74 | 57 |
| operations | 6 | 92 | 70 | 53 | 70 |
| legacy | 5 | 80 | 60 | 38 | 8 |
| reasoning | 14 | 71 | 74 | 73 | 59 |

## По сложности

| Сложность | N | Recall | Precision | Faith. | Relevancy |
|-----------|---|--------|-----------|--------|-----------|
| simple | 47 | 86 | 76 | 72 | 50 |
| hard | 46 | 86 | 84 | 79 | 60 |
| medium | 69 | 91 | 81 | 79 | 54 |
