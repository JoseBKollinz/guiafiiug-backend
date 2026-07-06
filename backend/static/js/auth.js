import { auth } from "./firebase-config.js";
import { signInWithEmailAndPassword } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";

const form = document.getElementById("loginForm");
const errorMsg = document.getElementById("errorMsg");
const btn = document.getElementById("btnIngresar");

document.getElementById("togglePass").addEventListener("click", () => {
  const p = document.getElementById("password");
  p.type = p.type === "password" ? "text" : "password";
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorMsg.textContent = "";
  btn.disabled = true;
  btn.textContent = "Ingresando...";

  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;

  try {
    const cred = await signInWithEmailAndPassword(auth, email, password);
    const idToken = await cred.user.getIdToken();

    const res = await fetch("/api/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken })
    });

    if (!res.ok) throw new Error("No se pudo validar la sesión en el servidor");
    const data = await res.json();

    localStorage.setItem("role", data.role);
    localStorage.setItem("email", email);

    if (data.debe_cambiar_password) {
      window.location.href = "cambiar-password.html";
    } else {
      window.location.href = "dashboard.html";
    }

  } catch (err) {
    errorMsg.textContent = "Credenciales incorrectas o usuario no autorizado.";
    btn.disabled = false;
    btn.textContent = "Ingresar";
  }
});