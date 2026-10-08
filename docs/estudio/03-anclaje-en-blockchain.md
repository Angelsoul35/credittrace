# 3. Anclaje en blockchain

## El problema de integridad

El modelo ya da una decisión explicada. Pero surge una pregunta de auditoría: dentro de
seis meses, en una disputa, ¿cómo pruebo que **esta** decisión se tomó así y no fue
editada después en la base de datos? Un registro en una base de datos lo controla quien
tiene acceso a la base de datos; no es prueba frente a un tercero.

La idea de CreditTrace: dejar una **huella inalterable** de cada decisión en un registro
de solo-escritura (un contrato en una EVM), de modo que cualquiera con la decisión
original pueda probar que existía y no cambió.

## Qué es un digest (hash)

Un *hash criptográfico* como `keccak256` toma cualquier entrada y produce 32 bytes de
salida con dos propiedades:

* **Determinista:** la misma entrada siempre da la misma salida.
* **Sensible:** cambiar un solo bit de la entrada cambia por completo la salida, y es
  inviable encontrar dos entradas con el mismo hash.

Entonces, si publico el hash de una decisión, luego puedo probar que una decisión dada
produce ese hash — y si alguien la altera, el hash ya no coincide.

## La carga canónica

El hash solo sirve si la serialización es **canónica**: la misma decisión debe producir
siempre los mismos bytes. En `app/chain/digest.py`:

```python
json.dumps(obj, sort_keys=True, separators=(",", ":"))
```

`sort_keys=True` fija el orden de las claves; `separators` elimina espacios. El objeto
tiene una forma fija:

```
{ "decision": "...", "features": {...}, "model_version": "m_...", "score_bps": 1518 }
```

El puntaje se guarda como **entero en puntos básicos** (`score_bps`, 1518 = 15.18%)
para evitar que diferencias de representación de números flotantes cambien el hash. El
digest es `keccak256(carga canónica)`. (Ver [ADR-0003](../adr/0003-canonical-serialization.md).)

## Solo el digest, nunca los datos

Punto crítico de diseño ([ADR-0002](../adr/0002-anchor-digest-not-data.md)): el
contrato almacena **únicamente** el digest de 32 bytes. Los datos personales y
financieros nunca llegan a la cadena. Esto cumple Habeas Data (Ley 1581) y hace que el
mismo esquema sirva incluso en una cadena pública: no hay nada privado que exponer.

La cadena actúa como **notario**, no como base de datos: confirma que un digest existía
en un bloque, pero no guarda la decisión. El dato autoritativo vive fuera de la cadena.

## El contrato `DecisionRegistry`

En `contracts/src/DecisionRegistry.sol`, un contrato minimalista:

* `anchor(bytes32 digest)` — guarda `{submitter, timestamp, blockNumber}`. Solo un
  *scorer* autorizado; revierte si el digest es cero o si ya fue anclado
  (`AlreadyAnchored`). Es **append-only**: no hay forma de borrar o reescribir.
* `isAnchored(digest)` / `recordOf(digest)` — lecturas públicas para verificar.
* `setScorer` / `transferOwnership` — control de acceso del dueño.

> **Concepto — control de acceso.** `onlyScorer` y `onlyOwner` son *modifiers* que
> revierten la transacción si `msg.sender` no tiene el permiso. Así, aunque el contrato
> sea público, solo las direcciones autorizadas pueden anclar.

## Verificación y detección de alteración

`GET /decisions/{id}/verify` (en `app/service.py`):

1. Recalcula el digest a partir del registro **guardado**.
2. Lo compara con el digest almacenado → `digest_matches`.
3. Consulta el digest en la cadena → `on_chain.anchored`.

| Estado | Significado |
|---|---|
| `verified` | el digest coincide y está anclado |
| `digest_mismatch` | alguien alteró un campo del registro |
| `not_anchored` | coincide pero nunca se ancló |
| `chain_disabled` | el anclaje estaba apagado |

El `make demo` lo demuestra: puntúa, verifica (`verified`), luego **altera** el ingreso
guardado y vuelve a verificar → `digest_mismatch`. Esa es la evidencia de manipulación.

## Cómo se prueba sin una blockchain real

No hace falta desplegar en una red real para desarrollar ni para las pruebas. Usamos:

* **`eth-tester` / PyEVM** — una EVM en memoria, dentro del proceso de Python. Las
  pruebas despliegan el contrato *compilado de verdad* ahí (ver `tests/test_chain.py`).
* **Anvil** — un nodo de desarrollo local (en `docker-compose.yml`), para correr el
  sistema completo.
* **`InMemoryAnchorClient`** — un doble en memoria que imita la semántica del contrato,
  para pruebas del servicio y la API sin ninguna EVM.

El servicio depende de la **interfaz** `AnchorClient`, no de web3 directamente, así que
las tres opciones son intercambiables (ver [capítulo 4](04-arquitectura-y-diseno.md)).

## Compilación del contrato

Compilamos con `solc-js` (el compilador de Solidity empaquetado en npm), vía
`node contracts/compile.js`, que produce `contracts/artifacts/DecisionRegistry.json`
(ABI + bytecode). Ese artefacto se versiona en git, de modo que el runtime y las
pruebas no necesitan un compilador instalado. CI recompila y verifica que el artefacto
comiteado no quedó desactualizado.
