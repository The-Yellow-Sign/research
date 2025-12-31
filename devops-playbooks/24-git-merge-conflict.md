---
title: "Git: Merge Conflict"
type: known_issue
service: git
---

# Git: Automatic merge failed; fix conflicts and then commit the result

## Ошибка

```text
Auto-merging src/app.js
CONFLICT (content): Merge conflict in src/app.js
Auto-merging README.md
CONFLICT (content): Merge conflict in README.md
Automatic merge failed; fix conflicts and then commit the result.
error: could not apply fa39b21... Update main logic
hint: after resolving the conflicts, mark the corrected paths
hint: with 'git add <paths>' or 'git rm <paths>'
hint: and commit the result with 'git commit'
```

## Причина

Git не смог автоматически объединить изменения из двух веток, так как в одном и том же файле были изменены одни и те же строки.

## Решение

1. Откройте конфликтные файлы и вручную выберите нужные изменения (удалите маркеры `<<<<<<<`, `=======`, `>>>>>>>`).
2. Добавьте исправленные файлы в индекс:
   ```bash
   git add src/app.js README.md
   ```
3. Завершите слияние:
   ```bash
   git commit -m "Resolve merge conflicts"
   ```
