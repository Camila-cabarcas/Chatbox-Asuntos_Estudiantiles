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
para desarrollar, no para medir la calidad del chatbot.

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

## Pruebas

```bash
pytest
```

No requieren internet, claves, Docker ni modelos descargados.

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
scripts/           utilidades (reindexar)
frontend/          interfaz web
tests/             pruebas automáticas
docs/              acuerdos del equipo y decisiones de arquitectura
```

## Licencia

MIT. Ver [LICENSE](LICENSE).
