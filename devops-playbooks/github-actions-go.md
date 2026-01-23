---
service: github-actions
title: "Автоматизация CI/CD для Go-проектов через GitHub Actions"
tags: [ci, github, go]
severity: low
---

# Настройка GitHub Actions для Go

В данной инструкции описано, как настроить автоматическую проверку кода и сборку Docker-образа при каждом Pull Request.

## Шаг 1: Создание Workflow
Создайте файл `.github/workflows/main.yml` в корне вашего репозитория.

```yaml
name: Go CI/CD

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Go
      uses: actions/setup-go@v5
      with:
        go-version: '1.21'
    - name: Build
      run: go build -v ./...
    - name: Test
      run: go test -v ./...
```

## Шаг 2: Сборка и отправка в Registry
Добавьте шаг для сборки Docker-образа.

```yaml
  release:
    needs: test
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Login to DockerHub
      uses: docker/login-action@v3
      with:
        username: ${{ secrets.DOCKERHUB_USERNAME }}
        password: ${{ secrets.DOCKERHUB_TOKEN }}
    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        push: true
        tags: user/app:latest
```

> [!NOTE]
> Не забудьте добавить секреты `DOCKERHUB_USERNAME` и `DOCKERHUB_TOKEN` в настройках репозитория.

### Результат
После настройки каждое изменение будет проходить через проверку тестами.

![Статус GitHub Actions](path/to/github_actions_status.png)
