# Guía de estudio — CreditTrace

Esta guía está en español y explica el proyecto para que puedas estudiarlo a fondo y
sustentarlo en una entrevista. El código y la documentación técnica están en inglés;
aquí se explica el *por qué* y el *cómo*, paso a paso.

## Orden sugerido de lectura

1. [El modelo de riesgo](01-modelo-de-riesgo.md) — cómo se genera el dato sintético,
   qué aprende XGBoost y qué significan las métricas (ROC-AUC, KS, Brier).
2. [Explicabilidad con SHAP](02-explicabilidad-shap.md) — por qué una decisión de
   crédito debe explicarse y cómo se traduce el modelo en razones legibles.
3. [Anclaje en blockchain](03-anclaje-en-blockchain.md) — qué es un digest, por qué se
   ancla solo el digest y no los datos, y cómo se detecta una alteración.
4. [Arquitectura y diseño](04-arquitectura-y-diseno.md) — las capas, la inversión de
   dependencias del cliente de cadena y por qué todo se puede probar sin blockchain.
5. [Preguntas de entrevista](05-preguntas-de-entrevista.md) — preguntas típicas con
   respuestas, de junior a senior.

## Cómo correrlo mientras estudias

```bash
make install    # instala el paquete y dependencias de desarrollo
make compile    # compila el contrato Solidity (Node + solc-js)
make demo       # ciclo completo: entrena, despliega, puntúa, ancla, verifica, altera
make test       # corre las 27 pruebas
```

`make demo` es la mejor forma de ver el sistema completo funcionando en menos de un
minuto, sin necesidad de Docker ni de una cadena externa.
