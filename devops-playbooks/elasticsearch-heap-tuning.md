---
title: Performance Tuning: Elasticsearch Java Heap Settings
---

# Optimizing Elasticsearch Heap Memory

If you notice frequent GC (Garbage Collection) pauses and "Circuit Breaker" errors, you likely have misconfigured heap settings.

## Recommendations

### 50% Rule
Never set the heap size to more than 50% of your total RAM. The OS needs the other 50% for file system caching (Lucene).

### 32GB Barrier
Do not go above ~31GB even if you have 256GB RAM. This is due to Java's Compressed Oops pointer limits.

## How to Apply
Edit your `jvm.options` or set `ES_JAVA_OPTS` environment variable:

```bash
# Set Xms and Xmx to the same value
-Xms16g
-Xmx16g
```

## Monitoring
Watch the following metric in `_nodes/stats`:
- `jvm.mem.heap_used_percent`
- `jvm.gc.collectors.old.collection_time_in_millis`

> [!TIP]
> Use G1GC if you are on latest version of OpenJDK 17+.
