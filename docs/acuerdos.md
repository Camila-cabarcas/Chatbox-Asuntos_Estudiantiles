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
- `fuera_de_alcance` es `true` cuando no hay información en las fichas, y
  también cuando el modelo concluye que la información encontrada no
  responde la pregunta. En ambos casos `fuentes` trae solo el canal oficial
  del Comité.

### `POST /api/consultas/{id_consulta}/valoracion`
Entrada: `{ "util": true }` → 204 si se guardó, 404 si no.

### `GET /api/health`
Estado de la base de datos, fragmentos indexados y proveedores en uso.

## Formato de las fichas
Ver `fichas/_plantilla.md`. Reglas:
- Una ficha por trámite. Campos obligatorios: `id`, `titulo`, `fuentes`.
- `preguntas_ejemplo` es clave para la búsqueda: cada pregunta se vuelve un
  fragmento propio. Deben ser varias y estar escritas como las haría un
  estudiante (por ejemplo, "se me pasó el tiempo de ajustes y necesito meter
  una materia"), no con el nombre oficial del trámite.
- Se recomienda que cada sección empiece con `## Nombre del trámite: ...`,
  pero no es obligatorio: el sistema ya agrega el título de la ficha y el de
  la sección al inicio de cada fragmento.
- Solo información de fuentes oficiales; lo que falte se marca `PENDIENTE`.
- Sin fechas de un semestre específico.
- Quien redacta no es quien revisa (`redactada_por` / `revisada_por`).

## Forma de trabajo con Git
- Nadie sube directo a `main`. Todo entra por Pull Request.
- `main` está protegida: todo Pull Request necesita la aprobación de otra
  persona, y `pytest` debe pasar.
- Después del merge se borra la rama.
- Si un Pull Request depende de otro que no se ha integrado, la rama se crea
  desde la rama del otro Pull Request.
- Terminado = el código corre, está en `main` y el README explica cómo usarlo.

### Nombres de ramas
Formato `prefijo/tarea`, con la tarea en minúsculas y separada por guiones.

| Prefijo | Para qué | Ejemplo |
|---|---|---|
| `ia/` | Prompt, embeddings, modelo de lenguaje | `ia/groq` |
| `backend/` | API, base de datos, despliegue | `backend/esqueleto-base` |
| `front/` | Interfaz | `front/burbuja-chat` |
| `fichas/` | Fuentes oficiales y fichas | `fichas/preguntas-ejemplo` |
| `pruebas/` | Pruebas automáticas y banco de preguntas | `pruebas/pytest-pythonpath` |
| `docs/` | Documentación y configuración del repositorio | `docs/gitattributes-acuerdos` |

## Responsables por carpeta
| Carpeta | Rol |
|---|---|
| `app/rag/`, `fichas/` (plantilla y proceso) | IA y conocimiento |
| `app/api/`, `app/db/`, `app/config.py`, despliegue | Backend y datos |
| `frontend/`, `tests/`, banco de preguntas | Interfaz y pruebas |
