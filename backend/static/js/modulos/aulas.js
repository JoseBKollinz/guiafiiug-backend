let ctx = null;
let bloques = [];
let bloqueFiltroActual = "";

export async function init(contexto) {
  ctx = contexto;

  document.getElementById("btnNuevaAula").addEventListener("click", () => abrirFormAula());
  document.getElementById("btnGuardarAula").addEventListener("click", guardarAula);
  document.getElementById("btnCancelarAula").addEventListener("click", cerrarModal);
  document.getElementById("selectBloqueFiltro").addEventListener("change", (e) => {
    bloqueFiltroActual = e.target.value;
    renderAulas();
  });

  await cargarBloques();
  await renderAulas();
}

async function cargarBloques() {
  const res = await fetch("/api/bloques");
  bloques = await res.json();

  const filtro = document.getElementById("selectBloqueFiltro");
  const selectModal = document.getElementById("aulaBloqueSelect");

  const opciones = bloques.map(b => `<option value="${b.id}">${b.nombre}</option>`).join("");
  filtro.innerHTML = `<option value="">Todos los bloques</option>` + opciones;
  selectModal.innerHTML = opciones;

  if (bloques.length) bloqueFiltroActual = "";
}

async function renderAulas() {
  const cont = document.getElementById("listaAulas");
  const msg = document.getElementById("aulasMsg");
  msg.textContent = "";
  cont.innerHTML = `<p style="color:#6b7280;font-size:13px">Cargando...</p>`;

  try {
    const bloquesAConsultar = bloqueFiltroActual
      ? [bloqueFiltroActual]
      : bloques.map(b => b.id);

    let todasLasAulas = [];
    for (const bloqueId of bloquesAConsultar) {
      const res = await fetch(`/api/bloques/${bloqueId}/aulas`);
      const aulas = await res.json();
      aulas.forEach(a => a.bloqueId = bloqueId);
      todasLasAulas = todasLasAulas.concat(aulas);
    }

    if (!todasLasAulas.length) {
      cont.innerHTML = `<p style="color:#6b7280;font-size:13px">No hay aulas registradas.</p>`;
      return;
    }

    cont.innerHTML = todasLasAulas.map(a => `
      <div class="panel-row" style="padding:10px 0;align-items:flex-start">
        <div>
          <strong style="font-size:13px">${a.nombre}</strong>
          <div style="font-size:11.5px;color:#6b7280">${a.tipo || ""} · ${nombreBloque(a.bloqueId)}</div>
        </div>
        <span style="display:flex;gap:8px">
          <button data-editar='${JSON.stringify(a)}' style="border:none;background:none;cursor:pointer">✏️</button>
          <button data-eliminar="${a.bloqueId}|${a.id}" style="border:none;background:none;cursor:pointer">🗑️</button>
        </span>
      </div>
    `).join("");

    cont.querySelectorAll("[data-editar]").forEach(btn => {
      btn.addEventListener("click", () => abrirFormAula(JSON.parse(btn.dataset.editar)));
    });
    cont.querySelectorAll("[data-eliminar]").forEach(btn => {
      const [bloqueId, aulaId] = btn.dataset.eliminar.split("|");
      btn.addEventListener("click", () => eliminarAula(bloqueId, aulaId));
    });
  } catch (err) {
    msg.textContent = "Error al cargar las aulas.";
    console.error(err);
  }
}

function nombreBloque(bloqueId) {
  const b = bloques.find(x => x.id === bloqueId);
  return b ? b.nombre : bloqueId;
}

function abrirFormAula(aula = null) {
  document.getElementById("modalAulaTitulo").textContent = aula ? "Editar aula" : "Nueva aula";
  document.getElementById("aulaIdEdit").value = aula ? `${aula.bloqueId}|${aula.id}` : "";
  document.getElementById("aulaBloqueSelect").value = aula ? aula.bloqueId : (bloques[0]?.id || "");
  document.getElementById("aulaNombreInput").value = aula ? aula.nombre : "";
  document.getElementById("aulaTipoInput").value = aula ? aula.tipo || "" : "";
  document.getElementById("aulaInfoInput").value = aula ? aula.info || "" : "";
  document.getElementById("aulaMapaInput").value = aula ? aula.mapa || "" : "";
  document.getElementById("aulaServiciosInput").value = aula ? (aula.servicios || []).join(", ") : "";
  document.getElementById("modalAula").style.display = "flex";
}

function cerrarModal() {
  document.getElementById("modalAula").style.display = "none";
}

async function guardarAula() {
  const idEdit = document.getElementById("aulaIdEdit").value;
  const bloqueId = document.getElementById("aulaBloqueSelect").value;
  const nombre = document.getElementById("aulaNombreInput").value.trim();
  const tipo = document.getElementById("aulaTipoInput").value.trim();
  const info = document.getElementById("aulaInfoInput").value.trim();
  const mapa = document.getElementById("aulaMapaInput").value.trim();
  const servicios = document.getElementById("aulaServiciosInput").value
    .split(",").map(s => s.trim()).filter(Boolean);

  const msg = document.getElementById("aulasMsg");

  if (!nombre || !bloqueId) {
    msg.textContent = "El bloque y el nombre son obligatorios.";
    return;
  }

  const idToken = await ctx.auth.currentUser.getIdToken();
  const body = JSON.stringify({ idToken, nombre, tipo, info, mapa, servicios });

  let url, metodo;
  if (idEdit) {
    const [bId, aId] = idEdit.split("|");
    url = `/api/bloques/${bId}/aulas/${aId}`;
    metodo = "PUT";
  } else {
    url = `/api/bloques/${bloqueId}/aulas`;
    metodo = "POST";
  }

  try {
    const res = await fetch(url, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body
    });
    const data = await res.json();

    if (res.ok) {
      cerrarModal();
      renderAulas();
    } else {
      msg.textContent = data.error || "Error al guardar";
    }
  } catch (err) {
    msg.textContent = "Error de conexión al guardar.";
    console.error(err);
  }
}

async function eliminarAula(bloqueId, aulaId) {
  if (!confirm(`¿Eliminar el aula "${aulaId}"? Esta acción no se puede deshacer.`)) return;

  const idToken = await ctx.auth.currentUser.getIdToken();

  try {
    const res = await fetch(`/api/bloques/${bloqueId}/aulas/${aulaId}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken })
    });
    const data = await res.json();

    if (res.ok) {
      renderAulas();
    } else {
      alert(data.error || "Error al eliminar");
    }
  } catch (err) {
    alert("Error de conexión al eliminar.");
    console.error(err);
  }
}