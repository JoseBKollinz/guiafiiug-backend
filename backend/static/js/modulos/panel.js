let ctx = null;

export async function init(contexto) {
  ctx = contexto;
  await cargarSaludo();

  if (["admin", "admin_junior"].includes(ctx.role)) {
    await cargarEstadisticas();
  } else {
    document.getElementById("panelStats").innerHTML = `<p style="color:#6b7280;font-size:13px">Estadísticas disponibles solo para administradores.</p>`;
  }

  if (["admin", "admin_junior", "auditor"].includes(ctx.role)) {
    await cargarTopFavoritos();
    await cargarActividadReciente();
  } else {
    document.querySelector(".charts-row").style.display = "none";
  }
}

async function cargarSaludo() {
  const cfgRes = await fetch("/api/configuracion");
  const cfg = await cfgRes.json();

  const nombreUsuario = ctx.email.split("@")[0];
  document.getElementById("panelSaludo").textContent = `Hola, ${nombreUsuario}`;
  document.getElementById("panelSubtitulo").textContent = cfg.nombre_facultad || "Sistema de Gestión de Espacios";
  document.getElementById("panelPeriodo").innerHTML = `<i class="ti ti-calendar"></i> ${cfg.periodo_academico || "—"}`;
}

async function cargarEstadisticas() {
  const idToken = await ctx.auth.currentUser.getIdToken();
  const res = await fetch("/api/estadisticas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken })
  });
  const data = await res.json();

  const tarjetas = [
    { icon: "ti-users", value: data.total_usuarios, label: "Estudiantes" },
    { icon: "ti-building", value: data.total_bloques, label: "Bloques" },
    { icon: "ti-door", value: data.total_aulas, label: "Aulas" },
    { icon: "ti-star", value: data.total_favoritos, label: "Favoritos" },
  ];

  document.getElementById("panelStats").innerHTML = tarjetas.map(t => `
    <div class="stat-card">
      <div class="stat-icon"><i class="ti ${t.icon}"></i></div>
      <div>
        <div class="stat-value">${t.value}</div>
        <div class="stat-label">${t.label}</div>
      </div>
    </div>
  `).join("");

  if (data.logins_fallidos_ultimas_24h > 0) {
    const alerta = document.getElementById("panelAlertaSeguridad");
    alerta.style.display = "block";
    alerta.innerHTML = `
      <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:14px 16px;font-size:13px;color:#991b1b;display:flex;align-items:center;gap:10px">
        <i class="ti ti-alert-triangle" style="font-size:18px"></i>
        <span>Se registraron <strong>${data.logins_fallidos_ultimas_24h}</strong> intento(s) de inicio de sesión fallido(s) en las últimas 24 horas. Revisa el módulo de Auditoría para más detalles.</span>
      </div>
    `;
  }
}

async function cargarTopFavoritos() {
  const idToken = await ctx.auth.currentUser.getIdToken();
  const res = await fetch("/api/favoritos-ranking", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken })
  });
  const ranking = await res.json();
  const top5 = ranking.slice(0, 5);

  new Chart(document.getElementById("panelFavoritosChart"), {
    type: "bar",
    data: {
      labels: top5.length ? top5.map(r => r.espacio.replace(/_/g, " ")) : ["Sin datos"],
      datasets: [{
        data: top5.length ? top5.map(r => r.total) : [0],
        backgroundColor: "#17b8c4",
        borderRadius: 6
      }]
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true, ticks: { stepSize: 1 } } }
    }
  });
}

async function cargarActividadReciente() {
  const idToken = await ctx.auth.currentUser.getIdToken();
  const res = await fetch("/api/auditoria", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken, limite: 5 })
  });
  const logs = await res.json();

  const cont = document.getElementById("panelActividad");
  if (!logs.length) {
    cont.innerHTML = `<p style="color:#6b7280;font-size:13px">Sin actividad reciente.</p>`;
    return;
  }

  cont.innerHTML = logs.map(l => `
    <div class="panel-row">
      <span>${l.usuario_nombre || "—"} · ${l.accion.replace(/_/g, " ")}</span>
      <span style="color:${l.resultado === 'exito' ? '#16a34a' : '#dc2626'}"><i class="ti ${l.resultado === 'exito' ? 'ti-check' : 'ti-x'}"></i></span>
    </div>
  `).join("");
}