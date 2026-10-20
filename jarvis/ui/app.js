"use strict";
// HUD de Jarvis. Todo texto entra con textContent (nada de HTML dinamico): correos y eventos son datos externos.
// ponytail: sin tests automaticos de comportamiento; mejorarlo con jsdom si la pagina crece.

const $ = (id) => document.getElementById(id);
const ESTADOS = { "reposo": "En reposo", "escuchando": "Escuchando", "pensando": "Pensando", "hablando": "Hablando" };
const QUIEN = { "usuario": "Tú", "jarvis": "Jarvis", "aviso": "Aviso", "sistema": "Sistema" };
const COLORES = { "reposo": "#29f0ff", "escuchando": "#3dffb0", "pensando": "#ffb02e", "hablando": "#7af7ff" };
const GRIS = "#8a949a";
const PARTE = "/hoy"; // el parte del día: se envía como un mensaje más
const MAX_NODOS = 50;

// Token: viaja en el fragmento de la URL (no llega al servidor ni a logs); se guarda solo en esta pestana.
const TOKEN = location.hash.slice(1) || sessionStorage.getItem("jarvis_token") || "";
if (TOKEN) {
  sessionStorage.setItem("jarvis_token", TOKEN);
  history.replaceState(null, "", location.pathname);
}

let ultimo = 0;
let estado = "reposo";
let conVoz = false;
let desconectado = false;
let hablandoHasta = 0;
let confirmacionId = null;
let confirmacionHasta = 0;

async function api(metodo, ruta, cuerpo) {
  const cabeceras = { "X-Jarvis-Token": TOKEN };
  const opciones = { method: metodo, cache: "no-store", headers: cabeceras };
  if (metodo === "POST") {
    cabeceras["Content-Type"] = "application/json";
    opciones.body = JSON.stringify(cuerpo);
  }
  const respuesta = await fetch(ruta, opciones);
  let datos = {};
  try { datos = await respuesta.json(); } catch (e) { datos = {}; }
  return { status: respuesta.status, datos: datos };
}

function mostrarConexion(texto) {
  $("aviso-conexion").textContent = texto;
  $("aviso-conexion").hidden = !texto;
}

// ---- Subtitulos ----
function agregarMensaje(m) {
  const fila = document.createElement("div");
  fila.className = "mensaje " + (QUIEN[m.quien] ? m.quien : "sistema");
  const quien = document.createElement("span");
  quien.className = "quien";
  quien.textContent = QUIEN[m.quien] || "Sistema";
  const cuerpo = document.createElement("span");
  cuerpo.className = "cuerpo";
  cuerpo.textContent = String(m.texto);
  fila.append(quien, cuerpo);
  const lista = $("subtitulos");
  lista.append(fila);
  while (lista.children.length > MAX_NODOS) lista.firstChild.remove();
  lista.scrollTop = lista.scrollHeight;
  if (m.quien === "jarvis" || m.quien === "aviso") {
    hablandoHasta = Date.now() + Math.min(6000, 40 * String(m.texto).length);
  }
}

// ---- Estado visual ----
function estadoVisible() {
  if (estado !== "reposo" || conVoz) return estado;
  // Sin voz el servidor solo conoce reposo y pensando: aqui se simulan los otros dos, solo como efecto visual.
  if (Date.now() < hablandoHasta) return "hablando";
  if (document.activeElement === $("texto") && $("texto").value !== "") return "escuchando";
  return "reposo";
}

function pintarEstado() {
  const visible = estadoVisible();
  document.body.className = desconectado ? "desconectado" : visible;
  $("panel").dataset.estado = visible;
  $("estado").textContent = desconectado ? "Sin conexión" : ESTADOS[visible];
}

function aplicarEstado(datos) {
  estado = ESTADOS[datos.estado] ? datos.estado : "reposo";
  conVoz = datos.voz === true;
  const ocupado = datos.ocupado === true;
  $("texto").disabled = ocupado;
  $("enviar").disabled = ocupado;
  if (!ocupado && !$("texto").disabled && document.activeElement === document.body && !confirmacionId) {
    $("texto").focus();
  }
}

// ---- Confirmacion (nunca hay un "si" por defecto) ----
function mostrarConfirmacion(c) {
  confirmacionId = c.id;
  confirmacionHasta = Date.now() + c.segundos * 1000;
  $("confirmacion-texto").textContent = String(c.texto);
  $("si").disabled = false;
  $("no").disabled = false;
  $("confirmacion").hidden = false;
  actualizarCuenta();
  $("no").focus();
}

function ocultarConfirmacion() {
  confirmacionId = null;
  $("confirmacion").hidden = true;
  $("texto").focus();
}

function actualizarCuenta() {
  if (confirmacionId === null) return;
  const restan = Math.max(0, Math.ceil((confirmacionHasta - Date.now()) / 1000));
  $("confirmacion-cuenta").textContent = "Se cancela solo en " + restan + " s";
}

async function responder(si) {
  if (confirmacionId === null || $("no").disabled) return;
  $("si").disabled = true;
  $("no").disabled = true;
  try {
    await api("POST", "/api/confirmar", { id: confirmacionId, si: si });
  } catch (e) {
    mostrarConexion("Sin conexión con Jarvis (¿cerraste la consola?)");
  }
}

