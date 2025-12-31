## Список изменений (Release Notes) — CI/CD Pipeline v3.2.0

В этой версии мы сфокусировались на ускорении сборки Docker-образов и улучшении интеграции с ArgoCD для GitOps-процессов.

### Что нового
- **GitLab CI**: Добавлена поддержка `interruptible: true` для всех job, что позволяет экономить Runner-ы при пуше в ту же ветку.
- **ArgoCD**: Теперь используется автоматический Image Updater. Вам больше не нужно менять тег в манифестах вручную.
- **Security**: В пайплайн встроен автоматический сканнер уязвимостей (Trivy).

### Улучшения
- Уменьшен размер базового образа для Python с 800MB до 120MB (Alpine).
- Оптимизировано кеширование `node_modules`.

### Исправления
- Исправлена ошибка, когда Helm-чарт не мог развернуться в пустой namespace.
- Пофиксен баг с дублированием алертов при деплое.

### Как обновиться?
Просто обновите `include` в вашем `.gitlab-ci.yml`:

```yaml
include:
  - project: 'ops/ci-templates'
    ref: 'v3.2.0'
    file: 'python.gitlab-ci.yml'
```

### Ссылки
- [Полный лог изменений в GitLab](https://gitlab.example.com/ops/ci-templates/-/tags/v3.2.0)
- [Инструкция по настройке ArgoCD](gcp-terraform-setup.md)

![Пример нового пайплайна](path/to/pipeline_v3.png)
