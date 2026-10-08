# 5. Preguntas de entrevista

Preguntas que te pueden hacer sobre este proyecto, con respuestas. Agrupadas por nivel.

## Nivel junior / media

**¿Qué hace el proyecto en una frase?**
Puntúa solicitudes de microcrédito con un modelo explicable (XGBoost + SHAP) y deja una
huella criptográfica de cada decisión en un contrato en una EVM, para poder probar
después que la decisión no fue alterada.

**¿Por qué XGBoost y no una regresión logística?**
Gradient boosting captura interacciones no lineales entre variables y suele dar mejor
poder predictivo en datos tabulares. La regresión logística sería más interpretable de
base, pero con SHAP recuperamos la interpretabilidad sin perder desempeño. En crédito,
ambos son defendibles; aquí priorizamos desempeño + explicabilidad post-hoc fiel.

**¿Qué significa ROC-AUC de 0.8?**
Que si tomas un incumplidor y un buen pagador al azar, el modelo le asigna mayor riesgo
al incumplidor el 80% de las veces. Mide capacidad de **ordenar**, no de calibrar.

**¿Cómo validas la entrada de la API?**
Con Pydantic (`ApplicantIn`): rangos (edad 18–100, montos positivos, DTI ≤ 3) y enums
(`region`, `loan_purpose`). Lo inválido se rechaza con 422 antes de llegar al modelo.

## Nivel media / senior

**¿Por qué anclas solo un hash y no la decisión completa?**
Privacidad y permanencia. Una cadena es efectivamente inmutable y, si es pública,
legible por todos. Poner datos personales ahí viola Habeas Data (Ley 1581) y no se
puede deshacer. El hash de 32 bytes prueba integridad sin exponer nada; el dato
autoritativo vive fuera de la cadena. La cadena es un notario, no una base de datos.

**¿Qué hace que el hash sea reproducible?**
Serialización canónica: `json.dumps(sort_keys=True, separators=(",",":"))` sobre un
objeto de forma fija, con el puntaje como entero en puntos básicos para evitar deriva de
flotantes. Así, la misma decisión siempre produce el mismo hash y cualquier cambio lo
rompe.

**¿Cómo detectas una manipulación?**
`verify` recalcula el hash desde el registro guardado y lo compara con el hash
almacenado y con el de la cadena. Si alguien editó un campo, el hash recalculado cambia
y devuelve `digest_mismatch`. El `make demo` lo demuestra en vivo.

**SHAP opera sobre columnas one-hot. ¿Cómo lo presentas al oficial de crédito?**
Agrego las contribuciones de las columnas one-hot a su variable padre (todas las
`region_*` suman en `region`), ordeno por contribución absoluta y devuelvo las top-k con
signo y dirección. El oficial ve "Región" o "Relación deuda/ingreso", no codificaciones.

**¿Cómo pruebas el contrato sin desplegar en una red?**
Tres niveles: (1) `eth-tester`/PyEVM, una EVM en memoria donde despliego el bytecode
real y corren las pruebas; (2) Anvil en docker-compose para el sistema completo; (3) un
`InMemoryAnchorClient` que imita la semántica del contrato para probar servicio y API
sin EVM. El servicio depende de la interfaz `AnchorClient`, no de web3.

**¿Qué pasa si puntúas dos veces al mismo solicitante?**
El digest es idéntico (misma entrada → misma decisión). El anclaje es idempotente: la
segunda vez el contrato ya tiene el digest y se marca `already_anchored`. En la base se
guardan ambos eventos de decisión; por eso `digest_hex` está indexado pero **no** es
único.

## Nivel senior / arquitectura

**¿Dónde están los límites de confianza del sistema?**
Cliente→API (entrada no confiable), servicio→base de datos, servicio→RPC (que tiene la
llave de firma) y el control de acceso del contrato. Están en
[`docs/threat-model.md`](../threat-model.md) con el análisis STRIDE.

**¿Cómo manejas la llave que firma los anclajes?**
Es configuración, nunca va al repo; `gitleaks` corre en CI. Si se compromete, el dueño
revoca ese *scorer* con `setScorer(addr, false)`. En producción usaría un firmante
respaldado por KMS/HSM. El demo usa la llave pública de desarrollo de Anvil, que es
pública a propósito.

**¿Qué le falta para producción?**
Auditoría de sesgo del modelo (impacto dispar sobre grupos protegidos), un firmante con
KMS/HSM, estrategia de respaldo de la base (sistema de registro autoritativo),
reentrenamiento con monitoreo de *drift*, y un RPC con reintentos/cola. Varios están
listados como riesgos residuales en el modelo de amenazas.

**¿Por qué no usar un blockchain para todo, incluido el modelo?**
Porque no aporta: la cadena es cara, lenta y pública. Solo la usamos para lo que aporta
valor único — una bitácora de integridad append-only que un tercero puede verificar. El
cómputo (modelo, SHAP) y el dato sensible viven fuera. Saber cuándo **no** usar
blockchain es parte del criterio de ingeniería.

## Reto para ti

* Agrega un endpoint que exporte un "certificado de decisión" (JSON con el payload
  canónico + el digest + el bloque) que un tercero pueda verificar sin acceso a la base.
* Agrega una métrica de calibración por tramos (reliability diagram) al reporte de
  entrenamiento.
* Cambia el `InMemoryAnchorClient` por un segundo contrato con *merkle batching* para
  anclar muchas decisiones en una sola transacción. ¿Qué cambia en `verify`?
