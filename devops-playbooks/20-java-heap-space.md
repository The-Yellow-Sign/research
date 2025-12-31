---
title: "Java: Java Heap Space Error"
type: known_issue
service: java
---

# Java: Java Heap Space Error

## Ошибка

```text
Exception in thread "main" java.lang.OutOfMemoryError: Java heap space
    at java.base/java.util.Arrays.copyOf(Arrays.java:3720)
    at java.base/java.util.Arrays.copyOf(Arrays.java:3689)
    at java.base/java.util.ArrayList.grow(ArrayList.java:238)
    at java.base/java.util.ArrayList.grow(ArrayList.java:243)
    at java.base/java.util.ArrayList.add(ArrayList.java:486)
    at java.base/java.util.ArrayList.add(ArrayList.java:499)
    at com.example.data.BigDataLoader.loadAllData(BigDataLoader.java:145)
    at com.example.data.BigDataLoader.process(BigDataLoader.java:89)
    at com.example.Main.main(Main.java:42)
    at java.base/jdk.internal.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
    at java.base/jdk.internal.reflect.NativeMethodAccessorImpl.invoke(NativeMethodAccessorImpl.java:62)
    at java.base/jdk.internal.reflect.DelegatingMethodAccessorImpl.invoke(DelegatingMethodAccessorImpl.java:43)
    at java.base/java.lang.reflect.Method.invoke(Method.java:566)
    at org.springframework.boot.loader.MainMethodRunner.run(MainMethodRunner.java:49)
    at org.springframework.boot.loader.Launcher.launch(Launcher.java:108)
    at org.springframework.boot.loader.JarLauncher.main(JarLauncher.java:88)
```

## Причина

Приложению не хватает выделенной оперативной памяти (Heap) для размещения всех объектов. Это часто происходит при загрузке больших файлов в память или утечках памяти (memory leaks).

## Решение

Увеличьте максимальный размер кучи (Heap Size) с помощью флага `-Xmx` при запуске.

```bash
java -Xms512m -Xmx4g -jar application.jar
```
*Где `-Xmx4g` устанавливает лимит в 4 гигабайта.*
