const visitanteId = localStorage.getItem("visitante_id");
if (!visitanteId) window.location.href = "visitante.html";

window.salir = function () {
  localStorage.removeItem("visitante_id");
  window.location.href = "visitante.html";
};

let mapas = {};
let mapaActualKey = "campus_general";
let vistaActual = "favoritos"; // o "busquedas"
let idsMarcados = new Set(); // ids de espacios a resaltar en el mapa

async function cargarCoordenadas() {
  const res = await fetch("/js/mapas_coordenadas.json");
  mapas = await res.json();
}

async function renderFavoritos() {
  const cont = document.getElementById("contenidoVisitante");
  cont.innerHTML = `<p style="color:#6b7280">Cargando tus favoritos...</p>`;

  const res = await fetch(`/api/favoritos-visitante/${visitanteId}`);
  const favoritos = await res.json();

  idsMarcados = new Set(favoritos.map(f => f.id));
  vistaActual = "favoritos";

  if (!favoritos.length) {
    cont.innerHTML = `<p style="color:#6b7280">Aún no tienes favoritos guardados en la app móvil.</p>`;
  } else {
    cont.innerHTML = `
      <div class="chart-card">
        ${favoritos.map(f => `<div class="panel-row"><span>${f.id.replace(/_/g, " ")}</span></div>`).join("")}
      </div>
    `;
  }

  renderMapaVisitante();
}

async function renderBusquedas() {
  const cont = document.getElementById("contenidoVisitante");
  cont.innerHTML = `<p style="color:#6b7280">Cargando tus búsquedas...</p>`;

  const res = await fetch(`/api/busquedas-visitante/${visitanteId}`);
  const busquedas = await res.json();

  if (!busquedas.length) {
    cont.innerHTML = `<p style="color:#6b7280">No se encontraron búsquedas asociadas a tu ID (${visitanteId}). Esto es esperado si no existe relación entre tu sesión anónima y tu registro de estudiante.</p>`;
    return;
  }

  cont.innerHTML = `
    <div class="chart-card">
      ${busquedas.map(b => `<div class="panel-row"><span>${b.espacio_encontrado || b.termino || "—"}</span></div>`).join("")}
    </div>
  `;
}

document.getElementById("tabBuscados").addEventListener("click", () => {
  setTab("tabBuscados");
  renderBusquedas();
});

function renderMapaVisitante() {
  const items = mapas[mapaActualKey] || [];
  const svg = document.getElementById("mapaSvgVisitante");
  if (!svg) return;
  svg.innerHTML = "";

  const colorActivo = vistaActual === "favoritos" ? "#d4537e" : "#2563eb";

  for (const item of items) {
    const pad = 3;
    const rectX = item.x + pad;
    const rectY = item.y + pad;
    const rectW = Math.max(item.w - pad * 2, 10);
    const rectH = Math.max(item.h - pad * 2, 10);

    const estaMarcado = idsMarcados.has(item.id);

    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", rectX);
    rect.setAttribute("y", rectY);
    rect.setAttribute("width", rectW);
    rect.setAttribute("height", rectH);
    rect.setAttribute("rx", 5);
    rect.setAttribute("fill", estaMarcado ? colorActivo : "#e4e9f0");
    rect.setAttribute("fill-opacity", estaMarcado ? "0.55" : "1");
    rect.setAttribute("stroke", estaMarcado ? colorActivo : "#9aa8b8");
    rect.setAttribute("stroke-width", estaMarcado ? "2" : "1.2");
    rect.style.cursor = "pointer";
    rect.addEventListener("click", (e) => mostrarBurbujaVisitante(e, item, estaMarcado));
    svg.appendChild(rect);
  }
}

function mostrarBurbujaVisitante(evento, item, estaMarcado) {
  let burbuja = document.getElementById("burbujaMapaVisitante");
  if (!burbuja) {
    burbuja = document.createElement("div");
    burbuja.id = "burbujaMapaVisitante";
    burbuja.style.position = "fixed";
    burbuja.style.background = "#16233a";
    burbuja.style.color = "#fff";
    burbuja.style.padding = "8px 12px";
    burbuja.style.borderRadius = "8px";
    burbuja.style.fontSize = "12.5px";
    burbuja.style.pointerEvents = "none";
    burbuja.style.zIndex = "1000";
    burbuja.style.boxShadow = "0 4px 14px rgba(0,0,0,.25)";
    burbuja.style.whiteSpace = "nowrap";
    document.body.appendChild(burbuja);
  }

  const etiqueta = vistaActual === "favoritos" ? "favorito" : "búsqueda";
  burbuja.innerHTML = estaMarcado
    ? `<strong>${item.id.replace(/_/g, " ")}</strong><br>Es tu ${etiqueta}`
    : `<strong>${item.id.replace(/_/g, " ")}</strong><br>Sin marcar`;
  burbuja.style.left = `${evento.clientX + 14}px`;
  burbuja.style.top = `${evento.clientY - 10}px`;
  burbuja.style.display = "block";

  setTimeout(() => document.addEventListener("click", ocultarBurbujaVisitanteUnaVez), 0);
}

function ocultarBurbujaVisitanteUnaVez(e) {
  const burbuja = document.getElementById("burbujaMapaVisitante");
  if (burbuja && !e.target.closest("rect")) {
    burbuja.style.display = "none";
    document.removeEventListener("click", ocultarBurbujaVisitanteUnaVez);
  }
}

document.getElementById("tabFavoritos").addEventListener("click", () => {
  setTab("tabFavoritos");
  renderFavoritos();
});
// Ya no agregamos el listener de tabBuscados, o lo dejamos pero sin acción:
document.getElementById("tabBuscados").addEventListener("click", () => {
  // Deshabilitado: requiere relacionar uid_usuario (anónimo) con usuario_id real
});
document.getElementById("mapaSelectVisitante").addEventListener("change", (e) => {
  mapaActualKey = e.target.value;
  renderMapaVisitante();
});

function setTab(id) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.id === id));
}

(async function init() {
  await cargarCoordenadas();
  await renderFavoritos();
})();