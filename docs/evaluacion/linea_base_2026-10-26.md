# Línea base: banco de 30 preguntas

**Fecha de la medición:** 26 de octubre de 2026
**Indicador del anteproyecto:** que el prototipo responda correctamente al menos
el 80 % de un banco de 30 preguntas.

Es una **primera medición**: las fichas aún no tienen revisión cruzada
(`redactada_por` / `revisada_por`).

## Resumen

| | Resultado | Meta |
|---|---|---|
| **Indicador (datos esenciales)** | **17 / 30 (57 %)** | 24 / 30 (80 %) |
| Regla estricta (todos los datos clave) | 14 / 30 (47 %) | — |

| Tipo | Correctas | Parciales | Incorrectas | % correctas |
|---|---|---|---|---|
| Normales (18) | 9 | 5 | 4 | 50 % |
| Ambiguas (4) | 0 | 2 | 2 | 0 % |
| Fuera de alcance (4) | 4 | 0 | 0 | 100 % |
| Remisión (4) | 4 | 0 | 0 | 100 % |
| **Total (30)** | **17** | **7** | **6** | **57 %** |

- **Lo que funciona:** el modelo casi no inventa. Las 8 preguntas fuera de
  alcance o de remisión salen correctas. Cuando no encuentra la ficha, dice
  que no tiene la información en lugar de suponer.
- **Lo que falla:** la búsqueda y el armado del contexto explican 12 de los
  13 fallos. El modelo se equivocó en 2 (en uno de ellos la causa es mixta).

## Configuración medida

| Parámetro | Valor |
|---|---|
| Rama | `pruebas/banco-30`, creada desde `fichas/cobertura-busqueda`, con las 55 `preguntas_ejemplo` nuevas |
| Embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (local); 477 fragmentos |
| Modelo de lenguaje | `qwen/qwen3.8-27b` en Groq |
| Búsqueda | `RAG_TOP_K=8`, `RAG_MAX_DISTANCE=0.50` |
| Contexto y respuesta | `RAG_CONTEXTO_MAX_TOKENS=1500`, `LLM_MAX_TOKENS=800` |
| Forma de medir | API real (`POST /api/chat`, puerto 8001), 25 s entre preguntas |
| Consumo | 25 llamadas al modelo (las otras 5 no pasaron el umbral); 46 700 tokens (mediana de 1 730 de entrada y 211 de salida; máximo de 2 218 por pregunta) |
| Tiempos y errores | Mediana de 2.2 s por respuesta (máximo 48 s, por latencia de Groq); ningún error ni respuesta cortada |

- **Banco:** [`tests/evaluacion/banco_30.csv`](../../tests/evaluacion/banco_30.csv).
  Sus preguntas tienen una similitud máxima de 0.796 con `preguntas.csv`,
  `cobertura.csv` y los `preguntas_ejemplo`.
- **Respuestas completas:** [`linea_base_2026-10-26_respuestas.json`](linea_base_2026-10-26_respuestas.json).

## Rúbrica

La rúbrica completa está en
[`tests/evaluacion/rubrica.md`](../../tests/evaluacion/rubrica.md). Se fijó
antes de medir, junto con la respuesta esperada y los datos esenciales de cada
pregunta.

- **Correcta:** contiene todos los datos esenciales, no inventa nada y remite
  bien. En fuera de alcance y remisión, reconoce que no puede responder o
  decidir, y da el canal oficial.
- **Parcial:** lo que dice es correcto, pero le falta algún dato esencial.
- **Incorrecta:** inventa, contradice la ficha, remite a una instancia
  equivocada o responde fuera de alcance como si supiera.
- **Ambiguas:** los esenciales son las dos vías y la condición que las
  distingue.
- **Fuentes:** se registran, pero no se califican, porque hoy el campo
  `fuentes` muestra una URL por documento (pendiente: fuentes por ficha).
- **Regla estricta (dato secundario):** exige todos los datos de
  `respuesta_esperada`.

## Resultados por pregunta

"¿En el contexto?" indica si la ficha esperada, o su alternativa, llegó al
contexto del modelo.