// ---- Sondeo cada 500 ms (cadena de setTimeout: nunca se solapan) ----
async function sondear() {
  let espera = 500;
  try {
    const r = await api("GET", "/api/estado?desde=" + ultimo);
    if (r.status !== 200) throw new Error("estado " + r.status);
    desconectado = false;
    mostrarConexion("");
    const d = r.datos;
    for (const m of d.mensajes || []) {
      if (m.id > ultimo) agregarMensaje(m);
    }
    if (typeof d.ultimo === "number") ultimo = d.ultimo;
    aplicarEstado(d);
    if (d.confirmacion && d.confirmacion.id !== confirmacionId) mostrarConfirmacion(d.confirmacion);
    else if (!d.confirmacion && confirmacionId !== null) ocultarConfirmacion();
  } catch (e) {
    desconectado = true;
    mostrarConexion("Sin conexión con Jarvis (¿cerraste la consola?)");
    espera = 2000;
  }
  pintarEstado();
  setTimeout(sondear, espera);
}

// ---- Envio ----
async function enviar(texto) {
  $("nota").textContent = "";
  try {
    const r = await api("POST", "/api/mensaje", { texto: texto });
    if (r.status === 202) return true;
    $("nota").textContent = r.status === 409 ? "Jarvis está ocupado; espera a que termine." : String(r.datos.error || "No se pudo enviar.");
  } catch (e) {
    $("nota").textContent = "Sin conexión con Jarvis.";
  }
  return false;
}

// ---- Panel del dia ----
async function cargarHoy() {
  try {
    const r = await api("GET", "/api/hoy");
    if (r.status !== 200) return;
    $("titulo-hoy").textContent = String(r.datos.titulo);
    const contenedor = $("secciones");
    contenedor.replaceChildren();
    for (const s of r.datos.secciones || []) {
      const h = document.createElement("h3");
      h.textContent = String(s.titulo);
      const pre = document.createElement("pre");
      pre.textContent = String(s.texto);
      if (String(s.texto).startsWith("No disponible")) pre.className = "no-disponible";
      contenedor.append(h, pre);
    }
  } catch (e) {
    // el aviso de desconexion ya lo da el sondeo
  }
}

// ---- Canvas ----
const lienzo = $("nucleo");
const ctx = lienzo.getContext("2d");
const reducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const barras = new Array(64).fill(0);
const LADO = 360;

function escalar() {
  const dpr = window.devicePixelRatio || 1;
  lienzo.width = Math.round(LADO * dpr);
  lienzo.height = Math.round(LADO * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function dibujar(ms) {
  const visible = desconectado ? "desconectado" : estadoVisible();
  const color = desconectado ? GRIS : COLORES[visible];
  const t = (ms / 1000) * (reducido ? 0.2 : 1);
  const c = LADO / 2;
  ctx.clearRect(0, 0, LADO, LADO);
  ctx.lineCap = "butt";
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = 8;

  // anillo exterior: 60 marcas que giran despacio
  ctx.lineWidth = 2;
  for (let i = 0; i < 60; i++) {
    const a = (i / 60) * Math.PI * 2 + t * 0.15;
    const largo = i % 5 === 0 ? 12 : 6;
    ctx.beginPath();
    ctx.moveTo(c + Math.cos(a) * 168, c + Math.sin(a) * 168);
    ctx.lineTo(c + Math.cos(a) * (168 - largo), c + Math.sin(a) * (168 - largo));
    ctx.stroke();
  }

  // tres arcos concentricos a velocidades distintas (rapidos y discontinuos al pensar)
  const pensando = visible === "pensando";
  const velocidad = pensando ? 3 : 1;
  const radios = [140, 120, 100];
  const giros = [0.6, -0.9, 1.3];
  ctx.lineWidth = 3;
  for (let k = 0; k < 3; k++) {
    ctx.setLineDash(pensando ? [18, 14] : []);
    const inicio = t * giros[k] * velocidad;
    ctx.beginPath();
    ctx.arc(c, c, radios[k], inicio, inicio + Math.PI * (1.2 - k * 0.2));
    ctx.stroke();
  }
  ctx.setLineDash([]);

  // barras alrededor del nucleo al escuchar y al hablar
  if ((visible === "escuchando" || visible === "hablando") && !reducido) {
    const grande = visible === "hablando" ? 34 : 14;
    ctx.lineWidth = 2;
    for (let i = 0; i < barras.length; i++) {
      barras[i] += (Math.random() * grande - barras[i]) * 0.2;
      const a = (i / barras.length) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(c + Math.cos(a) * 62, c + Math.sin(a) * 62);
      ctx.lineTo(c + Math.cos(a) * (62 + 4 + barras[i]), c + Math.sin(a) * (62 + 4 + barras[i]));
      ctx.stroke();
    }
  }

  // nucleo con degradado radial que late (~4 Hz al hablar)
  const frecuencia = visible === "hablando" ? 4 : 0.6;
  const latido = 1 + 0.08 * Math.sin(t * Math.PI * 2 * frecuencia);
  const r = 46 * latido;
  const grad = ctx.createRadialGradient(c, c, 2, c, c, r);
  grad.addColorStop(0, "#ffffff");
  grad.addColorStop(0.35, color);
  grad.addColorStop(1, "rgba(0, 0, 0, 0)");
  ctx.shadowBlur = 20;
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(c, c, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;

  requestAnimationFrame(dibujar);
}

// ---- Arranque ----
$("formulario").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const texto = $("texto").value.trim();
  if (!texto) return;
  if (await enviar(texto)) $("texto").value = "";
});
$("parte").addEventListener("click", () => { enviar(PARTE); });
$("actualizar").addEventListener("click", cargarHoy);
$("si").addEventListener("click", () => responder(true));
$("no").addEventListener("click", () => responder(false));
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && confirmacionId !== null) responder(false);
});

escalar();
requestAnimationFrame(dibujar);
if (!TOKEN) {
  mostrarConexion("Falta el token: abre Jarvis con python -m jarvis --ui");
} else {
  setInterval(actualizarCuenta, 1000);
  setInterval(cargarHoy, 5 * 60 * 1000);
  cargarHoy();
  sondear();
}
