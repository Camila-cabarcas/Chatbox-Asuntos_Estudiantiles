# Línea base: banco de 30 preguntas

**Fecha de la medición:** 2 de noviembre de 2026
**Indicador del anteproyecto:** que el prototipo responda correctamente al menos
el 80 % de un banco de 30 preguntas (24 de 30).

Es una **medición** del banco de 30 preguntas, sobre la rama
`fichas/cobertura-busqueda` (commit `153ae94`) **con cambios sin commitear** en
el árbol de trabajo. Las fichas no tienen revisión cruzada
(`redactada_por` / `revisada_por` vacíos).

## Resumen

| | Resultado | Meta |
|---|---|---|
| **Indicador (datos esenciales)** | **26 / 30 (87 %)** | 24 / 30 (80 %) |
| Conteo conservador (A02 parcial) | 25 / 30 (83 %) | 24 / 30 (80 %) |
| Regla estricta (todos los datos clave) | 18 / 30 (60 %) | — |

| Tipo | Correctas | Parciales | Incorrectas | % correctas |
|---|---|---|---|---|
| Normales (18) | 16 | 0 | 2 | 89 % |
| Ambiguas (4) | 3 | 0 | 1 | 75 % |
| Fuera de alcance (4) | 4 | 0 | 0 | 100 % |
| Remisión (4) | 3 | 1 | 0 | 75 % |
| **Total (30)** | **26** | **1** | **3** | **87 %** |

- **Lo que funciona:** las 8 preguntas fuera de alcance o de remisión salen
  correctas salvo R02. Las 18 preguntas normales bajan a 2 fallos (N04, N07).
  Las ambiguas quedan en 3 de 4: A01, A02 y A03 ya presentan las dos vías.
- **Lo que falla:** N04 y N07 no recuperan la ficha correcta; A04
  recibe la ficha pero no la sección con la regla del PAYSA; R02 da pasos pero
  no reconoce que no puede consultar el caso.
- **La cifra estable es 25, no 26.** A02 y N16 cambiaron de parcial a correcta
  en repeticiones con el **mismo contexto**: es varianza del modelo, no una
  mejora del sistema. El conteo conservador (A02 parcial) da 25/30; en una
  corrida mala podría bajar a 23–24. Las dos cifras superan la meta.

## Configuración medida

| Parámetro | Valor |
|---|---|
| Rama / commit | `fichas/cobertura-busqueda` / `153ae94`, con cambios sin commitear |
| Embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (local); **480 fragmentos** |
| Modelo de lenguaje | `openai/gpt-oss-120b` en Groq (`LLM_TEMPERATURE=0.1`, `LLM_TIMEOUT_SECONDS=30`) |
| Búsqueda | `RAG_TOP_K=8`, `RAG_MAX_DISTANCE=0.50` |
| Rescate léxico | `RAG_HIBRIDO=true`, `RAG_HIBRIDO_MARGEN=0.65` (BM25, solo tras un "no encontré") |
| Contexto y respuesta | `RAG_CONTEXTO_MAX_TOKENS=2000`, `LLM_MAX_TOKENS=1200` |
| Fragmentos | `RAG_FRAGMENTO_MAX_TOKENS=128`, solapamiento 1 |
| Base de datos | `DB_ENABLED=true`, pero `id_consulta` salió `null` en las 30 respuestas |
| Forma de medir | API real (`POST /api/chat`, puerto 8000) con `evaluar_banco.py`, 45 s entre preguntas |
| Tiempos y tokens | **No registrados.** El script no guarda latencia ni consumo |

> Los valores de `LLM_MAX_TOKENS` y `RAG_CONTEXTO_MAX_TOKENS` son los del
> `.env` local con el que se midió. La plantilla `.env.example` sigue en
> 800 / 1500; si se quiere reproducir esta corrida, hay que subirlos a
> 1200 / 2000.

- **Banco:** [`tests/evaluacion/banco_30.csv`](../../tests/evaluacion/banco_30.csv).
- **Respuestas completas:**
  [`linea_base_2026-11-02_respuestas.json`](linea_base_2026-11-02_respuestas.json),
  con las 30 respuestas consolidadas. SHA-256
  `49348EE6F093895C375B8F99F11D5B53A96FF8E26859062792AFF8B3F34344F3`.
- **Calificación por pregunta:** está en la tabla de este documento; los JSON
  de prueba se eliminaron de `data/`.
