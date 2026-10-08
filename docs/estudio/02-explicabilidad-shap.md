# 2. Explicabilidad con SHAP

## Por qué una decisión de crédito debe explicarse

Si rechazas un crédito, el solicitante (y el regulador) tienen derecho a saber **por
qué**. "El modelo dijo que no" no es aceptable. Además, un oficial de crédito necesita
entender la decisión para poder revertirla o pedir información adicional. La
explicación debe estar en **variables reales**, no en detalles internos del modelo.

## Qué es SHAP

SHAP (SHapley Additive exPlanations) reparte la predicción entre las variables usando
los **valores de Shapley** de la teoría de juegos. La idea: tratar cada variable como un
"jugador" que contribuye al resultado, y asignarle la contribución promedio que aporta
sobre todas las combinaciones posibles de variables.

Propiedades que lo hacen ideal aquí:

* **Aditividad:** `salida = valor_base + Σ contribuciones`. Las contribuciones suman
  exactamente la diferencia respecto a la predicción promedio.
* **Fidelidad al modelo:** no es una racionalización posterior; refleja cómo el modelo
  realmente usó cada variable.
* **Signo e intensidad:** cada contribución es positiva (empuja hacia más riesgo) o
  negativa (hacia menos), y su magnitud indica cuánto pesó.

Para modelos de árboles existe `TreeExplainer`, que calcula los valores SHAP de forma
exacta y eficiente.

## El detalle fino: volver a las variables originales

El modelo no ve `region`; ve columnas one-hot (`region_caribe`, `region_andina`, …).
SHAP da una contribución por **columna transformada**. Un oficial de crédito no
entiende `cat__region_caribe = 0.03`; entiende "Región".

Por eso, en `CreditRiskModel.explain` (`app/ml/model.py`) **agregamos** las
contribuciones de las columnas one-hot a su variable padre:

```
cat__region_andina  = 0.00
cat__region_caribe  = 0.03   ->  region = 0.03  (se suman todas las region_*)
cat__region_pacifica= 0.00
```

Luego ordenamos las variables por `|contribución|` y devolvemos las `top_k` (5 por
defecto), cada una con su valor, su contribución firmada y su dirección
(`increases_risk` / `decreases_risk`).

## Cómo se ve en una decisión

```
decision   : REVIEW (band=medium)
probability: 0.1518
top reasons:
   - Debt-to-income ratio: 0.1337 (-0.484)   <- baja el riesgo
   + Late payments (12m): 1 (+0.321)         <- sube el riesgo
   - Applicant age: 71 (-0.315)
```

El signo coincide con la intuición y con los pesos del generador sintético: menos
deuda sobre ingreso baja el riesgo; una mora reciente lo sube. Esa coincidencia es la
validación de que el modelo aprendió señal real, no ruido.

## Verificación cruzada con el generador

Como conocemos los pesos "reales" (`capítulo 1`), podemos comprobar que las variables
que el generador hizo importantes (`debt_to_income`, `num_late_payments_12m`,
`has_collateral`) aparecen de forma consistente en las razones SHAP con el signo
correcto. La prueba `test_higher_risk_profile_scores_higher` formaliza una parte de
esto: un perfil de alto riesgo debe puntuar más alto que uno de bajo riesgo.

## Advertencia honesta

SHAP explica **qué variables** movieron la predicción, no establece **causalidad**. En
un sistema real habría además un análisis de sesgo (impacto dispar sobre grupos
protegidos) antes de poner el modelo en producción. Lo mencionamos en el
[modelo de amenazas](../threat-model.md) como riesgo residual.
