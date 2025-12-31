# Построение Enterprise CI/CD Pipeline для Java-приложений

Это руководство описывает процесс создания надежного, безопасного и масштабируемого конвейера доставки для Java (Spring Boot) приложений с использованием GitLab CI, SonarQube, Nexus и ArgoCD.

## 1. Архитектура конвейера

Наш стандартный Pipeline состоит из следующих этапов:
1. **Build**: Компиляция кода и сборка JAR-файла через Maven/Gradle.
2. **Unit Test**: Запуск модульных тестов с генерацией отчетов о покрытии (Jacoco).
3. **Static Analysis**: Проверка качества кода в SonarQube.
4. **Security Scan**: Поиск уязвимостей в зависимостях (OWASP Dependency Check).
5. **Docker Build**: Создание образа и пуш в Nexus Repository.
6. **Integration Test**: Запуск тестов в изолированной среде (Testcontainers).
7. **Deploy to Dev/Staging**: Обновление манифестов в GitOps репозитории.
8. **Downtime-free Deploy to Prod**: Синхронизация через ArgoCD.

## 2. Описание этапов в .gitlab-ci.yml

### Переменные окружения
```yaml
variables:
  MAVEN_OPTS: "-Dmaven.repo.local=.m2/repository"
  SONAR_USER_HOME: "${CI_PROJECT_DIR}/.sonar"
  DOCKER_HOST: tcp://docker:2375
```

### Этап 1: Сборка и тесты
Используем кеширование для ускорения последующих запусков.

```yaml
build-and-test:
  stage: build
  image: maven:3.9-eclipse-temurin-17
  script:
    - mvn clean package -DskipTests=false
  artifacts:
    paths:
      - target/*.jar
      - target/site/jacoco/
    expire_in: 1 week
  cache:
    paths:
      - .m2/repository
```

### Этап 2: Анализ в SonarQube
Критически важно для соблюдения "Quality Gate".

```yaml
sonarqube-check:
  stage: test
  image: maven:3.9-eclipse-temurin-17
  script:
    - mvn sonar:sonar -Dsonar.projectKey=$CI_PROJECT_NAME -Dsonar.host.url=$SONAR_URL -Dsonar.login=$SONAR_TOKEN
  allow_failure: true
```

## 3. Сборка Docker-образа

Мы используем `Docker-in-Docker` (DinD) для сборки.

```yaml
docker-push:
  stage: release
  image: docker:24.0.5
  services:
    - docker:24.0.5-dind
  script:
    - docker login -u $NEXUS_USER -p $NEXUS_PASSWORD $NEXUS_URL
    - docker build -t $NEXUS_URL/repository/docker-prod/$CI_PROJECT_NAME:$CI_COMMIT_TAG .
    - docker push $NEXUS_URL/repository/docker-prod/$CI_PROJECT_NAME:$CI_COMMIT_TAG
  only:
    - tags
```

## 4. Интеграция с GitOps (ArgoCD)

Вместо прямого вызова `kubectl apply`, пайплайн обновляет версию образа в отдельном репозитории с инфраструктурным кодом.

```yaml
update-manifests:
  stage: deploy
  script:
    - git clone https://git-bot:$GIT_BOT_TOKEN@gitlab.com/infra/deployment-manifests.git
    - cd deployment-manifests
    - sed -i "s|image:.*|image: $NEXUS_URL/...:$CI_COMMIT_TAG|g" charts/$CI_PROJECT_NAME/values.yaml
    - git add .
    - git commit -m "Update $CI_PROJECT_NAME to $CI_COMMIT_TAG"
    - git push
```

## 5. Требования к инфраструктуре

Для корректной работы этого Pipeline необходимо:
- **GitLab Runner**: Минимум 4 CPU и 8GB RAM (помеченный тегом `java-builder`).
- **SonarQube Server**: Версия 9.9+ LTS.
- **Nexus OSS**: Для хранения Maven-артефактов и Docker-образов.

> [!IMPORTANT]
> Все пароли и токены должны храниться в GitLab CI/CD Secrets. Никогда не хардкодьте ключи в YAML файле.

## 6. Рекомендации по Dockerfile
Используйте многоэтапную сборку (multi-stage build) для уменьшения размера образа:

```dockerfile
# Stage 1: Build
FROM maven:3.9-eclipse-temurin-17 AS build
COPY . /app
WORKDIR /app
RUN mvn clean package -DskipTests

# Stage 2: Run
FROM eclipse-temurin:17-jre-alpine
COPY --from=build /app/target/*.jar /app/service.jar
ENTRYPOINT ["java", "-jar", "/app/service.jar"]
```

## 7. Мониторинг после деплоя
После успешного деплоя через ArgoCD, проверьте состояние подов:

```bash
kubectl get pods -n production -l app=$PROJECT_NAME
```

И посмотрите логи на наличие типичных проблем при старте:
- [Java Heap Space errors](java-docker-tuning.md)
- [Ошибки подключения к БД](post-mortem-db-failure.md)

---
*Документ обновлен 2025-12-29. По всем вопросам обращаться к @devops-team.*