- **Script de medición:** `evaluar_banco.py`.

### Cómo se armó esta corrida

1. **19:42** — corrida completa de las 30 (23/30 con el criterio de ese
   momento). 0 fallos de proveedor, 0 respuestas cortadas.
2. **20:09** — repetición dirigida de N15, N16 y A02. **No sirvió para N15:**
   uvicorn llevaba levantado desde las 19:15 y el índice solo se reconstruye al
   arrancar (`INDEX_ON_STARTUP=true`), así que midió las fichas viejas.
3. **20:19** — repetición dirigida de N15, N16 y A02 **después de reiniciar
   uvicorn**. Es la que se consolidó para esas tres preguntas. Las otras 27
   vienen de la corrida de 19:42.

## Rúbrica y criterios

La rúbrica completa está en
[`tests/evaluacion/rubrica.md`](../../tests/evaluacion/rubrica.md). Se aplicó
sin cambios.

- **Correcta:** contiene todos los datos esenciales, no inventa nada y remite
  bien. En fuera de alcance y remisión, reconoce que no puede responder o
  decidir, y da el canal oficial.
- **Parcial:** lo que dice es correcto, pero le falta algún dato esencial.
- **Incorrecta:** inventa, contradice la ficha, remite a una instancia
  equivocada o responde fuera de alcance como si supiera.
- **Ambiguas:** los esenciales son las dos vías y la condición que las
  distingue. Si presenta solo una vía y es correcta, la respuesta es parcial.
- **Fuentes:** se registran, pero **no se califican**.
- **Regla estricta:** exige todos los datos de `respuesta_esperada`.

### Por qué hay tres cifras

| Pregunta | Indicador | Conservador | Estricta | Motivo |
|---|---|---|---|---|
| A02 | Correcta | Parcial | Correcta | La última repetición añadió la Matrícula Extemporánea como alternativa, pero en una sola frase. La rúbrica dice que con las dos vías es correcta; el conteo conservador la deja en parcial. |
| N16 | Correcta | Correcta | Parcial | Da las dos vías y los 6 meses, pero no advierte que lo no presentado queda en 0.0. |
| R02 | Parcial | Parcial | Parcial | Da pasos y canal, pero no dice que no puede consultar el estado del caso. |

El indicador oficial es **26/30 (87 %)**. El conteo conservador **25/30 (83 %)**
es el que se venía usando y el que no depende de la frase adicional de A02. La
regla estricta queda en **18/30 (60 %)**.

## Resultados por pregunta

"¿En el contexto?" indica si la ficha esperada, o su alternativa, llegó al
contexto del modelo. "Solo rescate léxico" significa que el vectorial no la
trajo y entró en el segundo intento de `servicio.py` (BM25). "Dist. esperada"
es la distancia del fragmento más cercano de la ficha esperada; un guion
significa que esa ficha no quedó ni entre los 8 fragmentos recuperados.

