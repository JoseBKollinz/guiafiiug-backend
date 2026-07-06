let ctx = null;

export async function init(contexto) {
  ctx = contexto;

  document.getElementById("btnNuevoBloque").addEventListener("click", () => abrirFormBloque());
  document.getElementById("btnGuardarBloque").addEventListener("click", guardarBloque);
  document.getElementById("btnCancelarBloque").addEventListener("click", cerrarModal);

  await renderBloques();
}

async function renderBloques() {
  const cont = document.getElementById("listaBloques");
  const msg = document.getElementById("bloquesMsg");
  msg.textContent = "";

  try {
    const res = await fetch("/api/bloques");
    const bloques = await res.json();

    if (!bloques.length) {
      cont.innerHTML = `<p style="color:#6b7280;font-size:13px">Aún no hay bloques registrados.</p>`;
      return;
    }

    cont.innerHTML = bloques.map(b => `
      <div class="item-card">
        <div class="item-card-main">
          <div class="item-card-icon"><i class="ti ti-building"></i></div>
          <div class="item-card-text">
            <strong>${b.nombre}</strong>
            <span>${b.id}</span>
          </div>
        </div>
        <div class="item-card-actions">
          <button data-editar="${b.id}" data-nombre="${b.nombre}"><i class="ti ti-edit"></i></button>
          <button data-eliminar="${b.id}"><i class="ti ti-trash"></i></button>
        </div>
      </div>
    `).join("");

    cont.querySelectorAll("[data-editar]").forEach(btn => {
      btn.addEventListener("click", () => abrirFormBloque(btn.dataset.editar, btn.dataset.nombre));
    });
    cont.querySelectorAll("[data-eliminar]").forEach(btn => {
      btn.addEventListener("click", () => eliminarBloque(btn.dataset.eliminar));
    });
  } catch (err) {
    msg.textContent = "Error al cargar los bloques.";
    console.error(err);
  }
}

function abrirFormBloque(id = "", nombre = "") {
  document.getElementById("modalBloqueTitulo").textContent = id ? "Editar bloque" : "Nuevo bloque";
  document.getElementById("bloqueIdEdit").value = id;
  document.getElementById("bloqueNombreInput").value = nombre;
  document.getElementById("modalBloque").style.display = "flex";
}

function cerrarModal() {
  document.getElementById("modalBloque").style.display = "none";
}

async function guardarBloque() {
  const id = document.getElementById("bloqueIdEdit").value;
  const nombre = document.getElementById("bloqueNombreInput").value.trim();
  const msg = document.getElementById("bloquesMsg");

  if (!nombre) {
    msg.textContent = "El nombre es obligatorio.";
    return;
  }

  const idToken = await ctx.auth.currentUser.getIdToken();
  const url = id ? `/api/bloques/${id}` : "/api/bloques";
  const metodo = id ? "PUT" : "POST";

  try {
    const res = await fetch(url, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken, nombre })
    });
    const data = await res.json();

    if (res.ok) {
      cerrarModal();
      renderBloques();
    } else {
      msg.textContent = data.error || "Error al guardar";
    }
  } catch (err) {
    msg.textContent = "Error de conexión al guardar.";
    console.error(err);
  }
}

async function eliminarBloque(id) {
  if (!confirm(`¿Eliminar el bloque "${id}"? Esta acción no se puede deshacer.`)) return;

  const idToken = await ctx.auth.currentUser.getIdToken();

  try {
    const res = await fetch(`/api/bloques/${id}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken })
    });
    const data = await res.json();

    if (res.ok) {
      renderBloques();
    } else {
      alert(data.error || "Error al eliminar");
    }
  } catch (err) {
    alert("Error de conexión al eliminar.");
    console.error(err);
  }
}