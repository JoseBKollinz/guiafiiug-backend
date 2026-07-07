let ctx = null;

export async function init(contexto) {
  ctx = contexto;
  await cargarEstadisticas();
}

async function cargarEstadisticas() {
  const idToken = await ctx.auth.currentUser.getIdToken();
  const data = await window.fetchConCache("/api/estadisticas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken })
  });

  renderTarjetas(data);
  renderGraficoRoles(data.administradores_por_rol);
  renderDistribucion(data);
  renderLoginsPorDia(data.logins_por_dia);
  renderActividadSeguridad(data);
}

function renderTarjetas(data) {
  const promedioFavoritos = data.total_usuarios > 0
    ? (data.total_favoritos / data.total_usuarios).toFixed(1)
    : "0";

  const totalLogins = data.logins_ultimas_24h + data.logins_fallidos_ultimas_24h;
  const tasaExito = totalLogins > 0
    ? Math.round((data.logins_ultimas_24h / totalLogins) * 100)
    : 100;

  const tarjetas = [
    { icon: "ti-users", value: data.total_usuarios, label: "Estudiantes" },
    { icon: "ti-building", value: data.total_bloques, label: "Bloques" },
    { icon: "ti-door", value: data.total_aulas, label: "Aulas" },
    { icon: "ti-map-pin", value: data.total_areas_comunes, label: "Áreas comunes" },
    { icon: "ti-star", value: data.total_favoritos, label: "Favoritos totales" },
    { icon: "ti-heart", value: promedioFavoritos, label: "Favoritos / estudiante" },
    { icon: "ti-shield-check", value: `${tasaExito}%`, label: "Éxito login (24h)" },
  ];

  document.getElementById("statsGridModulo").innerHTML = tarjetas.map(t => `
    <div class="stat-card">
      <div class="stat-icon"><i class="ti ${t.icon}"></i></div>
      <div>
        <div class="stat-value">${t.value}</div>
        <div class="stat-label">${t.label}</div>
      </div>
    </div>
  `).join("");
}

function renderGraficoRoles(rolesConteo) {
  const labels = Object.keys(rolesConteo || {});
  const data = Object.values(rolesConteo || {});

  new Chart(document.getElementById("rolesChart"), {
    type: "doughnut",
    data: {
      labels: labels.length ? labels : ["Sin datos"],
      datasets: [{
        data: data.length ? data : [1],
        backgroundColor: ["#0a3d42", "#17b8c4", "#2fd4d4", "#7dd8e0", "#b3ecf0"]
      }]
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10.5 } } } }
    }
  });
}

function renderDistribucion(data) {
  new Chart(document.getElementById("distribucionChart"), {
    type: "pie",
    data: {
      labels: ["Bloques", "Aulas", "Áreas comunes"],
      datasets: [{
        data: [data.total_bloques, data.total_aulas, data.total_areas_comunes],
        backgroundColor: ["#0a3d42", "#17b8c4", "#7dd8e0"]
      }]
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10.5 } } } }
    }
  });
}

function renderLoginsPorDia(loginsPorDia) {
  const fechas = Object.keys(loginsPorDia || {}).sort();
  const exitosos = fechas.map(f => loginsPorDia[f].exitosos);
  const fallidos = fechas.map(f => loginsPorDia[f].fallidos);

  const labelsFormato = fechas.map(f => {
    const d = new Date(f + "T00:00:00");
    return d.toLocaleDateString("es-EC", { day: "2-digit", month: "short" });
  });

  new Chart(document.getElementById("loginsPorDiaChart"), {
    type: "line",
    data: {
      labels: labelsFormato.length ? labelsFormato : ["Sin datos"],
      datasets: [
        {
          label: "Exitosos",
          data: exitosos,
          borderColor: "#17b8c4",
          backgroundColor: "rgba(23, 184, 196, 0.15)",
          tension: 0.3,
          fill: true
        },
        {
          label: "Fallidos",
          data: fallidos,
          borderColor: "#dc2626",
          backgroundColor: "rgba(220, 38, 38, 0.1)",
          tension: 0.3,
          fill: true
        }
      ]
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10.5 } } } },
      scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
    }
  });
}

function renderActividadSeguridad(data) {
  const cont = document.getElementById("actividadSeguridad");
  cont.innerHTML = `
    <div class="panel-row"><span>Logins exitosos (24h)</span><span style="color:#0a3d42;font-weight:600">${data.logins_ultimas_24h}</span></div>
    <div class="panel-row"><span>Logins fallidos (24h)</span><span style="color:${data.logins_fallidos_ultimas_24h > 0 ? '#dc2626' : '#16a34a'};font-weight:600">${data.logins_fallidos_ultimas_24h}</span></div>
  `;
}