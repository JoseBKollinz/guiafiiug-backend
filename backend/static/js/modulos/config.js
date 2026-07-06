let ctx = null;

export async function init(contexto) {
  ctx = contexto;
  document.getElementById("btnGuardarConfig").addEventListener("click", guardarConfiguracion);
  await cargarConfiguracion();
}

async function cargarConfiguracion() {
  const res = await fetch("/api/configuracion");
  const cfg = await res.json();

  document.getElementById("cfgNombreFacultad").value = cfg.nombre_facultad || "";
  document.getElementById("cfgPeriodo").value = cfg.periodo_academico || "";
  document.getElementById("cfgLogoUrl").value = cfg.logo_url || "";
  document.getElementById("cfgDuracionSesion").value = cfg.duracion_sesion_minutos || 60;
  document.getElementById("cfgLimiteResultados").value = cfg.limite_resultados_busqueda || 20;
}

async function guardarConfiguracion() {
  const msg = document.getElementById("configMsg");
  msg.textContent = "";
  msg.style.color = "#d33";

  const nombre_facultad = document.getElementById("cfgNombreFacultad").value.trim();
  const periodo_academico = document.getElementById("cfgPeriodo").value.trim();
  const logo_url = document.getElementById("cfgLogoUrl").value.trim();
  const duracion_sesion_minutos = document.getElementById("cfgDuracionSesion").value;
  const limite_resultados_busqueda = document.getElementById("cfgLimiteResultados").value;

  if (!nombre_facultad || !periodo_academico) {
    msg.textContent = "Nombre de facultad y periodo académico son obligatorios.";
    return;
  }

  const idToken = await ctx.auth.currentUser.getIdToken();

  try {
    const res = await fetch("/api/configuracion", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        idToken, nombre_facultad, periodo_academico, logo_url,
        duracion_sesion_minutos, limite_resultados_busqueda
      })
    });
    const data = await res.json();

    if (res.ok) {
      msg.style.color = "#16a34a";
      msg.textContent = "Configuración guardada correctamente.";
    } else {
      msg.textContent = data.error || "Error al guardar";
    }
  } catch (err) {
    msg.textContent = "Error de conexión al guardar.";
    console.error(err);
  }
}