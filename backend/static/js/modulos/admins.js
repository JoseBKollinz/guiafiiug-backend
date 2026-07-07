let ctx = null;
let adminsCache = [];

export async function init(contexto) {
  ctx = contexto;

  document.getElementById("btnNuevoAdmin").addEventListener("click", () => abrirFormAdmin());
  document.getElementById("btnGuardarAdmin").addEventListener("click", guardarAdmin);
  document.getElementById("btnCancelarAdmin").addEventListener("click", cerrarModal);

  document.getElementById("filtroNombreAdmin").addEventListener("input", aplicarFiltros);
  document.getElementById("filtroEmailAdmin").addEventListener("input", aplicarFiltros);
  document.getElementById("filtroRolAdmin").addEventListener("change", aplicarFiltros);
  document.getElementById("btnLimpiarFiltrosAdmin").addEventListener("click", limpiarFiltros);

  await cargarAdmins();
}

async function cargarAdmins() {
  const msg = document.getElementById("adminsMsg");
  msg.textContent = "";

  try {
    const idToken = await ctx.auth.currentUser.getIdToken();
    const res = await fetch("/api/administradores", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken })
    });
    adminsCache = await res.json();
    renderTabla(adminsCache);
  } catch (err) {
    msg.textContent = "Error al cargar los administradores.";
    console.error(err);
  }
}

function aplicarFiltros() {
  const nombre = document.getElementById("filtroNombreAdmin").value.trim().toLowerCase();
  const email = document.getElementById("filtroEmailAdmin").value.trim().toLowerCase();
  const rol = document.getElementById("filtroRolAdmin").value;

  const filtrados = adminsCache.filter(a => {
    const coincideNombre = !nombre || (a.nombre || "").toLowerCase().includes(nombre);
    const coincideEmail = !email || (a.email || "").toLowerCase().includes(email);
    const coincideRol = !rol || a.role === rol;
    return coincideNombre && coincideEmail && coincideRol;
  });

  renderTabla(filtrados);
}

function limpiarFiltros() {
  document.getElementById("filtroNombreAdmin").value = "";
  document.getElementById("filtroEmailAdmin").value = "";
  document.getElementById("filtroRolAdmin").value = "";
  renderTabla(adminsCache);
}

function renderTabla(lista) {
  const tbody = document.getElementById("tablaAdmins");

  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="4" style="padding:14px;color:#6b7280">No se encontraron administradores.</td></tr>`;
    return;
  }

  const miUid = ctx.auth.currentUser.uid;

  tbody.innerHTML = lista.map(a => {
    const esProtegido = a.role === "admin"; // no editable/eliminable desde aquí
    const esYoMismo = a.uid === miUid;

    return `
      <tr style="border-bottom:1px solid #f1f3f6">
        <td style="padding:10px 8px">${a.nombre || "—"}</td>
        <td style="padding:10px 8px">${a.email || "—"}</td>
        <td style="padding:10px 8px"><span style="background:#e0edff;padding:3px 8px;border-radius:12px;font-size:11.5px">${a.role}</span></td>
        <td style="padding:10px 8px;text-align:center">
          ${esProtegido
        ? `<span style="color:#9ca3af;font-size:11.5px"><i class="ti ti-lock"></i> Protegido</span>`
        : `
        <button data-editar='${JSON.stringify({ uid: a.uid, nombre: a.nombre, role: a.role })}' style="border:none;background:none;cursor:pointer"><i class="ti ti-edit"></i></button>
        <button data-eliminar="${a.uid}" style="border:none;background:none;cursor:pointer" ${esYoMismo ? "disabled title='No puedes eliminar tu propia cuenta'" : ""}><i class="ti ti-trash"></i></button>
        `}
        </td>
      </tr>
    `;
  }).join("");

  tbody.querySelectorAll("[data-editar]").forEach(btn => {
    btn.addEventListener("click", () => abrirFormAdmin(JSON.parse(btn.dataset.editar)));
  });
  tbody.querySelectorAll("[data-eliminar]:not([disabled])").forEach(btn => {
    btn.addEventListener("click", () => eliminarAdmin(btn.dataset.eliminar));
  });
}

function abrirFormAdmin(admin = null) {
  document.getElementById("modalAdminTitulo").textContent = admin ? "Editar administrador" : "Nueva cuenta";
  document.getElementById("adminUidEdit").value = admin ? admin.uid : "";
  document.getElementById("adminNombreInput").value = admin ? admin.nombre : "";
  document.getElementById("adminRolInput").value = admin ? admin.role : "admin_junior";
  document.getElementById("adminEmailInput").value = "";
  document.getElementById("adminPasswordInput").value = "";
  document.getElementById("modalAdminMsg").textContent = "";

  // El correo y contraseña solo se piden al crear, no al editar
  document.getElementById("campoEmailAdmin").style.display = admin ? "none" : "block";
  document.getElementById("campoPasswordAdmin").style.display = admin ? "none" : "block";

  document.getElementById("modalAdmin").style.display = "flex";
}

function cerrarModal() {
  document.getElementById("modalAdmin").style.display = "none";
}

async function guardarAdmin() {
  const uid = document.getElementById("adminUidEdit").value;
  const nombre = document.getElementById("adminNombreInput").value.trim();
  const email = document.getElementById("adminEmailInput").value.trim();
  const password = document.getElementById("adminPasswordInput").value.trim();
  const role = document.getElementById("adminRolInput").value;
  const msg = document.getElementById("modalAdminMsg");

  if (!nombre || !role) {
    msg.textContent = "Nombre y rol son obligatorios.";
    return;
  }

  const idToken = await ctx.auth.currentUser.getIdToken();

  try {
    let res;
    if (uid) {
      res = await fetch(`/api/administradores/${uid}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken, nombre, role })
      });
    } else {
      if (!email || !password) {
        msg.textContent = "Correo y contraseña son obligatorios para una cuenta nueva.";
        return;
      }
      res = await fetch("/api/administradores/crear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken, nombre, email, password, role })
      });
    }

    const data = await res.json();

    if (res.ok) {
      cerrarModal();
      const idToken = await ctx.auth.currentUser.getIdToken();
      await window.fetchConCache("/api/administradores", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken })
      }, true);
      cargarAdmins();
    } else {
      msg.textContent = data.error || "Error al guardar";
    }
  } catch (err) {
    msg.textContent = "Error de conexión al guardar.";
    console.error(err);
  }
}

async function eliminarAdmin(uid) {
  if (!confirm("¿Eliminar esta cuenta administrativa? Esta acción no se puede deshacer.")) return;

  const idToken = await ctx.auth.currentUser.getIdToken();

  try {
    const res = await fetch(`/api/administradores/${uid}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken })
    });
    const data = await res.json();

    if (res.ok) {
      cerrarModal();
      const idToken = await ctx.auth.currentUser.getIdToken();
      await window.fetchConCache("/api/administradores", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken })
      }, true);
      cargarAdmins();
    } else {
      alert(data.error || "Error al eliminar");
    }
  } catch (err) {
    alert("Error de conexión al eliminar.");
    console.error(err);
  }
}