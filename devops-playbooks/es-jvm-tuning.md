# Тюнинг JVM для Elasticsearch 7.x/8.x (Short Guide)

Для оптимальной работы Elasticsearch необходимо правильно настроить параметры Java Virtual Machine.

### Настройки Heap
- **Размер**: Устанавливайте `Xms` и `Xmx` равными.
- **Лимит**: Не более 50% физической RAM и не более 31GB.

```text
# jvm.options
-Xms4g
-Xmx4g
```

### Сборщик мусора (GC)
Для современных версий ES рекомендуется использовать G1GC.

```text
-XX:+UseG1GC
-XX:G1ReservePercent=25
-XX:InitiatingHeapOccupancyPercent=30
```

> [!TIP]
> Включайте Garbage Collection Logging для отладки пауз (STW).

Для подробного тюнинга см. [основной гайд по ES](es-tuning.md).
