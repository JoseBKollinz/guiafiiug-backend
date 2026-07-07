const form = document.getElementById("visitanteForm");
const errorMsg = document.getElementById("errorMsg");
const btn = document.getElementById("btnBuscar");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorMsg.textContent = "";
  btn.disabled = true;
  btn.textContent = "Verificando...";

  const cedula = document.getElementById("cedula").value.trim();
  const apellido = document.getElementById("apellido").value.trim();

  try {
    const res = await fetch("/api/buscar-usuario", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cedula, apellido })
    });

    if (!res.ok) {
      errorMsg.textContent = "No encontramos ningún registro con esos datos. Verifica tu cédula y apellido.";
      btn.disabled = false;
      btn.textContent = "Ver mis datos";
      return;
    }

    const data = await res.json();
    localStorage.setItem("visitante_id", data.id);
    window.location.href = "dashboard-visitante.html";

  } catch (err) {
    errorMsg.textContent = "Error de conexión. Intenta de nuevo.";
    btn.disabled = false;
    btn.textContent = "Ver mis datos";
  }
});