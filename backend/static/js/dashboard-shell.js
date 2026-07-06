import { auth } from "./firebase-config.js";
import { onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";

const role = localStorage.getItem("role");
const email = localStorage.getItem("email");
if (!role) window.location.href = "login.html";

const MODULOS = {
  panel:        { icon: "ti-home",          label: "Panel de control",   roles: ["admin","admin_junior","editor","auditor"] },
  bloques:      { icon: "ti-building",      label: "Gestión de bloques", roles: ["admin","admin_junior","editor"] },
  aulas:        { icon: "ti-door",          label: "Gestión de aulas",   roles: ["admin","admin_junior","editor"] },
  areas:        { icon: "ti-map-pin",       label: "Áreas comunes",      roles: ["admin","admin_junior","editor"] },
  mapa:         { icon: "ti-map-2",         label: "Mapa de popularidad",roles: ["admin","admin_junior","auditor"] },
  favoritos:    { icon: "ti-star",          label: "Favoritos",          roles: ["admin","admin_junior","auditor"] },
  usuarios:     { icon: "ti-users",         label: "Usuarios (estudiantes)", roles: ["admin","admin_junior"] },
  admins:       { icon: "ti-shield-lock",   label: "Administradores",   roles: ["admin"] },
  auditoria:    { icon: "ti-file-text",     label: "Auditoría",         roles: ["admin","admin_junior","auditor"] },
  estadisticas: { icon: "ti-chart-bar",     label: "Estadísticas",      roles: ["admin","admin_junior"] },
  config:       { icon: "ti-settings",      label: "Configuración",     roles: ["admin"] },
};

let moduloActivo = null;

function renderSidebar() {
  const nav = document.getElementById("sidebarNav");
  const disponibles = Object.entries(MODULOS).filter(([_, m]) => m.roles.includes(role));

  nav.innerHTML = disponibles.map(([id, m]) => `
    <div class="nav-item" data-id="${id}">
      <i class="ti ${m.icon} nav-icon"></i> <span>${m.label}</span>
    </div>
  `).join("");

  nav.querySelectorAll(".nav-item").forEach(el => {
    el.addEventListener("click", () => cargarModulo(el.dataset.id));
  });

  if (disponibles.length) cargarModulo(disponibles[0][0]);
}

async function cargarModulo(id) {
  moduloActivo = id;

  document.querySelectorAll(".nav-item").forEach(n =>
    n.classList.toggle("active", n.dataset.id === id)
  );

  const contenido = document.getElementById("contenido");
  contenido.innerHTML = `<p style="color:#6b7280">Cargando...</p>`;

  try {
    const html = await fetch(`js/modulos/${id}.html`).then(r => r.text());
    contenido.innerHTML = html;

    const mod = await import(`./modulos/${id}.js?v=${Date.now()}`);
    if (mod.init) mod.init({ role, email, auth });
  } catch (err) {
    contenido.innerHTML = `<p style="color:#d33">No se pudo cargar este módulo.</p>`;
    console.error(`Error cargando módulo ${id}:`, err);
  }
}

function renderUserInfo() {
  document.getElementById("userName").textContent = email.split("@")[0];
  document.getElementById("userRoleLabel").textContent = role;
  document.getElementById("avatarInitials").textContent = email[0].toUpperCase();
}

window.logout = async function () {
  await signOut(auth);
  localStorage.clear();
  window.location.href = "login.html";
};

document.getElementById("hamburger").addEventListener("click", () => {
  document.getElementById("sidebar").classList.toggle("open");
});

onAuthStateChanged(auth, async (user) => {
  if (!user) { window.location.href = "login.html"; return; }

  const idToken = await user.getIdToken();
  const res = await fetch("/api/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken })
  });
  const data = await res.json();

  if (data.debe_cambiar_password) {
    window.location.href = "cambiar-password.html";
    return;
  }

  renderUserInfo();
  cargarPeriodoTopbar();
  renderSidebar();

  await obtenerDuracionSesion();
  iniciarMonitoreoInactividad();
});

async function cargarPeriodoTopbar() {
  try {
    const res = await fetch("/api/configuracion");
    const cfg = await res.json();
    document.getElementById("periodoActual").textContent = cfg.periodo_academico || "2026";
  } catch (err) {
    console.error("No se pudo cargar el periodo académico:", err);
  }
}

// ---------- Cierre de sesión automático por inactividad ----------
let duracionSesionMs = 60 * 60 * 1000; // valor por defecto: 60 min, se sobreescribe con la config real
let timerInactividad = null;
let timerAviso = null;

async function obtenerDuracionSesion() {
  try {
    const res = await fetch("/api/configuracion");
    const cfg = await res.json();
    const minutos = cfg.duracion_sesion_minutos || 60;
    duracionSesionMs = minutos * 60 * 1000;
  } catch (err) {
    console.error("No se pudo obtener la duración de sesión, se usa el valor por defecto (60 min)");
  }
}

function reiniciarTimerInactividad() {
  clearTimeout(timerInactividad);
  clearTimeout(timerAviso);

  // Aviso 1 minuto antes de cerrar sesión (si la duración es mayor a 1 min)
  const tiempoAviso = Math.max(duracionSesionMs - 60000, 0);
  timerAviso = setTimeout(() => {
    mostrarAvisoInactividad();
  }, tiempoAviso);

  timerInactividad = setTimeout(() => {
    cerrarSesionPorInactividad();
  }, duracionSesionMs);
}

function mostrarAvisoInactividad() {
  let aviso = document.getElementById("avisoInactividad");
  if (!aviso) {
    aviso = document.createElement("div");
    aviso.id = "avisoInactividad";
    aviso.style.position = "fixed";
    aviso.style.bottom = "20px";
    aviso.style.right = "20px";
    aviso.style.background = "#16233a";
    aviso.style.color = "#fff";
    aviso.style.padding = "14px 18px";
    aviso.style.borderRadius = "10px";
    aviso.style.fontSize = "13px";
    aviso.style.zIndex = "2000";
    aviso.style.boxShadow = "0 6px 20px rgba(0,0,0,.3)";
    aviso.innerHTML = `⏳ Tu sesión se cerrará por inactividad en 1 minuto.<br>Mueve el mouse para continuar.`;
    document.body.appendChild(aviso);
  }
  aviso.style.display = "block";
}

function ocultarAvisoInactividad() {
  const aviso = document.getElementById("avisoInactividad");
  if (aviso) aviso.style.display = "none";
}

async function cerrarSesionPorInactividad() {
  // Registra el cierre por inactividad en el log de auditoría
  try {
    const idToken = await auth.currentUser.getIdToken();
    await fetch("/api/logout-inactividad", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken })
    });
  } catch (err) {
    console.error("No se pudo registrar el cierre por inactividad:", err);
  }

  await signOut(auth);
  localStorage.clear();
  alert("Tu sesión se cerró automáticamente por inactividad.");
  window.location.href = "login.html";
}

function iniciarMonitoreoInactividad() {
  ["mousemove", "keydown", "click", "scroll", "touchstart"].forEach(evento => {
    document.addEventListener(evento, () => {
      ocultarAvisoInactividad();
      reiniciarTimerInactividad();
    });
  });
  reiniciarTimerInactividad();
}