| id | Tipo | ¿En el contexto? | Calificación | Estricta | Observación |
|---|---|---|---|---|---|
| N01 | normal | Sí | Parcial | Parcial | Tiene la ruta del portal y el PDF único; faltan cédula, PAYSA y Saber Pro |
| N02 | normal | Sí | Correcta | Parcial | No lista los campos del formulario |
| N03 | normal | Sí | Correcta | Correcta | |
| N04 | normal | No | Incorrecta | Incorrecta | "No encontré información" (mejor distancia: 0.709) |
| N05 | normal | Sí | Incorrecta | Incorrecta | Dice que lo que no puede faltar es la incapacidad (es el PAYSA) y agrega un documento de otra ficha |
| N06 | normal | Sí | Correcta | Correcta | |
| N07 | normal | No | Incorrecta | Incorrecta | "No encontré información" |
| N08 | normal | No | Incorrecta | Incorrecta | "No encontré información" |
| N09 | normal | Sí | Parcial | Parcial | Nombra el trámite; no dice SSOFI ni qué diligenciar |
| N10 | normal | Sí | Correcta | Parcial | No nombra el tipo de solicitud |
| N11 | normal | Sí | Correcta | Correcta | |
| N12 | normal | Sí | Parcial | Parcial | Tiene los 3 documentos; dice que no tiene el correo (no lo inventa) |
| N13 | normal | Sí | Correcta | Correcta | |
| N14 | normal | Sí | Correcta | Parcial | No menciona la radicación en SSOFI |
| N15 | normal | Sí | Parcial | Parcial | Tiene los 2 días hábiles; dice que no tiene el formato y menciona "el contexto" |
| N16 | normal | Solo la alternativa | Correcta (1) | Correcta | Responde por la vía del supletorio, completa |
| N17 | normal | Sí | Correcta | Correcta | |
| N18 | normal | Sí | Parcial | Parcial | Omite que decide el Consejo Académico; no dice SSOFI ni los 7 días |
| A01 | ambigua | Una de las dos | Incorrecta | Incorrecta | La vía "dentro del plazo" manda a SSOFI y no al Portal |
| A02 | ambigua | Una de las dos | Parcial | Parcial | Solo explica el ajuste extemporáneo |
| A03 | ambigua | No | Incorrecta | Incorrecta | "No encontré información" (llegó la ficha de exoneración) |
| A04 | ambigua | Sí | Parcial | Parcial | Solo explica la vía extemporánea; falta la del Portal |
| F01–F04 | fuera de alcance | — | Correcta | Correcta | Frase de fuera de alcance y canal oficial |
| R01 | remisión | Sí | Correcta | Correcta | "No puedo determinar…, lo decide el Comité" |
| R02 | remisión | Sí | Correcta (2) | Correcta | Respondió con la frase de fuera de alcance y el canal |
| R03 | remisión | Sí | Correcta | Correcta | No estima probabilidades ni inventa requisitos |
| R04 | remisión | Sí | Correcta | Correcta | Advierte que la nota del jurado es definitiva aunque sea menor |

**Calificaciones revisadas por el equipo** (las marcadas como dudosas):

1. **N16:** cuenta como correcta, porque el supletorio estaba definido como
   ficha alternativa antes de medir. Con la regla estricta también cuenta
   como correcta: trae todos los datos de esa vía.
2. **R02:** cuenta como correcta, pero podría explicar mejor que el asistente
   no consulta casos particulares, e indicar que las respuestas se publican
   en SSOFI desde las 14:00 del viernes posterior a la sesión.
3. **N05 y A01:** se confirman como incorrectas. N05 equivoca el documento
   indispensable. A01 contradice la ficha de cancelaciones: la cancelación
   ordinaria se hace por el Portal.

## Análisis de causas

| Causa | Casos | Preguntas |
|---|---|---|
| **No encontró la ficha** (o una de las dos, en las ambiguas) | 6 | N04, N07, N08, A03 · A01, A02 |
| **La ficha llegó, pero sin la sección que tiene el dato** | 5 | N01, N09, N12, N15, A04 |
| **El modelo se equivocó** | 2 | N05 · N18 (causa mixta) |
| **La ficha no tiene el dato** | 0 | — |

