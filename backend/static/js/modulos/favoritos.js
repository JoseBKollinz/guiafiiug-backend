let ctx = null;   // ← esta línea faltaba
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
        const pad = 0;
        const rectX = item.x + pad;
        const rectY = item.y + pad;              // sin el Math.min ahora 
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
        circle.setAttribute("fill", "#2563eb");
        circle.setAttribute("fill-opacity", "0.55");
        circle.setAttribute("stroke", "#1d4ed8");
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

    burbuja.innerHTML = `<strong>${item.id.replace(/_/g, " ")}</strong><br>${valor} favorito${valor === 1 ? "" : "s"}`;
    burbuja.style.left = `${evento.clientX + 14}px`;
    burbuja.style.top = `${evento.clientY - 10}px`;
    burbuja.style.display = "block";

    // Oculta la burbuja si se hace clic en cualquier otro lugar
    setTimeout(() => {
        document.addEventListener("click", ocultarBurbujaUnaVez);
    }, 0);
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

    const cont = document.getElementById("rankingFavoritos");
    if (!ranking.length) {
        cont.innerHTML = `<p style="color:#6b7280;font-size:13px">Aún no hay favoritos registrados.</p>`;
        return;
    }
    cont.innerHTML = ranking.map(r => `
    <div class="panel-row"><span>${r.espacio.replace(/_/g, " ")}</span><span>${r.total} ❤️</span></div>
  `).join("");
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
    if (!select) return; // por si el HTML de este módulo no incluye el selector

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
    if (!cont) return;

    if (!favoritos.length) {
        cont.innerHTML = `<p style="color:#6b7280;font-size:13px">Este estudiante no tiene favoritos.</p>`;
        return;
    }

    cont.innerHTML = favoritos.map(f => `
    <div class="panel-row"><span>${f.id.replace(/_/g, " ")}</span></div>
  `).join("");
}