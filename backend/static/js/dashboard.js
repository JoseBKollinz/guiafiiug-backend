import { auth, db } from "./firebase-config.js";
import { onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";
import { collection, getDocs, collectionGroup } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js";

const role = localStorage.getItem("role");
const email = localStorage.getItem("email");
if (!role) window.location.href = "login.html";

// ... (todo tu MENU, STATS, renderMenu, renderStats, renderUserInfo, renderChart, renderTotalUsuarios, renderSidePanel se quedan igual) ...

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
    // aquí seguiría la función que dibuja el mapa (renderMapa), pendiente de agregar al HTML
  }
});