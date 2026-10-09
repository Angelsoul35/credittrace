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

## Validación con datos reales: German Credit (UCI)

El dato sintético sirve para una cosa concreta: como conocemos los pesos "reales", podemos
verificar que SHAP los recupera. Pero no prueba que el enfoque funcione con **gente real**.
Para eso usamos un dataset **real y público**: el *Statlog German Credit* de la UCI — 1.000
solicitantes, 20 atributos, etiquetados como buen (700) o mal (300) crédito. Está vendoreado
en `datasets/german_credit.csv` con su procedencia, y se corre con `python -m app.ml.benchmark`.

### Ni underfit ni overfit: la curva de ajuste

El objetivo no es "la métrica más alta", es un modelo **bien ajustado**: fuerte en datos no
vistos (no underfit) **y** con el puntaje de entrenamiento cercano al de prueba (no overfit).
Esta es la curva real sobre German Credit (CV = validación cruzada 5-fold; `gap` = train − test):

| Config XGBoost | CV ROC-AUC | train | test | gap | veredicto |
|---|---|---|---|---|---|
| depth 6, 400 árboles, sin regular. | 0.771 | 1.000 | 0.798 | **0.202** | **overfit**: memoriza el train |
| depth 3, 300, reg_λ=2 | 0.786 | 0.941 | 0.795 | 0.147 | aún overfit |
| **depth 2, 200, reg_λ=5** | **0.786** | 0.856 | 0.784 | **0.072** | ✅ **bien ajustado** |
| depth 2, 150, reg_λ=8 | 0.764 | 0.819 | 0.765 | 0.054 | **underfit**: la CV empieza a caer |

La lección, que vale para la entrevista: **más capacidad no es mejor.** El modelo más profundo
tiene `train = 1.000` (se aprende el dataset de memoria) pero su CV es **más baja** (0.771):
memorizar *empeora* la generalización. El modelo regularizado (depth 2) llega al **techo real
del dato** (~0.78) con la brecha train-test más cerrada. No es recortar capacidad: es elegir el
punto donde el modelo generaliza.

> **¿Por qué el techo es ~0.78 y no 1.0?** Porque el riesgo crediticio real es intrínsecamente
> ruidoso: dos personas con el mismo perfil pueden pagar o no por razones que el dato no captura
> (un despido, una emergencia). La literatura de German Credit reporta AUC ~0.78–0.80. Un modelo
> que aquí marque ~1.0 tendría una **fuga** (p. ej. incluir el target disfrazado), no un acierto.

### La regresión logística empata al XGBoost

Sobre 1.000 filas, la regresión logística da CV AUC **0.786**, igual que el XGBoost. En datos
tabulares pequeños, un modelo lineal bien regularizado suele igualar a los árboles; el boosting
gana cuando hay muchas filas y muchas interacciones no lineales. Reportar la línea base lineal
es disciplina senior: evita justificar complejidad que no aporta.

### SHAP recupera los factores conocidos, también en real

Los factores de riesgo que SHAP ordena arriba sobre German Credit son: **estado de la cuenta
corriente** (el predictor dominante en la literatura), duración del crédito, ahorros, historial
crediticio, propósito y monto. Que el factor #1 coincida con el conocido valida que la
explicabilidad no es un artefacto del generador sintético: funciona sobre solicitantes reales.

## Para experimentar

```bash
python -m app.ml.train --rows 50000        # más datos sintéticos
python -m app.ml.benchmark                 # benchmark con datos reales (German Credit)
# edita _DEFAULT_PARAMS en app/ml/model.py (sintético) o _WELL_FIT_PARAMS en
# app/ml/benchmark.py (real) para mover la curva underfit <-> overfit tú mismo
```

Observa cómo cambian ROC-AUC/KS/Brier, cómo se abre o cierra la brecha train-test al tocar
`max_depth`/`reg_lambda`, y si las razones SHAP siguen coincidiendo con los factores conocidos.
