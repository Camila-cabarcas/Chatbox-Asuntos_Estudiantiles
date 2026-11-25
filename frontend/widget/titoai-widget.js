/*
 * Widget de chat TiToAI (Asuntos Estudiantiles, Facultad de Ingeniería).
 *
 * Se inserta en cualquier página con una sola etiqueta:
 *   <script src=".../widget/titoai-widget.js" data-api="https://servidor"
 *           data-auto-open="4" defer></script>
 *
 * Atributos opcionales:
 *   data-api        URL base de la API. Por defecto, el origen de este script.
 *   data-auto-open  Segundos para abrirse solo (4 por defecto; "no" = nunca).
 *   data-canal      URL del canal oficial para el estado de error.
 *
 * Diseño: docs/diseño/widget-titoai.md. Contrato de la API: docs/acuerdos.md.
 * Privacidad: la conversación vive solo en memoria. En localStorage se guarda
 * únicamente si la persona minimizó el chat.
 */
(function () {
  "use strict";

  // --- Configuración ------------------------------------------------------

  const script = document.currentScript;
  if (!script || document.querySelector("titoai-widget")) return;

  const URL_SCRIPT = new URL(script.src, location.href);
  const API = (script.dataset.api || URL_SCRIPT.origin).replace(/\/+$/, "");
  const AVATAR = new URL("assets/titoai.png", URL_SCRIPT).href;
  const SEGUNDOS_AUTO = script.dataset.autoOpen === undefined ? 4 : Number(script.dataset.autoOpen);
  const CANAL = {
    titulo: "Comité de Asuntos Estudiantiles - Facultad de Ingeniería",
    url: script.dataset.canal ||
      "https://www.udea.edu.co/wps/portal/udea/web/inicio/unidades-academicas/" +
      "ingenieria/acerca-facultad/comites/comite-asuntos-estudiantiles",
  };

  const TIEMPO_MAXIMO_MS = 35000;
  const MIN_CARACTERES = 2;
  const MAX_CARACTERES = 1000;
  const CLAVE_MINIMIZADO = "titoai-minimizado";

  const TEXTOS = {
    burbuja: "¿Dudas sobre trámites?",
    abrir: "¿Dudas sobre trámites? Abrir el chat de TiToAI",
    nombre: "TiToAI",
    subtitulo: "Asistente de Asuntos Estudiantiles · Facultad de Ingeniería",
    saludo: "¡Hola! Soy TiToAI. Te ayudo a encontrar información oficial sobre " +
      "trámites estudiantiles. ¿Qué necesitas?",
    aviso: "TiToAI orienta, pero no reemplaza la atención de la Unidad. " +
      "No compartas datos personales.",
    placeholder: "Escribe tu pregunta…",
    placeholderSinConexion: "Sin conexión…",
    escribiendo: "TiToAI está escribiendo…",
    error: "Algo salió mal y no pude responder. Puedes intentarlo de nuevo o " +
      "acudir al canal oficial.",
    franjaSinConexion: "Sin conexión. Revisa tu internet para seguir.",
    sinConexion: "Parece que no tienes conexión. Cuando vuelvas a estar en línea, " +
      "intenta enviar tu pregunta de nuevo.",
    longitud: "Tu pregunta debe tener entre " + MIN_CARACTERES + " y " +
      MAX_CARACTERES + " caracteres.",
  };

  const SUGERENCIAS = [
    "Ajustes de matrícula", "Cancelar un curso", "Validaciones", "Homologar materias",
  ];

  // Íconos fijos (trazos de 24 × 24). Son las únicas cadenas que se insertan
  // como HTML; nunca llevan texto de la API ni del usuario.
  const SVG_INICIO = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
    'aria-hidden="true" focusable="false">';
  const ICONOS = {
    minimizar: '<polyline points="6 9 12 15 18 9"/>',
    enviar: '<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>',
    info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/>' +
      '<line x1="12" y1="8" x2="12.01" y2="8"/>',
    advertencia: '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>' +
      '<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    alerta: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>' +
      '<line x1="12" y1="16" x2="12.01" y2="16"/>',
    sinConexion: '<line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/>' +
      '<path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M10.71 5.05A16 16 0 0 1 22.58 9"/>' +
      '<path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/>' +
      '<line x1="12" y1="20" x2="12.01" y2="20"/>',
    documento: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>' +
      '<polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>' +
      '<line x1="16" y1="17" x2="8" y2="17"/>',
    ubicacion: '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    flecha: '<line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/>',
    descargar: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/>' +
      '<line x1="12" y1="15" x2="12" y2="3"/>',
    reintentar: '<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>',
    pulgarArriba: '<path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>',
    pulgarAbajo: '<path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>',
  };

  const ESTILOS = `
    :host { all: initial; }
    *, *::before, *::after { box-sizing: border-box; }
    [hidden] { display: none !important; }

    .raiz {
      font-family: 'Open Sans', 'Segoe UI', Arial, sans-serif;
      font-size: 14px; line-height: 1.45; color: #1B1B1B;
    }
    .sr {
      position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
    }
    button { font: inherit; cursor: pointer; }
    button:focus-visible, a:focus-visible {
      outline: 3px solid #011A18; outline-offset: 2px;
    }
    .icono { width: 18px; height: 18px; flex: none; }
    .icono-chico { width: 14px; height: 14px; flex: none; }

    /* Burbuja minimizada */
    .burbuja {
      position: fixed; right: 12px; bottom: 12px; z-index: 2147483000;
      display: flex; align-items: center; gap: 10px;
      padding: 0; border: 0; border-radius: 999px; background: transparent;
    }
    .burbuja-etiqueta {
      background: #FFFFFF; color: #14612C; font-weight: 700; font-size: 14px;
      border: 1.5px solid #14612C; border-radius: 999px; padding: 10px 16px;
      box-shadow: 0 4px 14px rgba(1, 26, 24, 0.18);
      transition: color .15s, border-color .15s;
    }
    .burbuja-avatar {
      width: 64px; height: 64px; border-radius: 50%; display: block;
      border: 3px solid #14612C; background: #BEF97A; object-fit: cover;
      box-shadow: 0 6px 18px rgba(1, 26, 24, 0.28);
    }
    .burbuja:hover .burbuja-etiqueta { color: #0E4A21; border-color: #0E4A21; }
    .burbuja:hover .burbuja-avatar { border-color: #0E4A21; }

    /* Ventana */
    .ventana {
      position: fixed; right: 24px; bottom: 24px; z-index: 2147483000;
      width: 380px; height: 600px;
      max-width: calc(100vw - 48px); max-height: calc(100vh - 48px);
      display: flex; flex-direction: column; overflow: hidden;
      background: #FFFFFF; border-radius: 16px;
      box-shadow: 0 14px 44px rgba(1, 26, 24, 0.38);
    }

    /* Encabezado */
    .encabezado {
      display: flex; align-items: center; gap: 12px; min-height: 68px;
      padding: 10px 8px 10px 16px; flex: none;
      background: #33691E; color: #FFFFFF; border-bottom: 4px solid #7DB006;
    }
    .encabezado-avatar {
      width: 44px; height: 44px; border-radius: 50%; flex: none;
      border: 2px solid #BEF97A; background: #BEF97A; object-fit: cover;
    }
    .encabezado-textos { min-width: 0; }
    .nombre { margin: 0; font-size: 17px; font-weight: 700; line-height: 1.2; }
    .subtitulo { margin: 0; font-size: 12px; line-height: 1.35; }
    .minimizar {
      margin-left: auto; width: 44px; height: 44px; flex: none;
      display: grid; place-items: center;
      border: 0; border-radius: 50%; background: transparent; color: #FFFFFF;
      transition: background-color .15s;
    }
    .minimizar .icono { width: 24px; height: 24px; }
    .minimizar:hover { background: rgba(255, 255, 255, 0.16); }
    .minimizar:focus-visible { outline: 3px solid #BEF97A; outline-offset: -3px; }

    /* Franja sin conexión */
    .franja {
      display: flex; align-items: center; gap: 8px; flex: none;
      padding: 8px 14px; font-size: 12.5px;
      background: #FFF4D6; color: #4A3200; border-bottom: 1px solid #E3CF9A;
    }

    /* Mensajes */
    .mensajes {
      flex: 1; overflow-y: auto; overscroll-behavior: contain;
      display: flex; flex-direction: column; gap: 12px; padding: 16px 14px;
    }
    .fila-bot { display: flex; align-items: flex-start; gap: 8px; }
    .avatar-mini {
      width: 28px; height: 28px; border-radius: 50%; flex: none;
      background: #BEF97A; object-fit: cover;
    }
    .burbuja-bot {
      min-width: 0; max-width: 300px; padding: 10px 12px;
      background: #EEEEEE; color: #1B1B1B; font-size: 14px;
      border-radius: 4px 16px 16px 16px; overflow-wrap: anywhere;
    }
    .burbuja-bot p { margin: 0 0 8px; white-space: pre-line; }
    .burbuja-bot ol { margin: 4px 0 8px; padding-left: 22px; }
    .burbuja-bot li { margin-bottom: 4px; white-space: pre-line; }
    .burbuja-bot li::marker { color: #14612C; font-weight: 700; }
    .enlace-texto { color: #14612C; font-weight: 600; text-decoration: underline; overflow-wrap: anywhere; }
    .enlace-texto:hover { color: #0E4A21; }
    .burbuja-bot > :last-child, .contenido > :last-child { margin-bottom: 0; }
    .estado { display: flex; align-items: flex-start; gap: 8px; }
    .estado .icono { margin-top: 1px; }
    .burbuja-bot.error { background: #FCE8E6; color: #5C120B; }
    .burbuja-bot.error .estado .icono { color: #8A1C12; }
    .burbuja-bot.sin-conexion { background: #FFF4D6; color: #4A3200; border: 1px solid #E3CF9A; }

    .fila-usuario { display: flex; flex-direction: column; align-items: flex-end; }
    .burbuja-usuario {
      max-width: 82%; padding: 10px 12px;
      background: #14612C; color: #FFFFFF; font-size: 14px;
      border-radius: 16px 4px 16px 16px;
      white-space: pre-wrap; overflow-wrap: anywhere;
    }
    .no-enviado {
      display: flex; align-items: center; gap: 4px; margin-top: 4px;
      color: #8A1C12; font-size: 12px;
    }

    /* Tarjeta de fuente o canal */
    .tarjeta {
      margin-top: 10px; padding: 10px 12px 2px;
      background: #FFFFFF; border: 1px solid #C3CFB8; border-radius: 12px;
    }
    .tarjeta-etiqueta {
      display: flex; align-items: center; gap: 6px;
      font-size: 11.5px; font-weight: 700; letter-spacing: .06em;
      text-transform: uppercase; color: #444444;
    }
    .tarjeta-etiqueta .icono-chico { color: #14612C; }
    .tarjeta-titulo { margin: 4px 0 0; font-weight: 700; color: #1B1B1B; }
    .tarjeta a {
      display: inline-flex; align-items: center; gap: 4px; min-height: 44px;
      color: #14612C; font-weight: 600; font-size: 13px; text-decoration: underline;
    }
    .tarjeta a:hover { color: #0E4A21; }

    /* Botón de acción (Reintentar) */
    .accion {
      display: inline-flex; align-items: center; gap: 6px; margin-top: 10px;
      min-height: 44px; padding: 0 18px; border: 0; border-radius: 22px;
      background: #14612C; color: #FFFFFF; font-size: 14px; font-weight: 600;
      transition: background-color .15s;
    }
    .accion:hover { background: #0E4A21; }

    /* ¿Te fue útil? */
    .valoracion {
      display: flex; align-items: center; flex-wrap: wrap; gap: 4px;
      margin-top: 8px; font-size: 12.5px; color: #444444;
    }
    .valoracion-pregunta { margin-right: 4px; }
    .voto {
      width: 44px; height: 44px; display: grid; place-items: center;
      border: 1.5px solid #14612C; border-radius: 50%;
      background: #FFFFFF; color: #14612C; transition: background-color .15s;
    }
    .voto:hover:not(:disabled) { background: #EAF3E2; }
    .voto[aria-pressed="true"] { background: #14612C; color: #FFFFFF; }
    .voto:disabled { cursor: default; }
    .voto:disabled:not([aria-pressed="true"]) { border-color: #C3CFB8; color: #5F6F52; }
    .gracias { margin-left: 4px; color: #14612C; font-weight: 700; }

    /* Indicador de escritura */
    .escribiendo { display: flex; align-items: center; gap: 8px; color: #444444; font-size: 12.5px; }
    .puntos {
      display: inline-flex; gap: 4px; padding: 12px;
      background: #EEEEEE; border-radius: 4px 16px 16px 16px;
    }
    .puntos span {
      width: 7px; height: 7px; border-radius: 50%; background: #33691E;
      animation: rebote 1.2s infinite ease-in-out;
    }
    .puntos span:nth-child(2) { animation-delay: .15s; }
    .puntos span:nth-child(3) { animation-delay: .3s; }
    @keyframes rebote {
      0%, 80%, 100% { transform: translateY(0); opacity: .45; }
      40% { transform: translateY(-4px); opacity: 1; }
    }

    /* Sugerencias */
    .sugerencias { display: flex; flex-wrap: wrap; gap: 8px; padding-left: 36px; }
    .sugerencia {
      min-height: 44px; padding: 0 16px; border-radius: 22px;
      border: 1.5px solid #14612C; background: #FFFFFF;
      color: #14612C; font-size: 14px; font-weight: 600;
      transition: background-color .15s, color .15s;
    }
    .sugerencia:hover { border-color: #0E4A21; color: #0E4A21; background: #EAF3E2; }

    /* Campo de texto */
    .entrada { flex: none; padding: 10px 12px 12px; border-top: 1px solid #D5DCCB; }
    .aviso {
      display: flex; align-items: flex-start; gap: 6px; margin: 0 0 8px;
      font-size: 11.5px; line-height: 1.35; color: #444444;
    }
    .aviso .icono-chico { margin-top: 1px; }
    .fila-entrada { display: flex; align-items: center; gap: 8px; }
    .campo {
      flex: 1; min-width: 0; height: 44px; padding: 0 16px;
      border: 1.5px solid #5F6F52; border-radius: 22px;
      background: #FFFFFF; color: #1B1B1B;
      font-family: inherit; font-size: 14px;
    }
    .campo::placeholder { color: #444444; opacity: 1; }
    .campo:focus { outline: 3px solid #011A18; outline-offset: 1px; }
    .campo[aria-invalid="true"] { border-color: #8A1C12; }
    .campo:disabled { background: #F4F4F4; cursor: not-allowed; }
    .enviar {
      width: 44px; height: 44px; flex: none; display: grid; place-items: center;
      border: 0; border-radius: 50%; background: #14612C; color: #FFFFFF;
      transition: background-color .15s;
    }
    .enviar:hover:not(:disabled) { background: #0E4A21; }
    .enviar:disabled { background: #8FA383; cursor: not-allowed; }
    .error-campo { margin: 6px 4px 0; font-size: 12px; color: #8A1C12; }

    /* Móvil: pantalla completa y burbuja solo con el avatar */
    @media (max-width: 480px) {
      .ventana {
        top: 0; right: 0; bottom: 0; left: 0;
        width: auto; height: auto; max-width: none; max-height: none;
        border-radius: 0;
      }
      .burbuja-etiqueta { display: none; }
    }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation: none !important; transition: none !important; }
      .puntos span { opacity: .7; }
    }
  `;

  // --- Estado en memoria ----------------------------------------------------

  const estado = {
    enviando: false,
    abierto: false,
    temporizadorAuto: null,
  };
  let ui = null;

  // --- Utilidades del DOM ---------------------------------------------------

  // Crea un elemento con atributos y, opcionalmente, texto plano.
  function crear(etiqueta, atributos, texto) {
    const el = document.createElement(etiqueta);
    for (const [nombre, valor] of Object.entries(atributos || {})) {
      if (nombre === "clase") el.className = valor;
      else el.setAttribute(nombre, valor);
    }
    if (texto !== undefined) el.textContent = texto;
    return el;
  }

  // Devuelve un ícono SVG fijo (decorativo, oculto para lectores de pantalla).
  // Único uso de innerHTML: solo cadenas constantes de ICONOS.
  function icono(nombre, clase) {
    const plantilla = document.createElement("template");
    plantilla.innerHTML = SVG_INICIO + ICONOS[nombre] + "</svg>";
    const svg = plantilla.content.firstElementChild;
    svg.setAttribute("class", clase || "icono");
    return svg;
  }

  function imagenAvatar(clase) {
    return crear("img", { clase: clase, src: AVATAR, alt: "" });
  }

  function desplazarAlFinal() {
    ui.mensajes.scrollTop = ui.mensajes.scrollHeight;
  }

  // --- Preferencia de minimizado (lo único que se guarda) -------------------

  function leerMinimizado() {
    try {
      return window.localStorage.getItem(CLAVE_MINIMIZADO) === "1";
    } catch (e) {
      return false;
    }
  }

  function guardarMinimizado() {
    try {
      window.localStorage.setItem(CLAVE_MINIMIZADO, "1");
    } catch (e) {
      // Sin almacenamiento disponible: solo dura esta visita.
    }
  }

  // --- Construcción de la interfaz ------------------------------------------

  function construirBurbuja() {
    const boton = crear("button", { clase: "burbuja", type: "button", "aria-label": TEXTOS.abrir });
    boton.append(crear("span", { clase: "burbuja-etiqueta", "aria-hidden": "true" }, TEXTOS.burbuja),
      imagenAvatar("burbuja-avatar"));
    boton.addEventListener("click", () => abrir(true));
    return boton;
  }

  function construirEncabezado() {
    const encabezado = crear("div", { clase: "encabezado" });
    const textos = crear("div", { clase: "encabezado-textos" });
    textos.append(crear("p", { clase: "nombre" }, TEXTOS.nombre),
      crear("p", { clase: "subtitulo" }, TEXTOS.subtitulo));
    const minimizar = crear("button", { clase: "minimizar", type: "button", "aria-label": "Minimizar el chat" });
    minimizar.append(icono("minimizar"));
    minimizar.addEventListener("click", minimizarChat);
    encabezado.append(imagenAvatar("encabezado-avatar"), textos, minimizar);
    return { encabezado, minimizar };
  }

  function construirFranja() {
    const franja = crear("div", { clase: "franja", role: "status" });
    franja.append(icono("sinConexion", "icono-chico"), crear("span", {}, TEXTOS.franjaSinConexion));
    franja.hidden = true;
    return franja;
  }

  function construirEntrada() {
    const form = crear("form", { clase: "entrada", novalidate: "" });
    const aviso = crear("p", { clase: "aviso" });
    aviso.append(icono("info", "icono-chico"), crear("span", {}, TEXTOS.aviso));

    const fila = crear("div", { clase: "fila-entrada" });
    const etiqueta = crear("label", { clase: "sr", for: "titoai-campo" }, "Escribe tu pregunta");
    const campo = crear("input", {
      clase: "campo", id: "titoai-campo", type: "text", autocomplete: "off",
      placeholder: TEXTOS.placeholder, "aria-describedby": "titoai-error",
    });
    const enviar = crear("button", { clase: "enviar", type: "submit", "aria-label": "Enviar mensaje" });
    enviar.append(icono("enviar"));
    fila.append(etiqueta, campo, enviar);

    const error = crear("p", { clase: "error-campo", id: "titoai-error", "aria-live": "polite" });
    form.append(aviso, fila, error);
    form.addEventListener("submit", (evento) => {
      evento.preventDefault();
      enviarDesdeCampo();
    });
    campo.addEventListener("input", limpiarErrorCampo);
    return { form, campo, enviar, error };
  }

  function construirVentana() {
    const ventana = crear("section", { clase: "ventana", role: "dialog", "aria-label": "Chat de TiToAI" });
    const { encabezado, minimizar } = construirEncabezado();
    const franja = construirFranja();
    const mensajes = crear("div", { clase: "mensajes", role: "log", "aria-live": "polite" });
    const entrada = construirEntrada();
    ventana.append(encabezado, franja, mensajes, entrada.form);
    ventana.hidden = true;
    ventana.addEventListener("keydown", (evento) => {
      if (evento.key === "Escape") {
        evento.stopPropagation();
        minimizarChat();
      }
    });
    return { ventana, minimizar, franja, mensajes, ...entrada };
  }

  function construirSugerencias() {
    const contenedor = crear("div", { clase: "sugerencias" });
    for (const texto of SUGERENCIAS) {
      const boton = crear("button", { clase: "sugerencia", type: "button" }, texto);
      boton.addEventListener("click", () => enviarPregunta(texto));
      contenedor.append(boton);
    }
    return contenedor;
  }

  function montar() {
    const host = document.createElement("titoai-widget");
    const raizSombra = host.attachShadow({ mode: "open" });
    const estilo = document.createElement("style");
    estilo.textContent = ESTILOS;
    const raiz = crear("div", { clase: "raiz" });
    const burbuja = construirBurbuja();
    const partes = construirVentana();
    raiz.append(burbuja, partes.ventana);
    raizSombra.append(estilo, raiz);
    document.body.append(host);

    ui = { burbuja, ...partes };
    ui.sugerencias = construirSugerencias();
    agregarMensajeBot({ texto: TEXTOS.saludo });
    ui.mensajes.append(ui.sugerencias);

    actualizarConexion();
    window.addEventListener("online", actualizarConexion);
    window.addEventListener("offline", actualizarConexion);
    programarAperturaAutomatica();
  }

  // --- Abrir y minimizar ----------------------------------------------------

  // porPersona = true cuando la persona abrió el chat (no la apertura
  // automática): solo entonces se mueve el foco, para no quitárselo a la
  // página ni abrir el teclado del celular sin que lo pida.
  function abrir(porPersona) {
    clearTimeout(estado.temporizadorAuto);
    estado.abierto = true;
    ui.ventana.hidden = false;
    ui.burbuja.hidden = true;
    desplazarAlFinal();
    if (porPersona) enfocarEntrada();
  }

  function minimizarChat() {
    estado.abierto = false;
    ui.ventana.hidden = true;
    ui.burbuja.hidden = false;
    ui.burbuja.focus();
    guardarMinimizado();
  }

  function enfocarEntrada() {
    if (ui.campo.disabled) ui.minimizar.focus();
    else ui.campo.focus();
  }

  function programarAperturaAutomatica() {
    if (leerMinimizado() || !Number.isFinite(SEGUNDOS_AUTO) || SEGUNDOS_AUTO < 0) return;
    estado.temporizadorAuto = setTimeout(() => {
      if (!estado.abierto) abrir(false);
    }, SEGUNDOS_AUTO * 1000);
  }

  // --- Conexión -------------------------------------------------------------

  function actualizarConexion() {
    const enLinea = navigator.onLine;
    ui.franja.hidden = enLinea;
    ui.campo.disabled = !enLinea;
    ui.enviar.disabled = !enLinea;
    ui.campo.placeholder = enLinea ? TEXTOS.placeholder : TEXTOS.placeholderSinConexion;
  }

  // --- Mensajes -------------------------------------------------------------

  // Agrega un mensaje del bot y devuelve la burbuja para añadirle tarjetas
  // o botones. variante: "error" | "sin-conexion" | undefined.
  function agregarMensajeBot({ texto, variante }) {
    const fila = crear("div", { clase: "fila-bot" });
    const burbuja = crear("div", { clase: "burbuja-bot" + (variante ? " " + variante : "") });
    const contenido = crear("div", { clase: "contenido" });
    pintarTexto(contenido, texto);

    if (variante) {
      const filaEstado = crear("div", { clase: "estado" });
      filaEstado.append(icono(variante === "error" ? "advertencia" : "sinConexion"), contenido);
      burbuja.append(filaEstado);
    } else {
      burbuja.append(contenido);
    }
    fila.append(imagenAvatar("avatar-mini"), burbuja);
    ui.mensajes.append(fila);
    desplazarAlFinal();
    return { fila, burbuja };
  }

  function agregarMensajeUsuario(texto) {
    const fila = crear("div", { clase: "fila-usuario" });
    fila.append(crear("div", { clase: "burbuja-usuario" }, texto));
    ui.mensajes.append(fila);
    desplazarAlFinal();
    return fila;
  }

  function marcarNoEnviado(filaUsuario) {
    if (filaUsuario.querySelector(".no-enviado")) return;
    const nota = crear("div", { clase: "no-enviado" });
    nota.append(icono("alerta", "icono-chico"), crear("span", {}, "No enviado"));
    filaUsuario.append(nota);
  }

  function quitarNoEnviado(filaUsuario) {
    const nota = filaUsuario.querySelector(".no-enviado");
    if (nota) nota.remove();
  }

  // Convierte texto plano en párrafos y listas numeradas, sin usar HTML.
  function pintarTexto(contenedor, texto) {
    for (const bloque of dividirEnBloques(texto)) {
      if (bloque.tipo === "lista") {
        const lista = crear("ol");
        if (bloque.inicio !== 1) lista.start = bloque.inicio;
        for (const item of bloque.items) lista.append(textoConEnlaces(crear("li"), item));
        contenedor.append(lista);
      } else {
        contenedor.append(textoConEnlaces(crear("p"), bloque.texto));
      }
    }
  }

  // Agrega el texto al elemento convirtiendo en enlaces las direcciones
  // http(s):// y www. Todo se crea con nodos de texto, nunca como HTML.
  function textoConEnlaces(elemento, texto) {
    const patron = /(?:https?:\/\/|www\.)[^\s<>"']+/gi;
    let desde = 0;
    for (const coincidencia of texto.matchAll(patron)) {
      // La puntuación final (". , ; : ) !") no es parte de la dirección.
      const direccion = coincidencia[0].replace(/[.,;:!?)\]]+$/, "");
      const href = urlSegura(/^www\./i.test(direccion) ? "https://" + direccion : direccion);
      if (!href) continue;
      elemento.append(texto.slice(desde, coincidencia.index));
      const enlace = crear("a", { clase: "enlace-texto", href: href, target: "_blank", rel: "noopener noreferrer" },
        direccion);
      enlace.append(crear("span", { clase: "sr" }, " (se abre en una pestaña nueva)"));
      elemento.append(enlace);
      desde = coincidencia.index + direccion.length;
    }
    elemento.append(texto.slice(desde));
    return elemento;
  }

  // Agrupa las líneas: "1. ..." seguidas forman una lista; las líneas en
  // blanco separan párrafos; los demás saltos de línea se respetan.
  function dividirEnBloques(texto) {
    const bloques = [];
    let parrafo = [];
    let lista = null;
    const cerrarParrafo = () => {
      if (parrafo.length) bloques.push({ tipo: "parrafo", texto: parrafo.join("\n") });
      parrafo = [];
    };

    for (const linea of String(texto).replace(/\r\n?/g, "\n").split("\n")) {
      const numerada = /^\s*(\d{1,3})[.)]\s+(.+)$/.exec(linea);
      if (numerada) {
        cerrarParrafo();
        if (!lista) {
          lista = { tipo: "lista", inicio: Number(numerada[1]), items: [] };
          bloques.push(lista);
        }
        lista.items.push(numerada[2].trim());
      } else if (!linea.trim()) {
        cerrarParrafo();
      } else if (lista && !parrafo.length && /^\s+\S/.test(linea)) {
        // Línea con sangría: continúa el último paso de la lista.
        lista.items[lista.items.length - 1] += "\n" + linea.trim();
      } else {
        lista = null;
        parrafo.push(linea);
      }
    }
    cerrarParrafo();
    return bloques;
  }

  // Solo se aceptan enlaces absolutos http o https.
  function urlSegura(url) {
    try {
      const destino = new URL(String(url));
      return destino.protocol === "http:" || destino.protocol === "https:" ? destino.href : null;
    } catch (e) {
      return null;
    }
  }

  // tipo: "fuente" (Fuente oficial) o "canal" (Canal oficial).
  function crearTarjeta(fuente, tipo) {
    const esCanal = tipo === "canal";
    const tarjeta = crear("div", { clase: "tarjeta" });
    const etiqueta = crear("div", { clase: "tarjeta-etiqueta" });
    etiqueta.append(icono(esCanal ? "ubicacion" : "documento", "icono-chico"),
      crear("span", {}, esCanal ? "Canal oficial" : "Fuente oficial"));
    tarjeta.append(etiqueta, crear("p", { clase: "tarjeta-titulo" }, String(fuente.titulo || "")));

    const href = urlSegura(fuente.url);
    if (href) {
      const enlace = crear("a", { href: href, target: "_blank", rel: "noopener noreferrer" });
      const pdf = textoPdf(href);
      if (pdf) {
        enlace.append(crear("span", {}, pdf), icono("descargar", "icono-chico"));
      } else {
        enlace.append(crear("span", {}, esCanal ? "Ir al canal oficial" : "Ver fuente oficial"),
          icono("flecha", "icono-chico"),
          crear("span", { clase: "sr" }, " (se abre en una pestaña nueva)"));
      }
      tarjeta.append(enlace);
    }
    return tarjeta;
  }

  // Si el enlace es un PDF, devuelve el texto que avisa la descarga.
  function textoPdf(href) {
    const ruta = new URL(href).pathname.toLowerCase();
    if (!ruta.endsWith(".pdf")) return null;
    return ruta.includes("reglamento") ? "Descargar reglamento (PDF)" : "Descargar documento (PDF)";
  }

  function crearBotonReintentar(alHacerClic) {
    const boton = crear("button", { clase: "accion", type: "button" });
    boton.append(icono("reintentar", "icono-chico"), crear("span", {}, "Reintentar"));
    boton.addEventListener("click", alHacerClic);
    return boton;
  }

  function crearValoracion(idConsulta) {
    const contenedor = crear("div", { clase: "valoracion" });
    const pregunta = crear("span", { clase: "valoracion-pregunta" }, "¿Te fue útil?");
    const si = crear("button", { clase: "voto", type: "button", "aria-label": "Sí, me fue útil", "aria-pressed": "false" });
    const no = crear("button", { clase: "voto", type: "button", "aria-label": "No me fue útil", "aria-pressed": "false" });
    si.append(icono("pulgarArriba"));
    no.append(icono("pulgarAbajo"));
    const gracias = crear("span", { clase: "gracias", role: "status" });

    const votar = (util, boton) => {
      si.disabled = true;
      no.disabled = true;
      boton.setAttribute("aria-pressed", "true");
      gracias.textContent = "¡Gracias!";
      enviarValoracion(idConsulta, util);
    };
    si.addEventListener("click", () => votar(true, si));
    no.addEventListener("click", () => votar(false, no));
    contenedor.append(pregunta, si, no, gracias);
    return contenedor;
  }

  function mostrarEscribiendo() {
    const fila = crear("div", { clase: "fila-bot" });
    const indicador = crear("div", { clase: "escribiendo" });
    const puntos = crear("span", { clase: "puntos", "aria-hidden": "true" });
    puntos.append(crear("span"), crear("span"), crear("span"));
    indicador.append(puntos, crear("span", {}, TEXTOS.escribiendo));
    fila.append(imagenAvatar("avatar-mini"), indicador);
    ui.mensajes.append(fila);
    desplazarAlFinal();
    return fila;
  }

  // --- Envío de preguntas ---------------------------------------------------

  // Cuenta caracteres reales (un emoji = 1), como el backend.
  function validarPregunta(texto) {
    const largo = Array.from(texto).length;
    return largo >= MIN_CARACTERES && largo <= MAX_CARACTERES;
  }

  function mostrarErrorCampo(mensaje) {
    ui.error.textContent = mensaje;
    ui.campo.setAttribute("aria-invalid", "true");
  }

  function limpiarErrorCampo() {
    ui.error.textContent = "";
    ui.campo.removeAttribute("aria-invalid");
  }

  function enviarDesdeCampo() {
    const texto = ui.campo.value.trim();
    if (!validarPregunta(texto)) {
      mostrarErrorCampo(TEXTOS.longitud);
      ui.campo.focus();
      return;
    }
    if (enviarPregunta(texto)) ui.campo.value = "";
  }

  // Muestra la pregunta y la envía. Devuelve false si ya hay otra en curso.
  function enviarPregunta(texto) {
    if (estado.enviando) return false;
    limpiarErrorCampo();
    quitarSugerencias();
    const filaUsuario = agregarMensajeUsuario(texto);
    procesarPregunta(texto, filaUsuario);
    return true;
  }

  function quitarSugerencias() {
    if (!ui.sugerencias.isConnected) return;
    const teniaFoco = ui.sugerencias.contains(ui.ventana.getRootNode().activeElement);
    ui.sugerencias.remove();
    if (teniaFoco) enfocarEntrada();
  }

  async function procesarPregunta(texto, filaUsuario) {
    if (!navigator.onLine) {
      mostrarFallo(texto, filaUsuario, "sin-conexion");
      return;
    }
    estado.enviando = true;
    ui.enviar.disabled = true;
    const indicador = mostrarEscribiendo();
    try {
      mostrarRespuesta(await pedirRespuesta(texto));
    } catch (e) {
      mostrarFallo(texto, filaUsuario, navigator.onLine ? "error" : "sin-conexion");
    } finally {
      indicador.remove();
      estado.enviando = false;
      actualizarConexion();
    }
  }

  // POST /api/chat con tiempo máximo. Lanza un error si no hay respuesta 200
  // con el formato del contrato.
  async function pedirRespuesta(texto) {
    const control = new AbortController();
    const temporizador = setTimeout(() => control.abort(), TIEMPO_MAXIMO_MS);
    try {
      const respuesta = await fetch(API + "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pregunta: texto }),
        credentials: "omit",
        signal: control.signal,
      });
      if (respuesta.status !== 200) throw new Error("Estado " + respuesta.status);
      const datos = await respuesta.json();
      if (typeof datos.respuesta !== "string") throw new Error("Respuesta sin texto");
      return datos;
    } finally {
      clearTimeout(temporizador);
    }
  }

  function mostrarRespuesta(datos) {
    const { burbuja } = agregarMensajeBot({ texto: datos.respuesta });
    const fueraDeAlcance = datos.fuera_de_alcance === true;
    let fuentes = Array.isArray(datos.fuentes) ? datos.fuentes : [];
    if (fueraDeAlcance && !fuentes.length) fuentes = [CANAL];
    for (const fuente of fuentes) {
      if (fuente && typeof fuente === "object") {
        burbuja.append(crearTarjeta(fuente, fueraDeAlcance ? "canal" : "fuente"));
      }
    }
    if (Number.isInteger(datos.id_consulta)) burbuja.append(crearValoracion(datos.id_consulta));
    desplazarAlFinal();
  }

  // Error del servicio o sin conexión: marca la pregunta como no enviada y
  // ofrece reintentar con la misma pregunta.
  function mostrarFallo(texto, filaUsuario, variante) {
    marcarNoEnviado(filaUsuario);
    const esError = variante === "error";
    const mensaje = agregarMensajeBot({ texto: esError ? TEXTOS.error : TEXTOS.sinConexion, variante });
    mensaje.burbuja.append(crearBotonReintentar(() => reintentar(texto, filaUsuario, mensaje.fila)));
    if (esError) mensaje.burbuja.append(crearTarjeta(CANAL, "canal"));
    desplazarAlFinal();
  }

  function reintentar(texto, filaUsuario, filaFallo) {
    if (estado.enviando) return;
    filaFallo.remove();
    quitarNoEnviado(filaUsuario);
    enfocarEntrada();
    procesarPregunta(texto, filaUsuario);
  }

  // La valoración no es crítica: si falla, no se interrumpe a la persona.
  function enviarValoracion(idConsulta, util) {
    fetch(API + "/api/consultas/" + encodeURIComponent(idConsulta) + "/valoracion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ util: util }),
      credentials: "omit",
    }).catch(() => {});
  }

  // --- Inicio ---------------------------------------------------------------

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", montar);
  } else {
    montar();
  }
})();
