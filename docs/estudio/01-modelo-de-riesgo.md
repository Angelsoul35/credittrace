# 1. El modelo de riesgo

## El problema

Dada una solicitud de microcrédito, queremos estimar la **probabilidad de
incumplimiento** (probability of default, PD): la probabilidad de que el solicitante no
pague. Con esa probabilidad, una política de negocio decide aprobar, enviar a revisión
o rechazar.

## El dato es sintético y lo controlamos nosotros

En `app/ml/data.py` generamos solicitantes falsos con un proceso conocido. Esto es
intencional: como conocemos las "reglas reales" que determinan el riesgo, podemos
verificar después que el modelo (y SHAP) las recuperan.

El corazón del generador es un **modelo logístico latente**. Para cada solicitante
calculamos un log-odds `z`:

```
z = -2.6
    + 2.4 * debt_to_income            # más deuda sobre ingreso => más riesgo
    + 0.85 * num_late_payments_12m    # moras recientes => más riesgo
    + 0.18 * num_existing_loans
    - 0.05 * employment_length_years  # antigüedad laboral => menos riesgo
    - 0.45 * has_collateral           # garantía => menos riesgo
    - 0.012 * (age - 18)
    + efecto_region + efecto_proposito
    + ruido gaussiano
```

Luego `p = sigmoide(z)` y el incumplimiento se sortea con una Bernoulli(`p`). El ruido
evita que el problema sea trivial; sin él, el modelo tendría precisión perfecta y no
aprenderíamos nada.

> **Concepto — log-odds y sigmoide.** La función sigmoide `1/(1+e^-z)` convierte un
> número real `z` (de -∞ a +∞) en una probabilidad (0 a 1). Trabajar en log-odds hace
> que los efectos se sumen linealmente, que es como razonan la regresión logística y,
> aproximadamente, los árboles de gradient boosting.

## El modelo: XGBoost dentro de un Pipeline

En `app/ml/model.py`, el modelo es un `Pipeline` de scikit-learn con dos pasos:

1. **`ColumnTransformer`** — deja pasar las variables numéricas y aplica
   *one-hot encoding* a las categóricas (`region`, `loan_purpose`). One-hot convierte
   "region=caribe" en columnas binarias `region_andina=0, region_caribe=1, ...`.
2. **`XGBClassifier`** — un clasificador de *gradient boosting* sobre árboles.

> **Concepto — gradient boosting.** Se entrenan muchos árboles pequeños en secuencia;
> cada árbol corrige el error del conjunto anterior. XGBoost es una implementación
> eficiente y regularizada. Parámetros clave aquí: `n_estimators` (número de árboles),
> `max_depth` (profundidad, controla complejidad), `learning_rate` (cuánto aporta cada
> árbol) y `reg_lambda` (regularización L2).

## Versionado por contenido

Cada modelo entrenado recibe una versión `m_<hash>` calculada a partir de los
hiperparámetros y una huella del dataset. Así, cada decisión puede nombrar exactamente
el modelo que la produjo, y dos entrenamientos con el mismo dato y parámetros dan la
misma versión (reproducibilidad).

## Las métricas

Al entrenar reportamos tres métricas sobre un conjunto de prueba separado
(`train_test_split` estratificado):

| Métrica | Qué mide | Interpretación |
|---|---|---|
| **ROC-AUC** | Capacidad de ordenar buenos vs. malos pagadores | 0.5 = azar; 1.0 = perfecto. ~0.8 es bueno en crédito. |
| **KS** (Kolmogorov-Smirnov) | Máxima separación entre las distribuciones de buenos y malos | Más alto = mejor separación. Muy usado en *scoring* de crédito. |
| **Brier** | Error cuadrático de la probabilidad | Más bajo = mejor *calibración* (que un 0.2 signifique de verdad 20%). |

> **Por qué importa la calibración.** En crédito no basta con *ordenar* el riesgo:
> la probabilidad se usa para fijar umbrales de política y precios. Si el modelo dice
> 20% debe fallar ~20% de las veces. Por eso reportamos Brier, no solo AUC.

## Para experimentar

```bash
python -m app.ml.train --rows 50000        # más datos
# edita _DEFAULT_PARAMS en app/ml/model.py para probar otros hiperparámetros
```

Observa cómo cambian ROC-AUC/KS/Brier y si las razones SHAP siguen coincidiendo con los
pesos "reales" del generador.
