# 4. Arquitectura y diseño

## Las capas

```
app/
  ml/        contrato de features · dato sintético · modelo XGBoost · SHAP · versionado
  chain/     digest canónico · compilación (solc-js) · clientes de anclaje
  db/         modelos SQLAlchemy y sesión
  service.py  orquestación: puntuar -> persistir -> anclar -> verificar
  main.py     API FastAPI
contracts/   DecisionRegistry.sol + compilador solc-js + pruebas Foundry
```

Cada capa tiene una sola responsabilidad. La API (`main.py`) es una cáscara delgada
sobre `ScoringService`; el servicio no sabe de HTTP, y el modelo no sabe de bases de
datos ni de cadena. Esa separación es lo que hace el sistema testeable y mantenible.

## Inversión de dependencias: el corazón del diseño

`ScoringService` **no** depende de web3. Depende de un `Protocol`:

```python
class AnchorClient(Protocol):
    @property
    def address(self) -> str: ...
    def is_anchored(self, digest: bytes) -> bool: ...
    def record_of(self, digest: bytes) -> AnchorRecord: ...
    def anchor(self, digest: bytes) -> AnchorReceipt: ...
```

Hay dos implementaciones (`app/chain/registry.py`):

* **`Web3AnchorClient`** — habla con el contrato real, en Anvil o en la EVM en memoria.
* **`InMemoryAnchorClient`** — un diccionario que imita la semántica del contrato
  (digest de un solo uso, revierte en duplicado).

> **Principio SOLID — Inversión de Dependencias (la D).** Los módulos de alto nivel
> (el servicio) no deben depender de los de bajo nivel (web3), sino de abstracciones.
> Aquí el servicio depende de `AnchorClient`; web3 es un detalle intercambiable.

Beneficios concretos:

* Las pruebas del servicio y de la API corren **sin ninguna blockchain** usando el
  doble en memoria (rápidas y deterministas).
* El anclaje se puede **apagar** por completo (`CT_CHAIN_ENABLED=false`) para puntuar
  sin cadena.
* Cambiar de Anvil a una red real es cambiar configuración, no código.

## Inyección de dependencias en FastAPI

`app/deps.py` construye un `ScoringService` a partir de la configuración (carga el
modelo, abre la base de datos, conecta el cliente de cadena si corresponde). La API lo
recibe con `Depends(get_service)`. En las pruebas, `conftest.py` **sobrescribe** esa
dependencia (`app.dependency_overrides`) con un servicio armado sobre una EVM en memoria
y una base SQLite temporal. Así probamos la API real contra infraestructura de prueba.

## Configuración por entorno

`app/config.py` usa `pydantic-settings` con prefijo `CT_`. Nada de secretos en el
código: la URL de la base, la versión del modelo, la URL del RPC, la dirección del
contrato y la llave de firma son variables de entorno (ver `.env.example`).

## Persistencia

`app/db/models.py` define la tabla `decisions`. Guarda todo lo necesario para
**reconstruir** el digest (features, versión, puntaje, decisión) además del digest y la
información del anclaje. El `digest_hex` está indexado pero **no es único** a propósito:
los mismos datos pueden volver a puntuarse y producir el mismo digest (es una dirección
de contenido, no un identificador de fila).

## Flujo de una decisión

1. FastAPI valida la entrada con `ApplicantIn` (rangos y enums) → 422 si es inválida.
2. `ScoringService.score` obtiene probabilidad y razones del modelo.
3. La `RiskPolicy` mapea el puntaje (en bps) a banda y acción.
4. Se calcula el digest canónico.
5. Si el anclaje está activo y el digest no existe, se ancla; si ya existe, se marca
   `already_anchored` (idempotencia).
6. Se persiste la fila y se responde.

## Calidad y pruebas

* **27 pruebas**: digest, modelo, contrato (desplegado en EVM en memoria), servicio y
  API. Cobertura exigida ≥ 80% en CI.
* **Solidity** probado dos veces: por Python contra el bytecode compilado y por
  **Foundry** (`forge test`, con una prueba de *fuzzing*).
* **CI** (`.github/workflows/ci.yml`): `ruff` (lint), compilación del contrato +
  verificación de artefacto, pruebas con cobertura, `bandit` y `gitleaks` (seguridad),
  y build de la imagen Docker.

## Decisiones registradas (ADRs)

Las decisiones de diseño no obvias están documentadas en `docs/adr/`: por qué anclar
solo el digest, por qué la serialización canónica, por qué SHAP agregado a variables
reales. Leerlas es la mejor forma de entender el *por qué* detrás del *qué*.