### 1. No encontró la ficha (6)

- **N04, N07 y N08:** la ficha esperada no llegó al contexto.
  - En N04 ningún fragmento pasó el umbral: la mejor distancia fue 0.709.
  - En N07 y N08 la ficha esperada no quedó ni entre los 8 primeros
    fragmentos.
  - Las tres preguntas usan palabras que no aparecen en las fichas:
    "termodinámica", "no he ganado álgebra lineal", "Universidad Nacional",
    "refrenden".
- **A03:** "física de campos" atrajo la ficha de exoneración (que tiene
  preguntas sobre física) en lugar de supletorio o incompletos.
- **A01 y A02:** solo llegó una de las dos fichas relevantes, así que la
  respuesta presentó una sola vía.
  - En A01, el modelo completó la vía que faltaba con la regla de otra
    ficha, y por eso la respuesta es incorrecta y no parcial.

En los casos sin ficha, el modelo respondió "No encontré información". Es lo
seguro, pero el estudiante se queda sin respuesta.

### 2. La ficha llegó, pero sin la sección que tiene el dato (5)

El contexto se arma con la sección que coincidió con la pregunta, una por
ficha, hasta llenar 1 500 tokens. Si el dato está en otra sección de la misma
ficha, no llega al modelo:

| Pregunta | Sección que llegó | Sección que faltó |
|---|---|---|
| N01 | Pasos del grado | Documentos |
| N09 | Matrícula extemporánea | Campos del formulario |
| N12 | Pasos de movilidad | Contacto (el correo) |
| N15 | Requisitos del segundo calificador | Documentos (el enlace bit.ly/viceing) |
| A04 | Cancelación extemporánea de semestre | Cancelación ordinaria por el Portal |

En N12 y N15 el modelo dijo que no tenía el dato, sin inventarlo.

### 3. El modelo se equivocó (2)

- **N05:** la ficha correcta estaba en el contexto, junto con la de
  cancelación de cursos. El modelo mezcló las dos: presentó la incapacidad
  como el documento indispensable y agregó el "reporte de calificaciones",
  que pertenece a la otra ficha.
- **N18:** "decide el Consejo Académico" estaba en el contexto y el modelo
  lo omitió. La sección con la regla de los 7 días no llegó, así que la
  causa es mixta.

### Incumplimiento de la regla 10 del prompt

En **N15** el modelo escribió "El contexto proporcionado no especifica…". La
regla 10 del prompt dice que no debe mencionar el CONTEXTO sino hablar de
"la información oficial". No cambió la calificación (la respuesta ya era
parcial), pero se debe vigilar en las próximas mediciones.

## Por qué difiere del 83 % de cobertura

La medición de cobertura (`tests/calibracion/cobertura.csv`, rama
`fichas/cobertura-busqueda`) dio que la ficha esperada **llega al contexto**
en 50 de 60 preguntas (83 %). No mide lo mismo que este indicador:

1. **En la búsqueda, los dos resultados coinciden.** En este banco, la ficha
   esperada (o su alternativa) llegó al contexto en 22 de las 26 preguntas
   dentro del alcance (85 %), un valor casi igual al 83 %.
2. **Cobertura mide si la ficha llega, no si la respuesta sirve.** Que llegue
   la ficha no basta: el dato tiene que estar en la sección que entró al
   contexto, y el modelo tiene que usarlo bien. De las 22 preguntas que
   encontraron su ficha, 13 fueron correctas: en 5 la sección con el dato no
   llegó, en 2 el modelo se equivocó, y dos ambiguas encontraron solo una de
   sus dos fichas.
3. **Las ambiguas exigen dos fichas a la vez.** En cobertura bastaba con que
   llegara la esperada o una alternativa. Aquí las dos vías son esenciales, y
   ninguna de las 4 ambiguas salió correcta.
4. **Las preguntas del banco son nuevas.** Las 55 `preguntas_ejemplo` se
   escribieron para que `cobertura.csv` mejorara. El banco no se usó para
   ajustar nada; por eso mide mejor cómo se comportará el sistema con
   preguntas reales.