| id | Tipo | ¿En el contexto? | Dist. esperada | Calificación | Estricta | Observación |
|---|---|---|---|---|---|---|
| N01 | normal | Sí | 0.2510 | Correcta | Correcta | Ruta del portal, un solo PDF y los cuatro documentos |
| N02 | normal | Sí | 0.4735 | Correcta | Parcial | No dice que Álgebra Lineal es tronco común |
| N03 | normal | Sí | 0.3456 | Correcta | Parcial | Art. 136 y trámite correctos; no menciona la pérdida de calidad |
| N04 | normal | No | 0.7414 | Incorrecta | Incorrecta | "No encontré"; ningún fragmento pasó el umbral |
| N05 | normal | Sí | 0.3832 | Correcta | Correcta | Consejo Académico, PAYSA y soportes médicos |
| N06 | normal | Sí | 0.3237 | Correcta | Correcta | 10 días hábiles, Vicedecanato y formato |
| N07 | normal | No | — | Incorrecta | Incorrecta | Responde con Ajuste Extemporáneo; la ficha de exoneración no entró |
| N08 | normal | Solo rescate léxico | — | Correcta | Parcial | El vectorial no la trajo; el rescate léxico la recuperó |
| N09 | normal | Sí | 0.4074 | Correcta | Correcta | Trámite, campos y canal |
| N10 | normal | Sí | 0.3928 | Correcta | Parcial | Da el tope de 27 y los anexos; no menciona prerrequisitos |
| N11 | normal | Sí | 0.2330 | Correcta | Correcta | Art. 67, argumento Pensum cerrado y constancia |
| N12 | normal | Sí | 0.4441 | Correcta | Correcta | Los tres documentos y el correo |
| N13 | normal | Sí | 0.2587 | Correcta | Parcial | Tipo de solicitud correcto; no nombra la Escuela de Idiomas |
| N14 | normal | Sí | 0.2393 | Correcta | Correcta | Avales, entrega física y plazo |
| N15 | normal | Sí | 0.3417 | Correcta | Correcta | Plazo y formato; el enlace quedó en la sección de plazos |
| N16 | normal | Sí | 0.3549 | Correcta | Parcial | Las dos vías y los 6 meses; falta la consecuencia del 0.0 |
| N17 | normal | Sí | 0.3049 | Correcta | Correcta | Condiciones y tipo de solicitud |
| N18 | normal | Sí | 0.3520 | Correcta | Correcta | Aval, umbral de 7 días y Consejo Académico |
| A01 | ambigua | Sí | 0.3656 | Correcta | Parcial | Las dos vías; no concreta las causales |
| A02 | ambigua | Sí | 0.4874 | Correcta | Correcta | Las dos vías y la condición; la segunda va en una frase |
| A03 | ambigua | Solo rescate léxico | 0.5005 | Correcta | Parcial | El vectorial quedó justo sobre el umbral; el rescate dio las dos vías |
| A04 | ambigua | Sí, sección equivocada | 0.2605 | Incorrecta | Incorrecta | Afirma que la vía del Portal no exige PAYSA |
| F01–F04 | fuera de alcance | — | — | Correcta | Correcta | Reconoce el límite y da el canal oficial |
| R01 | remisión | Sí | 0.4447 | Correcta | Correcta | No promete resultado; describe el trámite y da el canal |
| R02 | remisión | Sí | 0.3479 | Parcial | Parcial | Da pasos y canal, pero no dice que no puede consultar el caso |
| R03 | remisión | Sí | 0.2928 | Correcta | Correcta | No estima probabilidad; explica las condiciones |
| R04 | remisión | Sí | 0.4099 | Correcta | Correcta | Nota definitiva, plazo y canal |

## Análisis de causas

| Causa | Casos | Preguntas |
|---|---|---|
| **No encontró la ficha** | 2 | N04, N07 |
| **La ficha llegó, pero sin la sección que tiene el dato** | 1 | A04 |
| **El modelo omitió un dato** | 1 | R02 |

### 1. No encontró la ficha (2)

- **N04:** ningún fragmento pasó el umbral; el más cercano quedó en 0.7414. La
  pregunta usa "termodinámica", "3.2" y "40 %", términos que no están en la
  ficha. El rescate léxico tampoco la encontró.
- **N07:** la ficha de exoneración no quedó ni entre los 8 primeros fragmentos.
  El mejor resultado fue la ficha de **Ajuste Extemporáneo** (0.4971), y el
  modelo la usó: respondió el trámite equivocado con seguridad. Como no dijo
  "no encontré", **el rescate léxico no se activó**. Es el caso más engañoso:
  la respuesta suena correcta y los documentos que da son plausibles, pero el
  trámite no es el que corresponde.
- Las dos comparten el mismo patrón: palabras del caso que no aparecen en
  la ficha. La solución no es subir el umbral, sino mejorar la recuperación
  (preguntas de ejemplo coloquiales, otro modelo de embeddings o un
  cross-encoder).

### 2. La ficha llegó, pero sin la sección que tiene el dato (1)

- **A04:** la ficha de cancelación extemporánea de semestre entra con holgura
  (0.2605), pero solo su bloque de **"Preguntas frecuentes"**. La sección
  *"Cancelaciones Ordinarias de Curso y Semestre (Portal UdeA)"* —la que dice
  que la vía del Portal **también** exige el Paz y Salvo de PAYSA— nunca entra
  al top 8. El modelo ve la vía extemporánea, no ve la regla de la ordinaria y
  concluye, con lógica, que la vía del Portal no necesita PAYSA. El error es de
  insumo, no de razonamiento.

### 3. El modelo omitió un dato (1)

