# Миграция с Jenkins Pipelines на GitLab CI

## Почему мы уходим от Jenkins?
- **Infrastructure as Code**: В GitLab пайплайн описывается в репозитории (`.gitlab-ci.yml`), а не в GUI или сложных Jenkinsfile.
- **Масштабируемость**: GitLab Runners проще масштабировать в Kubernetes.
- **Интеграция**: Нативная связь с Merge Requests и Container Registry.

## Сравнение синтаксиса

| Jenkins (Groovy) | GitLab CI (YAML) |
| :--- | :--- |
| `stage('Build') { ... }` | `build-job: stage: build` |
| `agent any` | `image: docker:latest` |
| `when { branch 'master' }` | `only: [master]` |

## Этапы переноса

### 1. Подготовка Runners
Убедитесь, что в вашем проекте зарегистрирован хотя бы один Runner.

```bash
# Проверка доступных раннеров через CLI
gitlab-runner list
```

### 2. Создание файла `.gitlab-ci.yml`
Пример базового пайплайна для Docker-сборки:

```yaml
stages:
  - build
  - test
  - deploy

docker-build:
  stage: build
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

unit-tests:
  stage: test
  script:
    - make test
```

### 3. Секреты (Secrets Management)
Перенесите все `Credentials` из Jenkins в `Settings -> CI/CD -> Variables`.

> [!IMPORTANT]
> Отметьте переменные как `Masked`, чтобы они не отображались в логах сборки.

## Особенности (Edge cases)
- **Shared Libraries**: Вместо них используйте механизм `include` в GitLab.
- **Плагины**: Большинство плагинов Jenkins заменяются стандартными CLI утилитами в Docker-контейнерах.

---
*Старые скрипты деплоя доступны в архиве `legacy-deploy-scripts.zip`*
