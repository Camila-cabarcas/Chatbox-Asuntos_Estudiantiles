# ADR-0001: Monolito modular en tres capas con RAG

## Estado
Aceptado

## Contexto
Prototipo académico de 16 semanas desarrollado por 3 estudiantes. El
anteproyecto define una arquitectura en tres capas (presentación, lógica,
conocimiento), RAG sin entrenar modelos propios, FastAPI, ChromaDB,
PostgreSQL en Docker y despliegue en una nube de capa gratuita.

## Decisión
- Un solo servicio FastAPI que expone la API REST y sirve el frontend
  (un único despliegue).
- Módulos con fronteras claras: `api` (entrada), `rag` (dominio del
  asistente), `db` (persistencia).
- Embeddings y modelo de lenguaje detrás de interfaces intercambiables
  (`local`/`mock` y `openai_compatible`/`mock`), elegidas por configuración.
- Degradación controlada: si fallan la base de datos o el proveedor de IA,
  el chatbot responde con un mensaje de remisión en vez de fallar.
- Tablas creadas al arrancar (`create_all`), sin migraciones.

## Consecuencias positivas
- Cada integrante trabaja en su módulo sin bloquear a los demás.
- Se puede desarrollar y probar sin claves, sin Docker y sin internet.
- Cambiar de proveedor de IA no requiere modificar código.

## Consecuencias negativas / riesgos
- Sin migraciones: cambiar la tabla `consultas` implica recrearla.
- En capa gratuita, el modelo de embeddings local puede exceder la memoria
  disponible; habría que agregar un proveedor de embeddings por API.
- El índice se reconstruye al arrancar (aceptable con decenas de fichas).

## Alternativas consideradas
- Streamlit: más rápido para una persona, pero mezcla interfaz y lógica y
  dificulta el trabajo en paralelo.
- FAISS: más bajo nivel; no guarda metadatos (título, URL) de forma nativa.
- Microservicios: complejidad operativa injustificada para un prototipo.
