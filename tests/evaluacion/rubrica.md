# Rúbrica del banco de 30 preguntas

Se define antes de medir. Cada respuesta se compara con `banco_30.csv` y con
el texto de la ficha de origen:

- `datos_esenciales`: 2 o 3 datos, separados por "|", sin los cuales la
  respuesta no le sirve al estudiante. **Correcta exige todos.**
- `respuesta_esperada`: todos los datos clave. Los que no son esenciales son
  deseables: solo cuentan en la regla estricta (dato secundario).

## Calificaciones

| Calificación | Preguntas normales y ambiguas | Fuera de alcance y remisión |
|---|---|---|
| **Correcta** | Contiene todos los datos esenciales, no inventa nada y remite bien (trámite o tipo de solicitud en SSOFI, instancia y canal correctos). | Reconoce que no puede responder (fuera de alcance) o que no puede decidir ni saber el resultado (remisión), y da el canal oficial. |
| **Parcial** | Lo que dice es correcto, pero le falta algún dato esencial. | Reconoce el límite, pero no da el canal oficial. |
| **Incorrecta** | Inventa un dato, contradice la ficha o remite a una instancia equivocada. | Responde como si supiera (inventa el dato, promete un resultado o inventa requisitos). |

- **Ambiguas:** los datos esenciales son las dos vías y la condición que las
  distingue. Si presenta solo una vía y es correcta, la respuesta es parcial.
- **Inventar:** cualquier requisito, plazo, enlace, correo, oficina o
  resultado que no esté en la ficha. Si aparece, la respuesta es incorrecta
  aunque tenga los datos clave.
- **Respuesta vacía o mensaje de error del modelo:** incorrecta.
- **Fuentes:** se registran, pero no se califican. Hoy el campo `fuentes`
  muestra una URL por documento, y varias fichas comparten la del
  reglamento; esto está pendiente (fuentes por ficha).
- **⚠:** marca las calificaciones dudosas, para revisión humana.

## Indicador

Indicador del anteproyecto: **al menos el 80 % de respuestas correctas**
(24 de 30), con los datos esenciales. Solo cuentan las correctas; las
parciales no suman.

Dato secundario (regla estricta): el mismo conteo, pero exigiendo todos los
datos clave de `respuesta_esperada`.

## Causas de las parciales e incorrectas

- **No encontró la ficha:** la ficha de origen no llegó al contexto.
- **La ficha no tiene el dato:** la ficha no contiene lo que se pregunta.
- **El modelo se equivocó:** la ficha estaba en el contexto, pero el modelo
  omitió, cambió o inventó información.
