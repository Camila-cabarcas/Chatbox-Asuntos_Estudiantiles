# Acuerdos del equipo

Cualquier cambio a este documento se discute con los tres integrantes.

## Contrato de la API

### `POST /api/chat`
Entrada:
```json
{ "pregunta": "¿Cómo cancelo el semestre?" }
```
- `pregunta`: texto de 2 a 1000 caracteres. Fuera de ese rango responde 422.

Salida (200):
```json
{
  "respuesta": "texto para mostrar al estudiante",
  "fuentes": [{ "titulo": "Cancelación regular de semestre", "url": "https://..." }],
  "fuera_de_alcance": false,
  "id_consulta": 123
}
```
- `id_consulta` es `null` si la base de datos no está disponible.
- `fuera_de_alcance` es `true` cuando no hay información en las fichas.

### `POST /api/consultas/{id_consulta}/valoracion`
Entrada: `{ "util": true }` → 204 si se guardó, 404 si no.

### `GET /api/health`
Estado de la base de datos, fragmentos indexados y proveedores en uso.

## Formato de las fichas
Ver `fichas/_plantilla.md`. Reglas:
- Una ficha por trámite. Campos obligatorios: `id`, `titulo`, `fuentes`.
- Cada sección empieza con `## Nombre del trámite: ...`.
- Solo información de fuentes oficiales; lo que falte se marca `PENDIENTE`.
- Sin fechas de un semestre específico.
- Quien redacta no es quien revisa (`redactada_por` / `revisada_por`).

## Forma de trabajo con Git
- Nadie sube directo a `main`. Todo entra por Pull Request.
- Ramas: `rol/tarea`, por ejemplo `ia/prompt-remisiones`, `backend/metricas`, `front/burbuja-chat`.
- Cada Pull Request lo aprueba otra persona y `pytest` debe pasar.
- Terminado = el código corre, está en `main` y el README explica cómo usarlo.

## Responsables por carpeta
| Carpeta | Rol |
|---|---|
| `app/rag/`, `fichas/` (plantilla y proceso) | IA y conocimiento |
| `app/api/`, `app/db/`, `app/config.py`, despliegue | Backend y datos |
| `frontend/`, `tests/`, banco de preguntas | Interfaz y pruebas |