- **R02:** la respuesta da pasos útiles (revisar SSOFI, escribir al Comité) y
  el canal oficial, pero **no dice que el asistente no puede consultar el
  estado de un caso particular**. La rúbrica lo exige para las remisiones. Es
  una omisión de redacción, no de contexto.

### 4. Varianza del modelo (no es un fallo del sistema)

- **N16 y A02** cambiaron de parcial a correcta entre repeticiones con el
  **mismo contexto**. En N16 la respuesta pasó de dar solo el supletorio a dar
  también la Solicitud Incompleto Curso o Semestre; en A02 apareció la segunda
  vía en una frase. No hubo cambio de ficha, índice ni prompt entre esas
  repeticiones: es el modelo.
- Por eso el número estable es el conservador (25/30), no el 26. Para la
  próxima medición conviene repetir 2–3 preguntas de control y reportar la
  banda, no un solo valor.

## Qué dicen estos números sobre la búsqueda

- La ficha esperada, o su alternativa, llegó al contexto en **24 de las 26
  preguntas** dentro del alcance (92 %). El vectorial solo llegó a 22; el
  rescate léxico sumó **N08 y A03**.
- De esas 24, **22 terminaron correctas**. Las dos que llegaron y fallaron son
  A04 (sección equivocada) y R02 (omisión del modelo).
- **La búsqueda no es el cuello de botella principal.** Quedan 2 fallos de
  recuperación (N04, N07); los otros dos son de armado de contexto y de
  redacción.
- El umbral de 0.50 está en una zona frágil: A03 quedó en 0.5005 (entró por el
  rescate léxico, no por el vectorial) y N07 en 0.4971 (entró la ficha
  equivocada). Cualquier cambio de embeddings obliga a recalibrar con
  `cobertura.csv`, no con el banco.

## Hallazgos adicionales

1. **`id_consulta` salió `null` en las 30 respuestas** con `DB_ENABLED=true`.
   El registro de consultas no se guardó, así que tampoco hay latencias ni
   valoraciones de esta corrida. Hay que revisar la conexión y las tablas.
2. **`fuentes` muestra la ficha equivocada.** En N08 y A03 el título
   que se muestra no es el de la ficha que aportó el dato. La causa es que
   varias fichas comparten la URL del reglamento y `_fuentes` deduplica por
   URL. No se califica, pero confunde al revisar.
3. **El rescate léxico es invisible en `fuentes`.** Cuando la ficha rescatada
   comparte la URL del reglamento, no aparece. Además, solo se activa tras un
   "no encontré": por eso ayudó a N08 y A03, pero no a N07, donde el modelo
   respondió con la ficha equivocada sin dudar.
4. **A04 es incorrecta; el intento de arreglarla por ficha no funcionó.**
   Se probó añadir la regla del PAYSA a la sección *"instancias de decisión"*
   de `Cancelación extemporanea semestre.md` (una sección que A04 sí recibe).
   El añadido partió la sección en 3 fragmentos, el nuevo no entró al top 8 y
   **desplazó fuera el fragmento que traía el "Consejo Académico"**. Se
   revirtió: la ficha volvió a sus 2 fragmentos originales. Cualquier edición
   de ficha debe verificarse contra el contexto de las 30, no solo de la
   pregunta objetivo.
5. **`practicas.md` tiene un fragmento de 130 tokens** (> 128) y con el
   problema de cobertura del CSV. Son los **2 tests rojos preexistentes**
   (`test_troceado`, `test_calibrar`); no hay fallos nuevos.
6. **`INDEX_ON_STARTUP=true` no recarga fichas en caliente.** Una edición de
   ficha no afecta a un uvicorn ya levantado. La repetición de N15 a las 20:09
   fue inválida por eso; la de las 20:19, tras reiniciar, es la que se usa.
   Para la próxima medición: editar fichas → reiniciar uvicorn (o reconstruir
   el índice) → medir.

## Plan de mejora

Las palancas están ordenadas por el número de fallos que podrían resolver.
Ninguna se aplicó después de esta medición.

### A. Recuperación (2 fallos: N04, N07)

1. **Más `preguntas_ejemplo` coloquiales.** Materias concretas
   ("termodinámica", "álgebra lineal") en cancelación y exoneración;
   "Universidad Nacional" y "refrenden" en homologación; "cirugía" y
   "hospitalización" en supletorio e incompletos. Deben escribirse a partir de
   las fichas, **nunca copiando preguntas de `banco_30.csv`**.
