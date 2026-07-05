import { auth } from "./firebase-config.js";
import { onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";

const role = localStorage.getItem("role");
const email = localStorage.getItem("email");
if (!role) window.location.href = "login.html";

const MODULOS = {
  panel:   { icon: "🏠", label: "Panel de control",  roles: ["admin","admin_junior","editor","auditor"] },
  bloques: { icon: "🏢", label: "Gestión de bloques", roles: ["admin","admin_junior","editor"] },
  aulas:   { icon: "🚪", label: "Gestión de aulas",   roles: ["admin","admin_junior","editor"] },
  areas:   { icon: "🌐", label: "Áreas comunes",       roles: ["admin","admin_junior","editor"] },
  favoritos: { icon: "⭐", label: "Favoritos", roles: ["admin","admin_junior","auditor"] },
};

let moduloActivo = null;

function renderSidebar() {
  const nav = document.getElementById("sidebarNav");
  const disponibles = Object.entries(MODULOS).filter(([_, m]) => m.roles.includes(role));

  nav.innerHTML = disponibles.map(([id, m]) => `
    <div class="nav-item" data-id="${id}">
      <span class="nav-icon">${m.icon}</span> ${m.label}
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

onAuthStateChanged(auth, (user) => {
  if (!user) { window.location.href = "login.html"; return; }
  renderUserInfo();
  renderSidebar();
});