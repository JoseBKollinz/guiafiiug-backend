import { auth, db } from "./firebase-config.js";
import { onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";
import { collection, getDocs, collectionGroup } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js";

const role = localStorage.getItem("role");
const email = localStorage.getItem("email");
if (!role) window.location.href = "login.html";

// ---------- Configuración de menú por rol ----------
const MENU = {
  admin: [
    { id: "panel", icon: "🏠", label: "Panel de control" },
    { id: "gestion_bloques", icon: "🏢", label: "Gestión de bloques" },
    { id: "estadisticas", icon: "📊", label: "Estadísticas generales" },
    { id: "populares", icon: "🔥", label: "Espacios más buscados" },
    { id: "gestion", icon: "🏢", label: "Gestión de espacios" },
    { id: "auditoria", icon: "🛡️", label: "Auditoría" },
    { id: "config", icon: "⚙️", label: "Configuración" }
  ],
  admin_junior: [
    { id: "panel", icon: "🏠", label: "Panel de control" },
    { id: "gestion_bloques", icon: "🏢", label: "Gestión de bloques" },
    { id: "gestion", icon: "🏢", label: "Gestión de espacios" },
    { id: "populares", icon: "🔥", label: "Espacios más buscados" },
    { id: "auditoria", icon: "🛡️", label: "Auditoría" }
    // se irán agregando conforme construyamos cada módulo nuevo
  ],
  editor: [
    { id: "panel", icon: "🏠", label: "Panel de control" },
    { id: "gestion_bloques", icon: "🏢", label: "Gestión de bloques" },
    { id: "gestion", icon: "🏢", label: "Gestión de espacios" }
  ],
  auditor: [
    { id: "panel", icon: "🏠", label: "Panel de control" },
    { id: "populares", icon: "🔥", label: "Espacios más buscados" },
    { id: "auditoria", icon: "🛡️", label: "Auditoría" }
  ],
  visitante: [
    { id: "panel", icon: "🏠", label: "Panel de control" },
    { id: "publico", icon: "🌐", label: "Espacios disponibles" }
  ]
};

// ---------- Tarjetas de stats por rol ----------
const STATS = {
  admin: [
    { icon: "🏢", bg: "#e0edff", value: "—", label: "Total de espacios", key: "totalEspacios" },
    { icon: "👥", bg: "#e3f8ec", value: "—", label: "Usuarios registrados", key: "totalUsuarios" },
    { icon: "⭐", bg: "#fff0e0", value: "—", label: "Total favoritos", key: "totalFavoritos" },
    { icon: "🔔", bg: "#fde8e8", value: "0", label: "Alertas hoy", key: "alertas" }
  ],
  editor: [
    { icon: "🏢", bg: "#e0edff", value: "—", label: "Espacios a tu cargo", key: "totalEspacios" },
    { icon: "🛠️", bg: "#fff4e0", value: "0", label: "Ediciones esta semana", key: "ediciones" }
  ],
  auditor: [
    { icon: "👥", bg: "#e3f8ec", value: "—", label: "Usuarios registrados", key: "totalUsuarios" },
    { icon: "🛡️", bg: "#fde8e8", value: "—", label: "Eventos de auditoría", key: "eventos" }
  ],
  visitante: [
    { icon: "🏢", bg: "#e0edff", value: "—", label: "Espacios disponibles", key: "disponibles" }
  ]
};

// ---------- Mapa de popularidad de espacios ----------
let mapas = {};
let datosReales = { busquedas: {}, favoritos: {} };

async function cargarCoordenadas() {
  const res = await fetch("/js/mapas_coordenadas.json");
  mapas = await res.json();
}

async function cargarPopularidad(idToken) {
  const res = await fetch("/api/popularidad-espacios", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken })
  });
  datosReales = await res.json();
}
// ---------- Render de sidebar ----------
function renderMenu() {
  const nav = document.getElementById("sidebarNav");
  const items = MENU[role] || [];
  nav.innerHTML = items.map((it, i) => `
    <div class="nav-item ${i === 0 ? "active" : ""}" data-id="${it.id}">
      <span class="nav-icon">${it.icon}</span> ${it.label}
    </div>
  `).join("");

  nav.querySelectorAll(".nav-item").forEach(el => {
    el.addEventListener("click", () => {
      nav.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
      el.classList.add("active");
      // Aquí luego puedes cambiar de vista/sección según el data-id
    });
  });
}

// ---------- Render de stat cards ----------
function renderStats() {
  const grid = document.getElementById("statsGrid");
  const cards = STATS[role] || [];
  grid.innerHTML = cards.map(c => `
    <div class="stat-card">
      <div class="stat-icon" style="background:${c.bg}">${c.icon}</div>
      <div>
        <div class="stat-value" data-key="${c.key}">${c.value}</div>
        <div class="stat-label">${c.label}</div>
      </div>
    </div>
  `).join("");
}

// ---------- Datos de usuario en topbar ----------
function renderUserInfo() {
  document.getElementById("userName").textContent = email.split("@")[0];
  document.getElementById("userRoleLabel").textContent = role;
  document.getElementById("avatarInitials").textContent = email[0].toUpperCase();
  document.getElementById("heroName").textContent = email.split("@")[0];

  const subtitles = {
    admin: "Tienes acceso completo al sistema.",
    editor: "Gestiona los espacios a tu cargo.",
    auditor: "Supervisa accesos y cambios del sistema.",
    visitante: "Consulta los espacios disponibles."
  };
  document.getElementById("heroSubtitle").textContent = subtitles[role] || "";
}

// ---------- Gráfico de espacios por tipo (Firestore real) ----------
let mapaActualKey = "campus_general";
let metricaActual = "favoritos";