2. **Búsqueda híbrida desde el primer intento.** Hoy el BM25 solo entra tras un
   "no encontré"; N07 demuestra que un modelo puede responder con la ficha
   equivocada y saltarse el rescate. Probar a mezclar el ranking léxico con el
   vectorial antes de llamar al modelo, con un margen conservador.
3. **Otro modelo de embeddings o un cross-encoder.** En la calibración,
   `mpnet` separó mejor las preguntas (23/23), pero usa ~1.9 GB de memoria.
   Requiere recalibrar el umbral con `cobertura.csv`.
4. **Recalibrar el umbral, no subirlo a ojo.** A03 (0.5005) y N07 (0.4971)
   están en la frontera. La calibración debe hacerse con `cobertura.csv`, no
   con el banco.

### B. Armado del contexto (1 fallo: A04, y ayuda en las ambiguas)

1. **Garantizar la sección de la vía ordinaria cuando la pregunta pide
   "salirme de todas las materias" o "cancelar el semestre".** Si la ficha de
   cancelación entra por una `pregunta_ejemplo`, añadir su sección
   *"Cancelaciones Ordinarias"* antes de llenar con secciones de otras fichas.
2. **Elegir la sección por intención, no por posición.** Si la pregunta pide
   documentos, plazos o formatos, priorizar las secciones de documentos,
   plazos o formulario de esa ficha.
3. **Cuidar el troceado al editar fichas.** A04 demostró que añadir una viñeta
   a una sección puede partirla y expulsar otro dato. Reconstruir el contexto
   offline (foto de las secciones que recibiría cada pregunta) antes de gastar
   una corrida completa.

### C. Prompt (1 fallo: R02; ayuda en A04 y N07)

- **Decir explícitamente que no puede consultar el estado de un caso.** La
  regla 5 cubre "no puedo saber el resultado", pero no "no puedo consultar el
  estado". Añadir una frase para las remisiones.
- **No negar un requisito que el contexto no contradice.** En A04 el modelo
  afirmó "no es necesario el PAYSA" sin que ninguna sección lo dijera. Una
  regla del tipo "si no ves la regla de una vía, no afirmes que no existe"
  podría evitar la afirmación falsa, pero afecta a las 30.
- **Si la pregunta dice que no aprobó un prerrequisito, el trámite es
  Exoneración.** Ayudaría a N07, pero es una regla específica y afecta a las
  30; medirla con una corrida completa.

### D. Medición

1. **Guardar latencia, tokens y distancias** en `evaluar_banco.py`. Hoy la
   distancia se reconstruyó aparte contra el índice; el JSON no la guarda.
2. **Arreglar `id_consulta`** (hallazgo 1): `DB_ENABLED=true` sin registro
   significa que no se está guardando nada.
3. **Repetir 2–3 preguntas de control** en cada medición para separar una
   mejora real de la varianza del modelo (N16 y A02 son el ejemplo).
4. **Corregir `practicas.md`** (hallazgo 5) y el CSV de cobertura: los 2 tests
   rojos no deben quedar como ruido permanente.

### Cómo medir el avance

Repetir esta medición con el mismo banco, la misma rúbrica y el mismo modelo
después de cada palanca, **una a la vez**. Reportar siempre las tres cifras:
indicador, conteo conservador y regla estricta. Reiniciar uvicorn después de
editar fichas. No ajustar `preguntas_ejemplo` con preguntas del banco. Cuando
las fichas tengan revisión cruzada, escribir un segundo banco que no se haya
usado para ajustar nada.

## Nota de entrega

- Los `data/evaluacion_*.json` de prueba se eliminaron del proyecto.
- El JSON consolidado con las 30 respuestas quedó en
  [`linea_base_2026-11-02_respuestas.json`](linea_base_2026-11-02_respuestas.json),
  con las respuestas de N15, N16 y A02 reevaluadas a las 20:19. También hay una
  copia fuera del repositorio (`evaluacion_final_2026-11-02.json`).
- Esta línea base (`linea_base_2026-11-02.md` y
  `linea_base_2026-11-02_respuestas.json`) **sí** se versiona.
- El `.env` está en `.gitignore` y **no está rastreado**: no hay que quitar la
  `api_key` para hacer el commit. El único archivo de entorno que se versiona
  es `.env.example`, que no contiene claves.
