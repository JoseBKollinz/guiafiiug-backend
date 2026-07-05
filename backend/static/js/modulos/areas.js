let ctx = null;

export async function init(contexto) {
  ctx = contexto;

  document.getElementById("btnNuevaArea").addEventListener("click", () => abrirFormArea());
  document.getElementById("btnGuardarArea").addEventListener("click", guardarArea);
  document.getElementById("btnCancelarArea").addEventListener("click", cerrarModal);

  await renderAreas();
}

async function renderAreas() {
  const cont = document.getElementById("listaAreas");
  const msg = document.getElementById("areasMsg");
  msg.textContent = "";
  cont.innerHTML = `<p style="color:#6b7280;font-size:13px">Cargando...</p>`;

  try {
    const res = await fetch("/api/areas-comunes");
    const areas = await res.json();

    if (!areas.length) {
      cont.innerHTML = `<p style="color:#6b7280;font-size:13px">No hay áreas comunes registradas.</p>`;
      return;
    }

    cont.innerHTML = areas.map(a => `
      <div class="panel-row" style="padding:10px 0;align-items:flex-start">
        <div>
          <strong style="font-size:13px">${a.nombre}</strong>
          <div style="font-size:11.5px;color:#6b7280">${a.tipo || ""}</div>
        </div>
        <span style="display:flex;gap:8px">
          <button data-editar='${JSON.stringify(a)}' style="border:none;background:none;cursor:pointer">✏️</button>
          <button data-eliminar="${a.id}" style="border:none;background:none;cursor:pointer">🗑️</button>
        </span>
      </div>
    `).join("");

    cont.querySelectorAll("[data-editar]").forEach(btn => {
      btn.addEventListener("click", () => abrirFormArea(JSON.parse(btn.dataset.editar)));
    });
    cont.querySelectorAll("[data-eliminar]").forEach(btn => {
      btn.addEventListener("click", () => eliminarArea(btn.dataset.eliminar));
    });
  } catch (err) {
    msg.textContent = "Error al cargar las áreas comunes.";
    console.error(err);
  }
}

function abrirFormArea(area = null) {
  document.getElementById("modalAreaTitulo").textContent = area ? "Editar área" : "Nueva área";
  document.getElementById("areaIdEdit").value = area ? area.id : "";
  document.getElementById("areaNombreInput").value = area ? area.nombre : "";
  document.getElementById("areaTipoInput").value = area ? area.tipo || "" : "";
  document.getElementById("areaInfoInput").value = area ? area.info || "" : "";
  document.getElementById("areaMapaInput").value = area ? area.mapa || "" : "";
  document.getElementById("areaServiciosInput").value = area ? (area.servicios || []).join(", ") : "";
  document.getElementById("modalArea").style.display = "flex";
}

function cerrarModal() {
  document.getElementById("modalArea").style.display = "none";
}

async function guardarArea() {
  const id = document.getElementById("areaIdEdit").value;
  const nombre = document.getElementById("areaNombreInput").value.trim();
  const tipo = document.getElementById("areaTipoInput").value.trim();
  const info = document.getElementById("areaInfoInput").value.trim();
  const mapa = document.getElementById("areaMapaInput").value.trim();
  const servicios = document.getElementById("areaServiciosInput").value
    .split(",").map(s => s.trim()).filter(Boolean);

  const msg = document.getElementById("areasMsg");

  if (!nombre) {
    msg.textContent = "El nombre es obligatorio.";
    return;
  }

  const idToken = await ctx.auth.currentUser.getIdToken();
  const url = id ? `/api/areas-comunes/${id}` : "/api/areas-comunes";
  const metodo = id ? "PUT" : "POST";

  try {
    const res = await fetch(url, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken, nombre, tipo, info, mapa, servicios })
    });
    const data = await res.json();

    if (res.ok) {
      cerrarModal();
      renderAreas();
    } else {
      msg.textContent = data.error || "Error al guardar";
    }
  } catch (err) {
    msg.textContent = "Error de conexión al guardar.";
    console.error(err);
  }
}

async function eliminarArea(id) {
  if (!confirm(`¿Eliminar el área "${id}"? Esta acción no se puede deshacer.`)) return;

  const idToken = await ctx.auth.currentUser.getIdToken();

  try {
    const res = await fetch(`/api/areas-comunes/${id}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken })
    });
    const data = await res.json();

    if (res.ok) {
      renderAreas();
    } else {
      alert(data.error || "Error al eliminar");
    }
  } catch (err) {
    alert("Error de conexión al eliminar.");
    console.error(err);
  }
}