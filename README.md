# Chatbox-Asuntos_Estudiantiles

Prototipo de asistente conversacional web que orienta a los estudiantes de
pregrado sobre los trámites del **Comité de Asuntos Estudiantiles de Pregrado**
de la Facultad de Ingeniería, usando únicamente información oficial (patrón RAG).

Proyecto Integrador 1 - Grupo 6 - Ingeniería de Sistemas, Universidad de Antioquia.

## Arquitectura

| Capa | Qué contiene | Carpeta |
|---|---|---|
| Presentación | Interfaz web del chat (HTML, CSS, JS) | `frontend/` |
| Lógica | API REST con FastAPI + servicio RAG | `app/api/`, `app/rag/` |
| Conocimiento | Fichas, índice ChromaDB, PostgreSQL (métricas anónimas) | `fichas/`, `data/`, `app/db/` |

Flujo de una pregunta: la API recibe la pregunta, enmascara datos personales,
busca los fragmentos de fichas más parecidos en ChromaDB, se los entrega al
modelo de lenguaje con instrucciones de usar solo esa información, y devuelve
la respuesta con el enlace a la fuente oficial. La consulta se registra de
forma anónima en PostgreSQL.

## Requisitos

- Python 3.12 (todo el equipo con la misma versión)
- Git
- Docker Desktop (solo para PostgreSQL; en Windows requiere WSL2)

## Instalación (una sola vez)

```bash
git clone https://github.com/Camila-cabarcas/Chatbox-Asuntos_Estudiantiles.git
cd Chatbox-Asuntos_Estudiantiles

# 1. Entorno virtual
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

# 2. Dependencias
pip install -r requirements-dev.txt
pip install -r requirements-embeddings.txt   # modelo multilingüe (pesado)

# 3. Variables de entorno
cp .env.example .env          # Windows (cmd): copy .env.example .env

# 4. Base de datos
docker compose up -d
```

## Ejecutar

```bash
uvicorn app.main:app --reload
```

- Página de prueba: http://localhost:8000
- Documentación interactiva de la API: http://localhost:8000/docs
- Estado del sistema: http://localhost:8000/api/health

La primera vez con `EMBEDDINGS_PROVIDER=local` tarda unos minutos porque
descarga el modelo de embeddings.

## Modos de trabajo según el rol

No todos necesitan todo instalado. En `.env`:

| Situación | Configuración |
|---|---|
| Trabajar en la interfaz, sin Docker ni modelos | `DB_ENABLED=false`, `EMBEDDINGS_PROVIDER=mock`, `LLM_PROVIDER=mock` |
| Probar la calidad de las respuestas | `EMBEDDINGS_PROVIDER=local` y un proveedor LLM real |
| Probar el registro de consultas | `DB_ENABLED=true` y `docker compose up -d` |

El modo `mock` de embeddings solo compara palabras, no significado: sirve
para desarrollar, no para medir la calidad del chatbot. `RAG_MAX_DISTANCE`
está calibrado para el modelo real (ver "Calibración de la búsqueda"); con
`mock` las distancias son otras.

## Conectar el modelo de lenguaje

En `.env`:

```
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=<URL base del proveedor, terminada en /v1 o la que indique su documentación>
LLM_API_KEY=<su clave>
LLM_MODEL=<nombre del modelo>
```

Funciona con cualquier proveedor que ofrezca el endpoint `/chat/completions`
en formato OpenAI. Si falta alguno de los tres valores, el servidor no
arranca y dice exactamente cuál falta.

### Conectar Groq

Groq tiene un plan gratuito y ofrece ese endpoint. Pasos:

1. **Crear la cuenta** en https://console.groq.com.
2. **Crear la clave** en https://console.groq.com/keys y llenar el campo
   **Expiration** con una fecha de vencimiento (por ejemplo, el fin del
   semestre). Cada integrante usa su propia clave. La clave solo se ve una
   vez: cópienla directo al `.env`.
3. **Activar Zero Data Retention** en https://console.groq.com/settings/data-controls
   (lo hace quien administra la organización). Por defecto Groq no guarda
   las preguntas, pero puede conservarlas hasta 30 días si investiga fallas
   o abusos; con ZDR activado no las conserva en ningún caso. Es importante
   porque los estudiantes pueden escribir datos personales que el
   enmascaramiento no detecta (por ejemplo, su nombre).
4. **Llenar el `.env`:**
   ```
   LLM_PROVIDER=openai_compatible
   LLM_BASE_URL=https://api.groq.com/openai/v1
   LLM_API_KEY=<su clave>
   LLM_MODEL=qwen/qwen3.8-27b
   LLM_MAX_TOKENS=800
   ```
   Los modelos disponibles cambian; para ver los de su cuenta, consulten
   `GET https://api.groq.com/openai/v1/models` con su clave. Si cambian de
   modelo, repitan las pruebas de abajo.
5. Reiniciar el servidor y probar en http://localhost:8000.

