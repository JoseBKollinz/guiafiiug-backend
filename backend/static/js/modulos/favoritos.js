let ctx = null;
let mapas = {};
let mapaActualKey = "campus_general";
let rankingActual = {};

export async function init(contexto) {
  ctx = contexto;
  await renderRanking();
  await cargarEstudiantes();
  await cargarCoordenadas();
  document.getElementById("mapaSelect").addEventListener("change", (e) => {
    mapaActualKey = e.target.value;
    renderMapa();
  });
  renderMapa();
}

async function cargarCoordenadas() {
  const res = await fetch("/js/mapas_coordenadas.json");
  mapas = await res.json();
}

function radiusFor(v, maxV) {
  const minR = 5, maxR = 26;
  return minR + Math.sqrt(v / Math.max(maxV, 1)) * (maxR - minR);
}

function renderMapa() {
  const items = mapas[mapaActualKey] || [];
  const svg = document.getElementById("mapaSvg");
  svg.innerHTML = "";

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
    circle.setAttribute("fill", "#17b8c4");
    circle.setAttribute("fill-opacity", "0.55");
    circle.setAttribute("stroke", "#0a3d42");
    circle.setAttribute("stroke-width", "1.5");
    circle.style.cursor = "pointer";
    circle.addEventListener("click", (e) => mostrarBurbuja(e, item, valor));
    svg.appendChild(circle);
  }
}

function mostrarBurbuja(evento, item, valor) {
  let burbuja = document.getElementById("burbujaMapa");
  if (!burbuja) {
    burbuja = document.createElement("div");
    burbuja.id = "burbujaMapa";
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
  burbuja.innerHTML = `<strong>${item.id.replace(/_/g, " ")}</strong><br>${valor} favorito${valor === 1 ? "" : "s"}`;
  burbuja.style.left = `${evento.clientX + 14}px`;
  burbuja.style.top = `${evento.clientY - 10}px`;
  burbuja.style.display = "block";

  setTimeout(() => document.addEventListener("click", ocultarBurbujaUnaVez), 0);
}

function ocultarBurbujaUnaVez(e) {
  const burbuja = document.getElementById("burbujaMapa");
  if (burbuja && !e.target.closest("circle")) {
    burbuja.style.display = "none";
    document.removeEventListener("click", ocultarBurbujaUnaVez);
  }
}

async function renderRanking() {
  const idToken = await ctx.auth.currentUser.getIdToken();
  const res = await fetch("/api/favoritos-ranking", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken })
  });
  const ranking = await res.json();

  rankingActual = {};
  ranking.forEach(r => rankingActual[r.espacio] = r.total);

  const totalFavoritos = ranking.reduce((sum, r) => sum + r.total, 0);
  const espacioTop = ranking[0];

  document.getElementById("favoritosStats").innerHTML = `
    <div class="stat-card">
      <div class="stat-icon"><i class="ti ti-star"></i></div>
      <div><div class="stat-value">${totalFavoritos}</div><div class="stat-label">Total de favoritos</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon"><i class="ti ti-map-pin"></i></div>
      <div><div class="stat-value">${ranking.length}</div><div class="stat-label">Espacios distintos</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon"><i class="ti ti-trophy"></i></div>
      <div><div class="stat-value" style="font-size:14px">${espacioTop ? espacioTop.espacio.replace(/_/g," ") : "—"}</div><div class="stat-label">Más favoriteado</div></div>
    </div>
  `;

  const top5 = ranking.slice(0, 5);
  const cont = document.getElementById("rankingFavoritos");
  cont.innerHTML = top5.length
    ? top5.map((r, i) => `<div class="panel-row"><span>#${i+1} ${r.espacio.replace(/_/g, " ")}</span><span style="color:#0a3d42;font-weight:600">${r.total} <i class="ti ti-heart"></i></span></div>`).join("")
    : `<p style="color:#6b7280;font-size:13px">Aún no hay favoritos registrados.</p>`;

  const tablaCont = document.getElementById("tablaRankingCompletoFav");
  tablaCont.innerHTML = ranking.map((r, i) => `
    <div class="panel-row"><span>#${i+1} ${r.espacio.replace(/_/g, " ")}</span><span>${r.total}</span></div>
  `).join("") || `<p style="color:#6b7280;font-size:13px">Sin datos.</p>`;
}

async function cargarEstudiantes() {
  const idToken = await ctx.auth.currentUser.getIdToken();
  const res = await fetch("/api/usuarios", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken })
  });
  const estudiantes = await res.json();

  const select = document.getElementById("selectEstudiante");
  if (!select) return;

  select.innerHTML = `<option value="">Selecciona un estudiante</option>` +
    estudiantes.map(e => `<option value="${e.id || e.cedula}">${e.nombre} ${e.apellido}</option>`).join("");

  select.addEventListener("change", () => {
    if (select.value) renderFavoritosEstudiante(select.value);
  });
}

async function renderFavoritosEstudiante(estudianteId) {
  const idToken = await ctx.auth.currentUser.getIdToken();
  const res = await fetch(`/api/favoritos-por-estudiante/${estudianteId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken })
  });
  const favoritos = await res.json();

  const cont = document.getElementById("favoritosEstudiante");
  if (!favoritos.length) {
    cont.innerHTML = `<p style="color:#6b7280;font-size:13px">Este estudiante no tiene favoritos.</p>`;
    return;
  }

  cont.innerHTML = favoritos.map(f => `
    <div class="panel-row"><span>${f.id.replace(/_/g, " ")}</span></div>
  `).join("");
}