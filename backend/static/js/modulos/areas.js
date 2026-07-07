let ctx = null;
let logsCache = [];
let reportesCache = [];

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

    // Trae logs reales y reportes pendientes en paralelo
    const [logs, reportes] = await Promise.all([
      window.fetchConCache("/api/auditoria", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken, limite: 200 })
      }),
      window.fetchConCache("/api/reportes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken, soloPendientes: true })
      })
    ]);

    logsCache = logs;
    reportesCache = reportes;

    renderTabla(combinarParaVista(logsCache, reportesCache));
  } catch (err) {
    msg.textContent = "Error al cargar el registro de auditoría.";
    console.error(err);
  }
}

// Convierte los reportes pendientes a un formato "compatible" con la tabla de logs,
// pero SIN escribir nada en Firestore — es solo para presentación
function combinarParaVista(logs, reportes) {
  const reportesComoFilas = reportes.map(r => ({
    id: `reporte_${r.id}`,
    accion: "reporte_pendiente",
    documento: r.nombre || r.lugarId || r.id,
    usuario_nombre: null,
    rol: null,
    resultado: "pendiente",   // marcador especial, no "exito"/"fallido"
    timestamp: r.fecha,        // epoch ms, igual que busquedas
    ip: null,
    _esReporte: true,          // bandera interna para diferenciar en el render
    _problema: r.problema
  }));

  const combinado = [...logs, ...reportesComoFilas];

  // Ordena todo por fecha descendente (logs usan Firestore Timestamp, reportes usan epoch ms)
  combinado.sort((a, b) => {
    const fechaA = obtenerEpoch(a.timestamp);
    const fechaB = obtenerEpoch(b.timestamp);
    return fechaB - fechaA;
  });

  return combinado;
}

function obtenerEpoch(ts) {
  if (!ts) return 0;
  if (typeof ts === "object" && ts._seconds) return ts._seconds * 1000;
  if (typeof ts === "number") return ts;
  return new Date(ts).getTime();
}

function aplicarFiltros() {
  const accion = document.getElementById("filtroAccion").value;
  const usuario = document.getElementById("filtroUsuarioLog").value.trim().toLowerCase();
  const resultado = document.getElementById("filtroResultado").value;
  const fecha = document.getElementById("filtroFechaLog").value;

  const combinado = combinarParaVista(logsCache, reportesCache);

  const filtrados = combinado.filter(l => {
    const coincideAccion = !accion || l.accion === accion;
    const coincideUsuario = !usuario ||
      (l.usuario_nombre || "").toLowerCase().includes(usuario) ||
      (l.usuario_uid || "").toLowerCase().includes(usuario) ||
      (l.documento || "").toLowerCase().includes(usuario);
    const coincideResultado = !resultado || l.resultado === resultado;
    const coincideFecha = !fecha || fechaCoincide(l.timestamp, fecha);
    return coincideAccion && coincideUsuario && coincideResultado && coincideFecha;
  });

  renderTabla(filtrados);
}

function fechaCoincide(campoFecha, fechaFiltro) {
  const epoch = obtenerEpoch(campoFecha);
  if (!epoch) return false;
  return new Date(epoch).toISOString().split("T")[0] === fechaFiltro;
}

function limpiarFiltros() {
  document.getElementById("filtroAccion").value = "";
  document.getElementById("filtroUsuarioLog").value = "";
  document.getElementById("filtroResultado").value = "";
  document.getElementById("filtroFechaLog").value = "";
  renderTabla(combinarParaVista(logsCache, reportesCache));
}

function renderTabla(lista) {
  const tbody = document.getElementById("tablaAuditoria");

  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="padding:14px;color:#6b7280">No se encontraron registros.</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(l => {
    const esReporte = l._esReporte;
    const colorResultado = esReporte ? "#d97706" : (l.resultado === 'exito' ? '#16a34a' : '#dc2626');
    const iconoResultado = esReporte
      ? '<i class="ti ti-alert-circle" style="color:#d97706"></i> Pendiente'
      : (l.resultado === 'exito'
          ? '<i class="ti ti-check" style="color:#16a34a"></i> Éxito'
          : '<i class="ti ti-x" style="color:#dc2626"></i> Fallido');

    return `
      <tr style="border-bottom:1px solid #f1f3f6;${esReporte ? 'background:#fffbeb' : ''}">
        <td style="padding:9px 8px;white-space:nowrap;color:#6b7280">${formatFecha(l.timestamp)}</td>
        <td style="padding:9px 8px">${l.usuario_nombre || (esReporte ? '—' : (l.usuario_uid || '—'))}</td>
        <td style="padding:9px 8px">${l.rol || "—"}</td>
        <td style="padding:9px 8px">
          <span style="background:${esReporte ? '#fef3c7' : '#e0edff'};color:${esReporte ? '#92400e' : '#0a3d42'};padding:2px 8px;border-radius:10px;font-size:11px">
            ${esReporte ? '⚠ ' + (l._problema || 'Reporte') : l.accion}
          </span>
        </td>
        <td style="padding:9px 8px;font-family:monospace;font-size:11.5px">${l.documento || "—"}</td>
        <td style="padding:9px 8px">${iconoResultado}</td>
        <td style="padding:9px 8px;color:#6b7280">${l.ip || "—"}</td>
      </tr>
    `;
  }).join("");
}

function formatFecha(f) {
  const epoch = obtenerEpoch(f);
  if (!epoch) return "—";
  return new Date(epoch).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "medium" });
}