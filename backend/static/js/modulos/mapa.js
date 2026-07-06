let ctx = null;
let mapas = {};
let mapaActualKey = "campus_general";
let rankingActual = {};

export async function init(contexto) {
  ctx = contexto;
  await cargarCoordenadas();
  await renderRanking();
  await renderRecientes();

  document.getElementById("mapaSelectBusquedas").addEventListener("change", (e) => {
    mapaActualKey = e.target.value;
    renderMapa();
  });

  renderMapa();
}

async function cargarCoordenadas() {
  const res = await fetch("/js/mapas_coordenadas.json");
  if (!res.ok) {
    console.error("No se pudo cargar mapas_coordenadas.json, status:", res.status);
    return;
  }
  mapas = await res.json();
  console.log("Mapas cargados:", Object.keys(mapas));
}

async function renderRanking() {
  const idToken = await ctx.auth.currentUser.getIdToken();
  const res = await fetch("/api/busquedas-ranking", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken })
  });
  const ranking = await res.json();
  console.log("Ranking de búsquedas:", ranking);

  rankingActual = {};
  ranking.forEach(r => rankingActual[r.espacio] = r.total);

  const cont = document.getElementById("rankingBusquedas");
  if (!ranking.length) {
    cont.innerHTML = `<p style="color:#6b7280;font-size:13px">Aún no hay búsquedas registradas.</p>`;
    return;
  }
  cont.innerHTML = ranking.map(r => `
    <div class="panel-row"><span>${r.espacio.replace(/_/g, " ")}</span><span style="color:#0a3d42;font-weight:600">${r.total} <i class="ti ti-search"></i></span></div>
  `).join("");
}

async function renderRecientes() {
  const idToken = await ctx.auth.currentUser.getIdToken();
  const res = await fetch("/api/busquedas-recientes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken, limite: 15 })
  });
  const recientes = await res.json();

  const cont = document.getElementById("listaBusquedasRecientes");
  if (!recientes.length) {
    cont.innerHTML = `<p style="color:#6b7280;font-size:13px">Sin búsquedas recientes.</p>`;
    return;
  }

  cont.innerHTML = recientes.map(b => `
    <div class="panel-row">
      <span>"${b.termino}" → ${(b.espacio_encontrado || "—").replace(/_/g, " ")}</span>
      <span style="color:#6b7280;font-size:11.5px">${formatFecha(b.timestamp)}</span>
    </div>
  `).join("");
}

function formatFecha(epochMs) {
  if (!epochMs) return "—";
  return new Date(epochMs).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" });
}

function radiusFor(v, maxV) {
  const minR = 5, maxR = 26;
  return minR + Math.sqrt(v / Math.max(maxV, 1)) * (maxR - minR);
}

function renderMapa() {
  const items = mapas[mapaActualKey] || [];
  const svg = document.getElementById("mapaSvgBusquedas");
  if (!svg) {
    console.error("No se encontró el elemento #mapaSvgBusquedas");
    return;
  }
  svg.innerHTML = "";

  if (!items.length) {
    console.warn(`No hay items para el mapa "${mapaActualKey}". Mapas disponibles:`, Object.keys(mapas));
    return;
  }

  const maxV = Math.max(...items.map(i => rankingActual[i.id] || 0), 1);

  for (const item of items) {
    const pad = 3;
    const rectX = item.x + pad;
    const rectY = item.y + pad;
    const rectW = Math.max(item.w - pad * 2, 10);
    const rectH = Math.max(item.h - pad * 2, 10);

    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", rectX);
    rect.setAttribute("y", rectY);
    rect.setAttribute("width", rectW);
    rect.setAttribute("height", rectH);
    rect.setAttribute("rx", 5);
    rect.setAttribute("fill", "#e4e9f0");
    rect.setAttribute("stroke", "#9aa8b8");
    rect.setAttribute("stroke-width", "1.2");
    svg.appendChild(rect);

    const cx = rectX + rectW / 2;
    const cy = rectY + rectH / 2;
    const valor = rankingActual[item.id] || 0;
    const r = radiusFor(valor, maxV);

    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", cx);
    circle.setAttribute("cy", cy);
    circle.setAttribute("r", r.toFixed(1));
    circle.setAttribute("fill", "#2fd4d4");
    circle.setAttribute("fill-opacity", "0.55");
    circle.setAttribute("stroke", "#0a3d42");
    circle.setAttribute("stroke-width", "1.5");
    circle.style.cursor = "pointer";
    circle.addEventListener("click", (e) => mostrarBurbuja(e, item, valor));
    svg.appendChild(circle);
  }
}

function mostrarBurbuja(evento, item, valor) {
  let burbuja = document.getElementById("burbujaMapaBusquedas");
  if (!burbuja) {
    burbuja = document.createElement("div");
    burbuja.id = "burbujaMapaBusquedas";
    burbuja.style.position = "fixed";
    burbuja.style.background = "#0a1e2a";
    burbuja.style.color = "#fff";
    burbuja.style.padding = "8px 12px";
    burbuja.style.borderRadius = "8px";
    burbuja.style.fontSize = "12.5px";
    burbuja.style.pointerEvents = "none";
    burbuja.style.zIndex = "1000";
    burbuja.style.boxShadow = "0 4px 14px rgba(0,0,0,.25)";
    burbuja.style.whiteSpace = "nowrap";
    burbuja.style.border = "1px solid #2fd4d4";
    document.body.appendChild(burbuja);
  }
  burbuja.innerHTML = `<strong>${item.id.replace(/_/g, " ")}</strong><br>${valor} búsqueda${valor === 1 ? "" : "s"}`;
  burbuja.style.left = `${evento.clientX + 14}px`;
  burbuja.style.top = `${evento.clientY - 10}px`;
  burbuja.style.display = "block";

  setTimeout(() => document.addEventListener("click", ocultarBurbujaUnaVez), 0);
}

function ocultarBurbujaUnaVez(e) {
  const burbuja = document.getElementById("burbujaMapaBusquedas");
  if (burbuja && !e.target.closest("circle")) {
    burbuja.style.display = "none";
    document.removeEventListener("click", ocultarBurbujaUnaVez);
  }
}