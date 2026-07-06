import { auth } from "./firebase-config.js";
import { onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";

onAuthStateChanged(auth, (user) => {
  if (!user) window.location.href = "login.html";
});

const inputNueva = document.getElementById("passwordNueva");
const requisitos = {
  len: (p) => p.length >= 8,
  upper: (p) => /[A-Z]/.test(p),
  lower: (p) => /[a-z]/.test(p),
  num: (p) => /[0-9]/.test(p),
  special: (p) => /[!@#$%^&*(),.?":{}|<>_\-]/.test(p)
};

inputNueva.addEventListener("input", () => {
  const val = inputNueva.value;
  for (const key in requisitos) {
    const cumplido = requisitos[key](val);
    const li = document.getElementById(`req-${key}`);
    li.style.color = cumplido ? "#2fd4d4" : "#9fb8c2";
  }
});

document.getElementById("cambiarForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorMsg = document.getElementById("errorMsg");
  const btn = document.getElementById("btnCambiar");
  errorMsg.textContent = "";
  btn.disabled = true;
  btn.textContent = "Guardando...";

  const passwordActual = document.getElementById("passwordActual").value;
  const passwordNueva = document.getElementById("passwordNueva").value;
  const passwordConfirmar = document.getElementById("passwordConfirmar").value;

  try {
    const idToken = await auth.currentUser.getIdToken();
    const res = await fetch("/api/cambiar-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken, passwordActual, passwordNueva, passwordConfirmar })
    });
    const data = await res.json();

    if (res.ok) {
      alert("Contraseña actualizada correctamente. Vuelve a iniciar sesión.");
      await signOut(auth);
      localStorage.clear();
      window.location.href = "login.html";
    } else {
      errorMsg.textContent = data.error || "Error al cambiar la contraseña";
      btn.disabled = false;
      btn.textContent = "Guardar nueva contraseña";
    }
  } catch (err) {
    errorMsg.textContent = "Error de conexión.";
    btn.disabled = false;
    btn.textContent = "Guardar nueva contraseña";
  }
});