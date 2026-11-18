# Especificación de diseño: widget TiToAI

Resumen del mockup "TiToAI · Widget de chatbot" hecho en Claude Design.
Es la referencia visual para desarrollar el widget en `frontend/`.

## Colores

| Uso | Color |
|---|---|
| Encabezado (fondo) | `#33691E` |
| Línea inferior del encabezado | `#7DB006` (4 px) |
| Verde principal: botones, burbuja del usuario, bordes de sugerencias | `#14612C` |
| Verde al pasar el mouse (hover) | `#0E4A21` |
| Fondo del avatar y foco sobre fondo oscuro | `#BEF97A` |
| Verde casi negro: sombras y contorno de foco | `#011A18` |
| Burbuja del bot | `#EEEEEE`, texto `#1B1B1B` |
| Texto secundario | `#444444` |
| Bordes del campo de texto | `#5F6F52` |
| Borde de la tarjeta de fuente | `#C3CFB8` |
| Línea sobre el campo de texto | `#D5DCCB` |
| Error: fondo / texto / icono | `#FCE8E6` / `#5C120B` / `#8A1C12` |
| Sin conexión: fondo / texto / borde | `#FFF4D6` / `#4A3200` / `#E3CF9A` |

Tipografía: `'Open Sans', 'Segoe UI', Arial, sans-serif`. Tamaños: nombre 17 px
(negrita), mensajes 14 px, subtítulos y avisos 11.5–12.5 px.

## Componentes

**Burbuja minimizada** (abajo a la derecha, 12 px del borde)
- Etiqueta blanca tipo píldora "¿Dudas sobre trámites?", texto `#14612C` en
  negrita 14 px, borde 1.5 px `#14612C`, sombra suave.
- Avatar de la mascota de 64 px, circular, borde 3 px `#14612C`, fondo `#BEF97A`.
- Todo es un solo botón con `aria-label="¿Dudas sobre trámites? Abrir el chat de TiToAI"`.
- En móvil puede mostrarse solo el avatar.

**Ventana del chat**
- Escritorio: 380 × 600 px, esquinas de 16 px, a 24 px del borde inferior y
  derecho, sombra `0 14px 44px rgba(1,26,24,0.38)`.
- Móvil (≤ 480 px de ancho): pantalla completa, sin esquinas redondeadas.
- `role="dialog"`, `aria-label="Chat de TiToAI"`.

**Encabezado** (alto mínimo 68 px)
- Avatar de 44 px con borde 2 px `#BEF97A`.
- "TiToAI" (17 px, negrita) y debajo "Asistente de Asuntos Estudiantiles ·
  Facultad de Ingeniería" (12 px).
- Botón de minimizar de 44 × 44 px con una flecha hacia abajo,
  `aria-label="Minimizar el chat"`.

**Mensaje del bot**
- Avatar pequeño de 28 px a la izquierda.
- Burbuja `#EEEEEE`, esquinas `4px 16px 16px 16px`, ancho máximo 300 px.
- Puede incluir: lista numerada de pasos (números en negrita `#14612C`),
  tarjeta de fuente, botón de acción ("Reintentar") y la pregunta "¿Te fue
  útil?" con pulgar arriba y abajo (botones de 44 px).
- Variante de error: fondo `#FCE8E6` con icono de advertencia.

**Mensaje del usuario**
- Alineado a la derecha, fondo `#14612C`, texto blanco, esquinas
  `16px 4px 16px 16px`, ancho máximo 82%.
- Si no se pudo enviar: debajo, "No enviado" en `#8A1C12` con icono.

**Tarjeta de fuente / canal**
- Fondo blanco, borde `#C3CFB8`, esquinas 12 px.
- Etiqueta en mayúsculas: "FUENTE OFICIAL" (icono de documento) o "CANAL
  OFICIAL" (icono de ubicación).
- Título del trámite en negrita y enlace subrayado "Ver fuente oficial" o "Ir
  al canal oficial" con icono de flecha, que abre en una pestaña nueva.

**Indicador de escritura**
- Tres puntos animados `#33691E` y el texto "TiToAI está escribiendo…".
- Sin animación si la persona tiene activado `prefers-reduced-motion`.

**Sugerencias**
- Botones tipo píldora de 44 px de alto, borde 1.5 px `#14612C`, texto
  `#14612C` 14 px semibold: "Ajustes de matrícula", "Cancelar un curso",
  "Validaciones", "Homologar materias".

**Campo de texto**
- Aviso permanente arriba (11.5 px, icono de información): "TiToAI orienta,
  pero no reemplaza la atención de la Unidad. No compartas datos personales."
- Campo de 44 px de alto, esquinas de 22 px, placeholder "Escribe tu
  pregunta…", con su `<label>` accesible.
- Botón de enviar circular de 44 px, `#14612C`, `aria-label="Enviar mensaje"`.
- Sin conexión: campo y botón deshabilitados, placeholder "Sin conexión…".

## Textos

- Saludo: "¡Hola! Soy TiToAI. Te ayudo a encontrar información oficial sobre
  trámites estudiantiles. ¿Qué necesitas?"
- Error: "Algo salió mal y no pude responder. Puedes intentarlo de nuevo o
  acudir al canal oficial." + botón "Reintentar" + tarjeta de canal oficial.
- Sin conexión (franja amarilla bajo el encabezado): "Sin conexión. Revisa tu
  internet para seguir." y en el chat: "Parece que no tienes conexión. Cuando
  vuelvas a estar en línea, intenta enviar tu pregunta de nuevo." + "Reintentar".

## Estados que muestra el mockup

1. Minimizado (solo la burbuja).
2. Abierto con saludo y sugerencias.
3. Conversación: pregunta, respuesta con pasos, tarjeta de fuente y "¿Te fue útil?".
4. Remisión (fuera de alcance): mensaje y tarjeta de canal oficial.
5. Error del servicio.
6. Sin conexión.
7. Móvil: burbuja y chat a pantalla completa.

## Comportamiento

- El chat se abre solo a los 4 segundos de cargar la página.
- Si la persona lo minimiza, queda solo la burbuja y no se vuelve a abrir solo.
- Al tocar la burbuja, se abre de nuevo.