function radiusFor(v, maxV) {
  const minR = 5, maxR = 26;
  return minR + Math.sqrt(v / Math.max(maxV, 1)) * (maxR - minR);
}

function renderMapa() {
  const items = mapas[mapaActualKey] || [];
  const svg = document.getElementById("mapaSvg");
  svg.innerHTML = "";

  const conteo = datosReales[metricaActual] || {};
  const maxV = Math.max(...items.map(i => conteo[i.id] || 0), 1);

  for (const item of items) {
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", item.x);
    rect.setAttribute("y", Math.min(item.y, 380));
    rect.setAttribute("width", item.w);
    rect.setAttribute("height", item.h);
    rect.setAttribute("rx", 4);
    rect.setAttribute("fill", "#f3f5f8");
    rect.setAttribute("stroke", "#dde3ea");
    rect.setAttribute("stroke-width", "0.5");
    rect.style.cursor = "pointer";
    rect.addEventListener("click", () => mostrarInfoEspacio(item.id));
    svg.appendChild(rect);

    const cx = item.x + item.w / 2;
    const cy = Math.min(item.y, 380) + item.h / 2;
    const valor = conteo[item.id] || 0;
    const r = radiusFor(valor, maxV);

    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", cx);
    circle.setAttribute("cy", cy);
    circle.setAttribute("r", r.toFixed(1));
    circle.setAttribute("fill", metricaActual === "favoritos" ? "#d4537e" : "#d85a30");
    circle.setAttribute("fill-opacity", "0.4");
    circle.setAttribute("stroke", metricaActual === "favoritos" ? "#d4537e" : "#d85a30");
    circle.setAttribute("stroke-width", "1");
    circle.style.cursor = "pointer";
    circle.addEventListener("click", () => mostrarInfoEspacio(item.id));
    svg.appendChild(circle);
  }
}

function mostrarInfoEspacio(id) {
  const nombre = id.replace(/_/g, " ").trim();
  const busquedas = (datosReales.busquedas || {})[id] || 0;
  const favoritos = (datosReales.favoritos || {})[id] || 0;
  document.getElementById("mapaInfo").textContent = `${nombre}: ${busquedas} búsquedas, ${favoritos} favoritos`;
}

function initMapaControles() {
  document.getElementById("mapaSelect").addEventListener("change", (e) => {
    mapaActualKey = e.target.value;
    renderMapa();
  });
  document.querySelectorAll('input[name="metricaMapa"]').forEach(radio => {
    radio.addEventListener("change", (e) => {
      metricaActual = e.target.value;
      renderMapa();
    });
  });
}
// ---------- Gráfico de espacios más favoriteados (dato real desde Firestore) ----------
async function renderChart() {
  const snap = await getDocs(collectionGroup(db, "favoritos"));

  const conteo = {};
  snap.forEach(doc => {
    const bloque = doc.id; // ej: "Bloque_D"
    conteo[bloque] = (conteo[bloque] || 0) + 1;
  });

  const ordenado = Object.entries(conteo).sort((a, b) => b[1] - a[1]);
  const labels = ordenado.map(e => e[0]);
  const data = ordenado.map(e => e[1]);

  new Chart(document.getElementById("espaciosChart"), {
    type: "bar",
    data: {
      labels: labels.length ? labels : ["Aún no hay favoritos registrados"],
      datasets: [{
        data: data.length ? data : [0],
        backgroundColor: "#e08a3c",
        borderRadius: 6
      }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
    }
  });

  // Actualiza el stat card correspondiente
  const totalEl = document.querySelector('[data-key="totalFavoritos"]');
  if (totalEl) totalEl.textContent = snap.size;

  return ordenado; // lo reusamos para el panel lateral (top 3)
}

// ---------- Total de usuarios registrados (colección "usuarios") ----------
async function renderTotalUsuarios() {
  const snap = await getDocs(collection(db, "usuarios"));
  const totalEl = document.querySelector('[data-key="totalUsuarios"]');
  if (totalEl) totalEl.textContent = snap.size;
}

// ---------- Panel lateral con ranking real de favoritos ----------
function renderSidePanel(ranking = []) {
  const panel = document.getElementById("sidePanel");

  if (role === "admin" || role === "auditor") {
    const top3 = ranking.slice(0, 3);
    panel.innerHTML = `
      <h3>⭐ Top espacios favoritos</h3>
      ${top3.length ? top3.map(([bloque, count]) => `
        <div class="panel-row"><span>${bloque}</span><span>${count} ❤️</span></div>
      `).join("") : `<div class="panel-row"><span>Sin datos aún</span></div>`}
    `;
  } else {
    panel.innerHTML = `
      <h3>ℹ️ Información</h3>
      <div class="panel-row"><span>Sistema</span><span>Operativo</span></div>
    `;
  }
}
// ---------- Logout ----------
window.logout = async function () {
  await signOut(auth);
  localStorage.clear();
  window.location.href = "login.html";
};

// ---------- Hamburger (mobile) ----------
document.getElementById("hamburger").addEventListener("click", () => {
  document.getElementById("sidebar").classList.toggle("open");
});

// ---------- Init ----------
onAuthStateChanged(auth, async (user) => {
  if (!user) { window.location.href = "login.html"; return; }

  renderMenu();
  renderStats();
  renderUserInfo();
  renderTotalUsuarios();

  try {
    const ranking = await renderChart();
    renderSidePanel(ranking);
  } catch (err) {
    console.error("Error cargando favoritos/gráfico:", err);
    renderSidePanel([]);
  }

  if (role === "admin" || role === "auditor") {
    const idToken = await user.getIdToken();
    await cargarCoordenadas();
    await cargarPopularidad(idToken);

    document.getElementById("mapaCard").style.display = "block";
    initMapaControles();
    renderMapa();
  }
});