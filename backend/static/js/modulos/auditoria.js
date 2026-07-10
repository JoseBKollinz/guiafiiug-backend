let ctx = null;
let logsCache = [];
let reportesCache = [];
let lugaresInfoCache = [];

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

    const [logsResult, reportesResult, lugaresResult] = await Promise.allSettled([
      window.fetchConCache("/api/auditoria", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken, limite: 200 })
      }),
      window.fetchConCache("/api/reportes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken, soloPendientes: true })
      }),
      window.fetchConCache("/api/lugares-info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken })
      })
    ]);

    logsCache = logsResult.status === "fulfilled" ? logsResult.value : [];
    reportesCache = (reportesResult.status === "fulfilled" && Array.isArray(reportesResult.value)) ? reportesResult.value : [];
    lugaresInfoCache = (lugaresResult.status === "fulfilled" && Array.isArray(lugaresResult.value)) ? lugaresResult.value : [];

    renderTabla(combinarParaVista(logsCache, reportesCache, lugaresInfoCache));
  } catch (err) {
    msg.textContent = "Error al cargar el registro de auditoría.";
    console.error(err);
  }
}

function combinarParaVista(logs, reportes, lugaresInfo) {
  const reportesComoFilas = reportes.map(r => ({
    id: `reporte_${r.id}`,
    accion: "reporte_pendiente",
    documento: r.nombre || r.lugarId || r.id,
    usuario_nombre: null,
    rol: null,
    resultado: "pendiente",
    timestamp: r.fecha,
    ip: null,
    _tipo: "reporte",
    _detalle: r.problema
  }));

  const lugaresComoFilas = lugaresInfo.map(l => ({
    id: `lugar_info_${l.id}`,
    accion: "edicion_lugar_info",
    documento: l.nombre || l.id,
    usuario_nombre: null,
    rol: null,
    resultado: "sin_auditoria",
    timestamp: null,
    ip: null,
    _tipo: "lugar_info",
    _detalle: l.tipo || ""
  }));

  const combinado = [...logs, ...reportesComoFilas, ...lugaresComoFilas];
  combinado.sort((a, b) => obtenerEpoch(b.timestamp) - obtenerEpoch(a.timestamp));
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

  const combinado = combinarParaVista(logsCache, reportesCache, lugaresInfoCache);

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
  renderTabla(combinarParaVista(logsCache, reportesCache, lugaresInfoCache));
}

function renderTabla(lista) {
  const tbody = document.getElementById("tablaAuditoria");

  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="padding:14px;color:#6b7280">No se encontraron registros.</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(l => {
    const esReporte = l._tipo === "reporte";
    const esLugarInfo = l._tipo === "lugar_info";
    const esEspecial = esReporte || esLugarInfo;

    let colorFondo = "";
    let etiquetaAccion = l.accion;
    let iconoResultado = `<i class="ti ${l.resultado === 'exito' ? 'ti-check' : 'ti-x'}" style="color:${l.resultado === 'exito' ? '#16a34a' : '#dc2626'}"></i> ${l.resultado === 'exito' ? 'Éxito' : 'Fallido'}`;

    if (esReporte) {
      colorFondo = "background:#fffbeb";
      etiquetaAccion = "⚠ " + (l._detalle || "Reporte");
      iconoResultado = `<i class="ti ti-alert-circle" style="color:#d97706"></i> Pendiente`;
    } else if (esLugarInfo) {
      colorFondo = "background:#fffbeb";
      etiquetaAccion = "✎ Edición de lugar" + (l._detalle ? ` (${l._detalle})` : "");
      iconoResultado = `<i class="ti ti-alert-triangle" style="color:#d97706"></i> Sin fecha`;
    }

    return `
      <tr style="border-bottom:1px solid #f1f3f6;${colorFondo}">
        <td style="padding:9px 8px;white-space:nowrap;color:#6b7280">${l.timestamp ? formatFecha(l.timestamp) : "—"}</td>
        <td style="padding:9px 8px">${l.usuario_nombre || "—"}</td>
        <td style="padding:9px 8px">${l.rol || "—"}</td>
        <td style="padding:9px 8px">
          <span style="background:${esEspecial ? '#fef3c7' : '#e0edff'};color:${esEspecial ? '#92400e' : '#0a3d42'};padding:2px 8px;border-radius:10px;font-size:11px">
            ${etiquetaAccion}
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