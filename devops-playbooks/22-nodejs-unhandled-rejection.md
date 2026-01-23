---
title: "Node.js: UnhandledPromiseRejectionWarning"
type: known_issue
service: nodejs
---

# Node.js: UnhandledPromiseRejectionWarning

## Ошибка

```text
(node:18421) UnhandledPromiseRejectionWarning: Error: connect ECONNREFUSED 127.0.0.1:5432
    at TCPConnectWrap.afterConnect [as oncomplete] (net.js:1146:16)
(node:18421) UnhandledPromiseRejectionWarning: Unhandled promise rejection. This error originated either by throwing inside of an async function without a catch block, or by rejecting a promise which was not handled with .catch(). To terminate the node process on unhandled promise rejection, use the CLI flag `--unhandled-rejections=strict` (see https://nodejs.org/api/cli.html#cli_unhandled_rejections_mode). (rejection id: 1)
(node:18421) [DEP0018] DeprecationWarning: Unhandled promise rejections are deprecated. In the future, promise rejections that are not handled will terminate the Node.js process with a non-zero exit code.
```

## Причина

В асинхронном коде (Promise или async/await) произошла ошибка, которая не была перехвачена блоком `.catch()` или `try/catch`. В данном примере — отказ соединения с базой данных.

## Решение

Оберните асинхронный вызов в блок `try/catch`.

```javascript
try {
  await database.connect();
} catch (error) {
  console.error('Failed to connect to DB:', error);
  process.exit(1);
}
```