5. **Este indicador incluye fuera de alcance y remisión,** que salieron al
   100 % y suben el total.

## Plan de mejora

Las palancas están ordenadas por el número de fallos que podrían resolver.
Ninguna se aplicó en esta medición.

### A. Armado del contexto (5 fallos por sección faltante, y ayuda en las ambiguas)

1. **Priorizar secciones según la pregunta.** Hoy entra la sección que
   coincidió con la pregunta. Propuesta:
   - Incluir siempre la sección de **contacto** de cada ficha encontrada. Es
     corta (mediana de unos 160 tokens) y resuelve N12.
   - Si la pregunta pide documentos, plazos o formatos ("qué subo", "qué
     papeles", "cuántos días", "qué formato"), agregar la sección de
     **documentos** o **plazos** de la misma ficha (N01, N15).
   - Si la primera ficha cabe completa, incluirla entera y llenar con las
     demás. Una ficha completa tiene de 270 a 1 900 tokens estimados, con
     mediana de 1 330, así que con 1 500 tokens solo cabe completa la mitad
     de las fichas.
2. **Garantizar las dos primeras fichas distintas.** Esto ayudaría en las
   ambiguas (A01, A02, A04), pero solo si la búsqueda las trae (ver B).
3. **Subir `RAG_CONTEXTO_MAX_TOKENS`, y su efecto en los límites de Groq.**
   El plan gratuito permite **8 000 tokens por minuto y 200 000 por día**
   (también 30 solicitudes por minuto y 1 000 por día, que no son el límite
   que se alcanza primero).

   | `RAG_CONTEXTO_MAX_TOKENS` | Tokens por pregunta (aprox.) | Preguntas por minuto | Preguntas por día |
   |---|---|---|---|
   | 1 500 (actual) | ~1 870 (medido) | ~4 | ~105 |
   | 2 500 | ~2 900 | ~2–3 | ~70 |
   | 3 000 | ~3 400 | ~2 | ~58 |

   Duplicar el contexto reduce casi a la mitad las preguntas por día con la
   misma cuenta. Para el prototipo puede servir, pero en producción haría
   falta un plan de pago o un proveedor con límites mayores. Además, un
   contexto más grande diluye la información, y casos como N05 (mezclar
   fichas) pueden aumentar. Por eso conviene probar primero la priorización
   (punto 1), que no aumenta el costo.

### B. Búsqueda (6 fallos por ficha no encontrada)

1. **Más `preguntas_ejemplo` coloquiales.** Por ejemplo: materias concretas
   ("termodinámica", "álgebra lineal") en exoneración y cancelación; "me
   refrenden" y otras universidades en homologación; cirugía o
   hospitalización en supletorio e incompletos.
   - Riesgo: sobreajuste. Deben escribirse a partir de las fichas, nunca
     copiando preguntas de `banco_30.csv`, o la próxima medición dejará de
     ser válida.
2. **Búsqueda híbrida (palabras clave + embeddings).** Un índice por
   palabras (BM25) encontraría términos exactos que MiniLM no relaciona:
   "PIFLE", "refrendar", "PAYSA", "supletorio", nombres de materias. Se
   combina con la búsqueda actual (por ejemplo, fusión por posiciones). No
   necesita más memoria de modelo.
3. **Otro modelo de embeddings.** En la calibración, `mpnet` separó mejor
   las preguntas (23/23), pero usa unos 1.9 GB de memoria. Otra opción son
   los embeddings por API, que no ocupan memoria del servidor pero agregan
   costo y límites. Hay que recalibrar el umbral en cualquier caso.

### C. Modelo y prompt (2 fallos y una regla incumplida)

- Reforzar en el prompt que no mezcle datos de fichas distintas en un mismo
  trámite (N05) y que no mencione "el contexto" (N15).
- En remisión, pedir que explique que no consulta casos particulares (R02).

### Cómo medir el avance

Repetir esta medición con el mismo banco y la misma rúbrica después de cada
palanca, una a la vez, para atribuir el efecto. Cuando las fichas tengan
revisión cruzada, conviene escribir un segundo banco que no se haya usado
para ajustar nada.
