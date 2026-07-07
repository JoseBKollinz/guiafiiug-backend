let ctx = null;
let usuariosCache = [];

export async function init(contexto) {
  ctx = contexto;

  document.getElementById("btnNuevoUsuario").addEventListener("click", () => abrirFormUsuario());
  document.getElementById("btnGuardarUsuario").addEventListener("click", guardarUsuario);
  document.getElementById("btnCancelarUsuario").addEventListener("click", cerrarModal);

  document.getElementById("filtroNombre").addEventListener("input", aplicarFiltros);
  document.getElementById("filtroApellido").addEventListener("input", aplicarFiltros);
  document.getElementById("filtroCedula").addEventListener("input", aplicarFiltros);
  document.getElementById("filtroFecha").addEventListener("change", aplicarFiltros);
  document.getElementById("btnLimpiarFiltros").addEventListener("click", limpiarFiltros);

  await cargarUsuarios();
}

async function cargarUsuarios() {
  const msg = document.getElementById("usuariosMsg");
  msg.textContent = "";

  try {
    const idToken = await ctx.auth.currentUser.getIdToken();
    usuariosCache = await window.fetchConCache("/api/usuarios", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken })
    });
    renderTabla(usuariosCache);
  } catch (err) {
    msg.textContent = "Error al cargar los usuarios.";
    console.error(err);
  }
}

function aplicarFiltros() {
  const nombre = document.getElementById("filtroNombre").value.trim().toLowerCase();
  const apellido = document.getElementById("filtroApellido").value.trim().toLowerCase();
  const cedula = document.getElementById("filtroCedula").value.trim().toLowerCase();
  const fecha = document.getElementById("filtroFecha").value; // formato YYYY-MM-DD

  const filtrados = usuariosCache.filter(u => {
    const coincideNombre = !nombre || (u.nombre || "").toLowerCase().includes(nombre);
    const coincideApellido = !apellido || (u.apellido || "").toLowerCase().includes(apellido);
    const coincideCedula = !cedula || (u.cedula || "").toLowerCase().includes(cedula);
    const coincideFecha = !fecha || fechaCoincide(u.fechaRegistro, fecha);
    return coincideNombre && coincideApellido && coincideCedula && coincideFecha;
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
  const fechaDocStr = fechaDoc.toISOString().split("T")[0]; // YYYY-MM-DD
  return fechaDocStr === fechaFiltro;
}

function limpiarFiltros() {
  document.getElementById("filtroNombre").value = "";
  document.getElementById("filtroApellido").value = "";
  document.getElementById("filtroCedula").value = "";
  document.getElementById("filtroFecha").value = "";
  renderTabla(usuariosCache);
}

function renderTabla(lista) {
  const tbody = document.getElementById("tablaUsuarios");

  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="padding:14px;color:#6b7280">No se encontraron estudiantes.</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(u => `
    <tr style="border-bottom:1px solid #f1f3f6">
      <td style="padding:10px 8px">${u.nombre || "—"}</td>
      <td style="padding:10px 8px">${u.apellido || "—"}</td>
      <td style="padding:10px 8px;font-family:monospace">${u.cedula || "—"}</td>
      <td style="padding:10px 8px;color:#6b7280">${formatFecha(u.fechaRegistro)}</td>
      <td style="padding:10px 8px;text-align:center">
        <button data-editar='${JSON.stringify({ id: u.id, nombre: u.nombre, apellido: u.apellido })}' style="border:none;background:none;cursor:pointer"><i class="ti ti-edit"></i></button>
        <button data-eliminar="${u.id}" style="border:none;background:none;cursor:pointer"><i class="ti ti-trash"></i></button>
</td>
    </tr>
  `).join("");

  tbody.querySelectorAll("[data-editar]").forEach(btn => {
    btn.addEventListener("click", () => abrirFormUsuario(JSON.parse(btn.dataset.editar)));
  });
  tbody.querySelectorAll("[data-eliminar]").forEach(btn => {
    btn.addEventListener("click", () => eliminarUsuario(btn.dataset.eliminar));
  });
}

function formatFecha(f) {
  if (!f) return "—";
  if (typeof f === "object" && f._seconds) {
    return new Date(f._seconds * 1000).toLocaleDateString("es-EC");
  }
  return new Date(f).toLocaleDateString("es-EC");
}

function abrirFormUsuario(usuario = null) {
  document.getElementById("modalUsuarioTitulo").textContent = usuario ? "Editar estudiante" : "Nuevo estudiante";
  document.getElementById("usuarioIdEdit").value = usuario ? usuario.id : "";
  document.getElementById("usuarioNombreInput").value = usuario ? usuario.nombre : "";
  document.getElementById("usuarioApellidoInput").value = usuario ? usuario.apellido : "";
  document.getElementById("usuarioCedulaInput").value = "";
  document.getElementById("modalUsuarioMsg").textContent = "";
  document.getElementById("campoCedula").style.display = usuario ? "none" : "block";
  document.getElementById("modalUsuario").style.display = "flex";
}

function cerrarModal() {
  document.getElementById("modalUsuario").style.display = "none";
}

async function guardarUsuario() {
  const id = document.getElementById("usuarioIdEdit").value;
  const nombre = document.getElementById("usuarioNombreInput").value.trim();
  const apellido = document.getElementById("usuarioApellidoInput").value.trim();
  const cedula = document.getElementById("usuarioCedulaInput").value.trim();
  const msg = document.getElementById("modalUsuarioMsg");

  if (!nombre || !apellido) {
    msg.textContent = "Nombre y apellido son obligatorios.";
    return;
  }
  if (!id && !cedula) {
    msg.textContent = "La cédula es obligatoria para un nuevo estudiante.";
    return;
  }

  const idToken = await ctx.auth.currentUser.getIdToken();

  try {
    let res;
    if (id) {
      res = await fetch(`/api/usuarios/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken, nombre, apellido })
      });
    } else {
      const data = await window.fetchConCache("/api/registrar-estudiante", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken })
      });
    }

    if (res.ok) {
      cerrarModal();
      cargarUsuarios();
    } else {
      msg.textContent = data.error || "Error al guardar";
    }
  } catch (err) {
    msg.textContent = "Error de conexión al guardar.";
    console.error(err);
  }
}

async function eliminarUsuario(id) {
  if (!confirm("¿Eliminar este estudiante? Esta acción no se puede deshacer.")) return;

  const idToken = await ctx.auth.currentUser.getIdToken();

  try {
    const res = await fetch(`/api/usuarios/${id}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken })
    });
    const data = await res.json();

    if (res.ok) {
      cargarUsuarios();
    } else {
      alert(data.error || "Error al eliminar");
    }
  } catch (err) {
    alert("Error de conexión al eliminar.");
    console.error(err);
  }
}