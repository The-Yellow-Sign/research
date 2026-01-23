# Документация API сервиса авторизации (Go)

Микросервис `auth-svc` предназначен для управления сессиями и выдачи JWT токенов.

## Эндпоинты

| Method | Path | Description | Result |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/login` | Аутентификация пользователя | `JWT Token` |
| `POST` | `/api/refresh`| Обновление токена | `New JWT` |
| `GET`  | `/api/me` | Профиль текущего юзера | `User Info` |

## Примеры

### Запрос логина
```json
{
  "username": "admin",
  "password": "password123"
}
```

### Ответ (Go struct)
```go
type AuthResponse struct {
    Token     string `json:"token"`
    ExpiresIn int64  `json:"expires_in"`
}
```

### Ошибки
- `401 Unauthorized`: Неправильный логин/пароль.
- `429 Too Many Requests`: Сработал Rate Limiter.
