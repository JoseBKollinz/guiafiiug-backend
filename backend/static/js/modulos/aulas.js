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
  await Promise.all([renderAulas(), renderResumenKPIs()]);
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
      <div class="item-card">
        <div class="item-card-main">
          <div class="item-card-icon"><i class="ti ti-door"></i></div>
          <div class="item-card-text">
            <strong>${a.nombre}</strong>
            <span>${a.tipo || ""} · ${nombreBloque(a.bloqueId)}</span>
          </div>
        </div>
        <div class="item-card-actions">
          <button data-editar='${JSON.stringify(a)}'><i class="ti ti-edit"></i></button>
          <button data-eliminar="${a.bloqueId}|${a.id}"><i class="ti ti-trash"></i></button>
        </div>
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

async function renderResumenKPIs() {
  const res = await fetch("/api/aulas-resumen");
  const data = await res.json();

  const tipoTop = Object.entries(data.tipos_conteo).sort((a, b) => b[1] - a[1])[0];
  const servicioTop = Object.entries(data.servicios_conteo).sort((a, b) => b[1] - a[1])[0];

  const tarjetas = [
    { icon: "ti-door", value: data.total_aulas, label: "Total de aulas" },
    { icon: "ti-category", value: tipoTop ? tipoTop[0] : "—", label: "Tipo más común" },
    { icon: "ti-wifi", value: servicioTop ? servicioTop[0] : "—", label: "Servicio más común" },
  ];

  document.getElementById("aulasStats").innerHTML = tarjetas.map(t => `
    <div class="stat-card">
      <div class="stat-icon"><i class="ti ${t.icon}"></i></div>
      <div>
        <div class="stat-value" style="font-size:15px">${t.value}</div>
        <div class="stat-label">${t.label}</div>
      </div>
    </div>
  `).join("");

  // Gráfico de servicios — altura dinámica según cantidad de servicios distintos
  const labelsServicios = Object.keys(data.servicios_conteo);
  const valoresServicios = Object.values(data.servicios_conteo);

  if (!labelsServicios.length) {
    document.getElementById("serviciosChartWrapper").innerHTML =
      `<p style="color:#6b7280;font-size:12.5px">No hay datos de servicios registrados en las aulas.</p>`;
  } else {
    // Cada barra necesita ~28px de alto para verse bien; mínimo 180px
    const alturaCalculada = Math.max(labelsServicios.length * 28, 180);
    document.getElementById("serviciosChartWrapper").style.height = `${alturaCalculada}px`;

    new Chart(document.getElementById("serviciosChart"), {
      type: "bar",
      data: {
        labels: labelsServicios,
        datasets: [{
          data: valoresServicios,
          backgroundColor: "#2fd4d4",
          borderRadius: 6
        }]
      },
      options: {
        maintainAspectRatio: false,
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, ticks: { stepSize: 1 } } }
      }
    });
  }

  // Gráfico de aulas por tipo
  const labelsTipos = Object.keys(data.tipos_conteo);
  const valoresTipos = Object.values(data.tipos_conteo);

  new Chart(document.getElementById("tiposChart"), {
    type: "doughnut",
    data: {
      labels: labelsTipos.length ? labelsTipos : ["Sin datos"],
      datasets: [{
        data: valoresTipos.length ? valoresTipos : [1],
        backgroundColor: ["#0a3d42", "#17b8c4", "#2fd4d4", "#7dd8e0", "#b3ecf0", "#0d4a50"]
      }]
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10.5 } } } }
    }
  });
}