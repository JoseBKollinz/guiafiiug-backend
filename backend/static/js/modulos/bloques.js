let ctx = null;

export async function init(contexto) {
  ctx = contexto;
  document.getElementById("btnNuevoBloque").addEventListener("click", () => abrirFormBloque());
  document.getElementById("btnGuardarBloque").addEventListener("click", guardarBloque);
  document.getElementById("btnCancelarBloque").addEventListener("click", cerrarModal);

  await Promise.all([renderBloques(), renderResumenKPIs()]);
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
async function renderResumenKPIs() {
  const res = await fetch("/api/aulas-resumen");
  const data = await res.json();

  const promedio = data.total_bloques > 0 ? (data.total_aulas / data.total_bloques).toFixed(1) : "0";
  const bloqueTop = Object.entries(data.aulas_por_bloque).sort((a, b) => b[1] - a[1])[0];

  const tarjetas = [
    { icon: "ti-building", value: data.total_bloques, label: "Total de bloques" },
    { icon: "ti-door", value: data.total_aulas, label: "Total de aulas" },
    { icon: "ti-chart-bar", value: promedio, label: "Promedio aulas / bloque" },
    { icon: "ti-trophy", value: bloqueTop ? bloqueTop[0] : "—", label: "Bloque con más aulas" },
  ];

  document.getElementById("bloquesStats").innerHTML = tarjetas.map(t => `
    <div class="stat-card">
      <div class="stat-icon"><i class="ti ${t.icon}"></i></div>
      <div>
        <div class="stat-value" style="font-size:16px">${t.value}</div>
        <div class="stat-label">${t.label}</div>
      </div>
    </div>
  `).join("");

  new Chart(document.getElementById("aulasPorBloqueChart"), {
    type: "bar",
    data: {
      labels: Object.keys(data.aulas_por_bloque),
      datasets: [{
        data: Object.values(data.aulas_por_bloque),
        backgroundColor: "#17b8c4",
        borderRadius: 6
      }]
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
    }
  });

  const labelsTipos = Object.keys(data.tipos_conteo || {});
  const valoresTipos = Object.values(data.tipos_conteo || {});

  new Chart(document.getElementById("tiposGlobalChart"), {
    type: "pie",
    data: {
      labels: labelsTipos.length ? labelsTipos : ["Sin datos"],
      datasets: [{
        data: valoresTipos.length ? valoresTipos : [1],
        backgroundColor: ["#0a3d42", "#17b8c4", "#2fd4d4", "#7dd8e0", "#b3ecf0"]
      }]
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10.5 } } } }
    }
  });
}