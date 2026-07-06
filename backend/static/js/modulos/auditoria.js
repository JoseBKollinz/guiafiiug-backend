let ctx = null;
let logsCache = [];

export async function init(contexto) {
  ctx = contexto;

  document.getElementById("filtroAccion").addEventListener("change", aplicarFiltros);
  document.getElementById("filtroUsuarioLog").addEventListener("input", aplicarFiltros);
  document.getElementById("filtroResultado").addEventListener("change", aplicarFiltros);
  document.getElementById("filtroFechaLog").addEventListener("change", aplicarFiltros);
  document.getElementById("btnLimpiarFiltrosLog").addEventListener("click", limpiarFiltros);

  await cargarLogs();
}

async function cargarLogs() {
  const msg = document.getElementById("auditoriaMsg");
  msg.textContent = "";

  try {
    const idToken = await ctx.auth.currentUser.getIdToken();
    const res = await fetch("/api/auditoria", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken, limite: 200 })
    });
    logsCache = await res.json();
    renderTabla(logsCache);
  } catch (err) {
    msg.textContent = "Error al cargar el registro de auditoría.";
    console.error(err);
  }
}

function aplicarFiltros() {
  const accion = document.getElementById("filtroAccion").value;
  const usuario = document.getElementById("filtroUsuarioLog").value.trim().toLowerCase();
  const resultado = document.getElementById("filtroResultado").value;
  const fecha = document.getElementById("filtroFechaLog").value;

  const filtrados = logsCache.filter(l => {
    const coincideAccion = !accion || l.accion === accion;
    const coincideUsuario = !usuario ||
      (l.usuario_nombre || "").toLowerCase().includes(usuario) ||
      (l.usuario_uid || "").toLowerCase().includes(usuario);
    const coincideResultado = !resultado || l.resultado === resultado;
    const coincideFecha = !fecha || fechaCoincide(l.timestamp, fecha);
    return coincideAccion && coincideUsuario && coincideResultado && coincideFecha;
  });

  renderTabla(filtrados);
}

function fechaCoincide(campoFecha, fechaFiltro) {
  if (!campoFecha) return false;
  let fechaDoc;
  if (typeof campoFecha === "object" && campoFecha._seconds) {
    fechaDoc = new Date(campoFecha._seconds * 1000);
  } else {
    fechaDoc = new Date(campoFecha);
  }
  return fechaDoc.toISOString().split("T")[0] === fechaFiltro;
}

function limpiarFiltros() {
  document.getElementById("filtroAccion").value = "";
  document.getElementById("filtroUsuarioLog").value = "";
  document.getElementById("filtroResultado").value = "";
  document.getElementById("filtroFechaLog").value = "";
  renderTabla(logsCache);
}

function renderTabla(lista) {
  const tbody = document.getElementById("tablaAuditoria");

  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="padding:14px;color:#6b7280">No se encontraron registros.</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(l => `
    <tr style="border-bottom:1px solid #f1f3f6">
      <td style="padding:9px 8px;white-space:nowrap;color:#6b7280">${formatFecha(l.timestamp)}</td>
      <td style="padding:9px 8px">${l.usuario_nombre || l.usuario_uid || "—"}</td>
      <td style="padding:9px 8px">${l.rol || "—"}</td>
      <td style="padding:9px 8px"><span style="background:#e0edff;padding:2px 8px;border-radius:10px;font-size:11px">${l.accion}</span></td>
      <td style="padding:9px 8px;font-family:monospace;font-size:11.5px">${l.documento || "—"}</td>
      <td style="padding:9px 8px">
        <span style="color:${l.resultado === 'exito' ? '#16a34a' : '#dc2626'}">
          ${l.resultado === 'exito' ? '✅ Éxito' : '❌ Fallido'}
        </span>
      </td>
      <td style="padding:9px 8px;color:#6b7280">${l.ip || "—"}</td>
    </tr>
  `).join("");
}

function formatFecha(f) {
  if (!f) return "—";
  let fecha;
  if (typeof f === "object" && f._seconds) {
    fecha = new Date(f._seconds * 1000);
  } else {
    fecha = new Date(f);
  }
  return fecha.toLocaleString("es-EC", { dateStyle: "short", timeStyle: "medium" });
}