**Límites del plan gratuito** para `qwen/qwen3.8-27b` (octubre de 2026, según
https://console.groq.com/docs/rate-limits y las cabeceras de respuesta):

| Límite | Valor | Qué significa para el chatbot |
|---|---|---|
| Solicitudes por minuto / por día | 30 / 1 000 | No es el límite que se alcanza primero |
| Tokens por minuto | 8 000 | ~4 preguntas por minuto |
| **Tokens por día** | **200 000** | **~100 a 120 preguntas por día** |

Cada pregunta consume entre 1 500 y 2 000 tokens (instrucciones + contexto +
respuesta). Para que alcance para más preguntas se puede bajar
`RAG_CONTEXTO_MAX_TOKENS` o `LLM_MAX_TOKENS`, a costa de algo de calidad. Si
se supera un límite, Groq responde con error y el chatbot muestra un mensaje
que remite al canal oficial.

**Resultado de las pruebas** (octubre de 2026, `qwen/qwen3.8-27b`, embeddings
MiniLM-L12, `RAG_MAX_DISTANCE=0.50`). Cada dato de las respuestas se comparó
con el contexto que recibió el modelo:

| Pregunta | Resultado |
|---|---|
| ¿Cuándo se reúne el comité? | Correcta (martes; solicitudes hasta el viernes anterior) |
| se me pasó el tiempo de ajustes y necesito meter una materia | Correcta: pasos en SSOFI y qué hacer según el tipo de materia |
| dejé de estudiar hace dos años y quiero volver a la carrera | Correcta: presenta las dos vías según la fecha, sin suponerla |
| ¿cuánto cuesta la matrícula este semestre y dónde la pago? | Fuera de alcance: remite al canal oficial |
| quiero matricular física II pero no he aprobado física I | Fuera de alcance por el umbral (pendiente: mejorar la ficha de exoneración) |
| ¿cómo preparo unas arepas con queso? | Fuera de alcance |
| Me llamo Ana y mi cédula es 1036456789, ¿cómo cancelo el semestre? | Correcta; la cédula llega enmascarada al modelo |
| ¿me van a aprobar la cancelación si la pido? | No decide el caso; explica qué instancia decide |

Ninguna respuesta inventó fechas, requisitos, correos ni enlaces, ni mostró
datos marcados como `PENDIENTE`. Tiempo de respuesta: 1 a 2,5 s. Ajustes que
salieron de estas pruebas (en `app/rag/prompts.py` y `app/rag/servicio.py`):

- Si el modelo concluye que no tiene la información, responde con la frase
  fija de fuera de alcance y la API lo marca como `fuera_de_alcance=true`.
- Respuestas de máximo ~250 palabras, en texto plano (la interfaz actual no
  muestra Markdown; si se cambia, se puede quitar esa regla del prompt).
- No supone datos del caso que el estudiante no dio; si el trámite depende
  de ellos, presenta cada opción.
- Si la respuesta se corta por `LLM_MAX_TOKENS`, se avisa al estudiante y se
  remite al canal oficial. Si el modelo escribe razonamiento interno
  (`<think>`), se quita antes de responder.

## Trabajar con las fichas

1. Descargar las fuentes oficiales: `python herramientas/descargar_fuentes.py`
2. Copiar `fichas/_plantilla.md` con un nombre nuevo y llenarla.
3. Verificar que se indexa bien y qué recupera:
   ```bash
   python -m scripts.indexar --probar "¿Cuándo se reúne el comité?"
   ```
4. Reiniciar el servidor (o dejar `INDEX_ON_STARTUP=true`).

Una ficha mal escrita no rompe el sistema: se omite y aparece una
advertencia en la consola. Las pruebas (`pytest`) fallan si alguna ficha de
la carpeta no es válida.

### Cómo se usan las fichas en la búsqueda

El modelo de embeddings solo lee 128 tokens por texto y descarta el resto en
silencio. Por eso se busca con fragmentos pequeños y se responde con
secciones completas:

- **Búsqueda:** cada pregunta de `preguntas_ejemplo` es un fragmento propio,
  y cada sección se divide por párrafos o elementos de lista (sin partir
  frases) hasta caber en `RAG_FRAGMENTO_MAX_TOKENS`.
- **Respuesta:** el modelo de lenguaje recibe las secciones completas de los
  fragmentos encontrados, sin pasar de `RAG_CONTEXTO_MAX_TOKENS`.

## Calibración de la búsqueda

`scripts/calibrar.py` mide, con el banco de preguntas de
`tests/calibracion/preguntas.csv`, qué ficha encuentra el chatbot para cada
pregunta y a qué distancia. Sirve para elegir el modelo de embeddings y
`RAG_MAX_DISTANCE`. Construye el índice en una carpeta temporal y **no lee
`.env`**: el proveedor y el modelo se pasan por argumentos.

```bash
python -m scripts.calibrar --proveedor mock
python -m scripts.calibrar --proveedor local --modelo sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
# Opcional: --json data/calibracion.json guarda el detalle por pregunta
```

Por seguridad, `--csv` solo acepta archivos `.csv` dentro del proyecto,
`--json` solo escribe archivos `.json` dentro de `data/` (que Git ignora) y
`--modelo` solo acepta identificadores de Hugging Face, no rutas locales.

Para cada pregunta muestra la primera ficha encontrada, si es la esperada,
en qué puesto quedó la esperada y la distancia del mejor fragmento. Al final
resume los aciertos, las distancias dentro y fuera del alcance, el rango de
umbral que mejor las separa, los tiempos y la memoria.

**Vuelvan a calibrar** cuando cambien el modelo de embeddings, el troceado o
muchas fichas. El CSV tiene las columnas `pregunta`, `ficha_esperada`,
`dentro_alcance` (`true`/`false`) y `tipo` (opcional). Las preguntas no deben
copiar ningún `preguntas_ejemplo`: tienen que estar escritas como las haría
un estudiante.

### Resultados (octubre de 2026)

Banco de 23 preguntas: 15 dentro del alcance (una por ficha), 6 de otros
temas de la universidad y 2 sin relación. "Top 4" = la ficha esperada está
entre las primeras 4 fichas distintas.

| | mock | **MiniLM-L12** (elegido) | mpnet-base |
|---|---|---|---|
| Ficha correcta en 1.er lugar | 11/15 | 11/15 | 11/15 |
| Ficha correcta en el top 4 | 14/15 | 14/15 | 13/15 |
| Distancia máxima dentro del alcance | 0.752 | 0.518 | 0.402 |
| Distancia mínima fuera del alcance | 0.505 | 0.432 | 0.411 |
| Mejor separación dentro/fuera | 16/23 | 21/23 | 23/23 (margen de 0.009) |
| Construir el índice | 2 s | 24 s | 118 s |
| Consulta media | 9 ms | 40 ms | 144 ms |
| Memoria máxima del proceso | ~100 MB | ~1 GB | ~1,9 GB |

**Por qué MiniLM-L12 con `RAG_MAX_DISTANCE=0.50`:**

- mpnet separa mejor, pero su 23/23 depende de un margen de 0.009 en solo 23
  preguntas, usa casi el doble de memoria, tarda 5 veces más en construir el
  índice y acierta menos en el top 4.
- Con MiniLM, entre 0.48 y 0.55 siempre quedan 2 preguntas mal clasificadas.
  Con 0.50 los errores son los menos dañinos:
  - "quiero matricular física II pero no he aprobado física I…" (0.518)
    queda fuera de alcance y se remite al canal oficial. Su búsqueda ya
    fallaba (la ficha de exoneración no queda en el top 4), así que
    aceptarla daría una respuesta equivocada.
  - "¿cuánto cuesta la matrícula este semestre y dónde la pago?" (0.432) se
    acepta aunque no es del Comité. Ningún umbral lo evita sin perder
    preguntas válidas; depende de que el modelo de lenguaje siga la regla de
    remitir cuando el contexto no tiene la respuesta.
  - La biblioteca (0.517) queda fuera por un margen de solo 0.017.
- El modo `mock` no separa dentro de fuera (16/23); por eso las pruebas
  automáticas usan su propio umbral en `tests/conftest.py`.

### Decisión pendiente: memoria para el despliegue

Con MiniLM el proceso llega a **~1 GB de memoria** (PyTorch, el modelo,
ChromaDB y el cálculo de los vectores al arrancar). En un servidor gratuito
de 512 MB no cabe. Opciones, por evaluar y medir antes de desplegar:

1. **Embeddings por API:** el servidor no carga ningún modelo. Hay que
   recalibrar con el modelo del proveedor y considerar sus límites y costos.
2. **Modelo cuantizado en ONNX**, sin PyTorch: menos memoria con el mismo
   modelo. Hay que verificar que las distancias no cambien mucho.
3. **Índice construido antes del despliegue:** el servidor solo vectoriza
   las preguntas. Reduce el tiempo de arranque, pero el modelo se sigue
   cargando en memoria.

## Pruebas

```bash
pytest
```

No requieren internet, claves, Docker ni modelos descargados. La prueba que
usa el tokenizador real del modelo se salta sola si el modelo no está
descargado.

## Seguridad y datos personales

- `.env` nunca se sube a GitHub. Si una clave se sube por error, hay que
  **revocarla en el proveedor y generar otra**; borrarla del repositorio no basta.
- No se guarda IP, navegador ni datos del estudiante. Correos y números
  largos (cédulas, teléfonos) se enmascaran antes de enviarse al modelo y
  antes de guardarse.

## Estructura

```
app/
  main.py          arranque y ensamblaje de componentes
  config.py        configuración (lee .env)
  api/             endpoints y contrato (schemas.py)
  rag/             fichas, embeddings, índice, prompts, LLM, servicio RAG
  db/              conexión, modelos y repositorio de PostgreSQL
  utils/           privacidad y logs
fichas/            base de conocimiento (una ficha por trámite)
fuentes/           copias fechadas de las páginas oficiales
herramientas/      recolección de fuentes
scripts/           utilidades (reindexar, calibrar)
frontend/          interfaz web
tests/             pruebas automáticas
docs/              acuerdos del equipo y decisiones de arquitectura
```

## Licencia

MIT. Ver [LICENSE](LICENSE).
