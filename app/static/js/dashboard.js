/* dashboard.js — live metrics polling every 5s, Chart.js charts */
(function () {
  let trendChart, defectChart;
  const POLL_MS = 5000;

  // ── Init charts ──────────────────────────────────────────────────────────
  function initCharts() {
    const darkColor = (a) => `rgba(148,163,184,${a})`;

    trendChart = new Chart(document.getElementById('trendChart'), {
      type: 'bar',
      data: { labels: [], datasets: [{ label: 'Uploads', data: [],
        backgroundColor: 'rgba(37,99,235,.7)', borderRadius: 4 }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#94a3b8', font: { size: 11 } }, grid: { color: 'rgba(255,255,255,.05)' } },
          y: { ticks: { color: '#94a3b8', font: { size: 11 } }, grid: { color: 'rgba(255,255,255,.05)' }, beginAtZero: true },
        },
      },
    });

    defectChart = new Chart(document.getElementById('defectChart'), {
      type: 'doughnut',
      data: { labels: [], datasets: [{ data: [],
        backgroundColor: ['#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#a855f7','#ec4899','#14b8a6'] }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 11 }, boxWidth: 12 } } },
      },
    });
  }

  // ── Fetch + update ────────────────────────────────────────────────────────
  async function refresh() {
    try {
      const [mRes, hRes, aRes] = await Promise.all([
        fetch('/dashboard/api/metrics', { credentials: 'same-origin' }),
        fetch('/dashboard/api/health',  { credentials: 'same-origin' }),
        fetch('/dashboard/api/activity',{ credentials: 'same-origin' }),
      ]);
      const m = await mRes.json();
      const h = await hRes.json();
      const a = await aRes.json();

      // KPIs
      setText('kpiUploads',    m.uploads_24h);
      setText('kpiAccept',     m.accept_rate + '%');
      setText('kpiMs',         m.avg_detect_ms + 'ms');
      setText('kpiNid',        m.nid_updates_24h);
      setText('kpiLogins',     m.logins_24h);
      setText('kpiFailLogins', m.login_fails_24h);

      // Trend chart
      trendChart.data.labels   = m.hourly_trend.map(t => t.hour);
      trendChart.data.datasets[0].data = m.hourly_trend.map(t => t.count);
      trendChart.update('none');

      // Defect chart
      if (m.defect_breakdown.length) {
        defectChart.data.labels   = m.defect_breakdown.map(d => d.code);
        defectChart.data.datasets[0].data = m.defect_breakdown.map(d => d.count);
        defectChart.update('none');
      }

      // Health
      const healthList = document.getElementById('healthList');
      healthList.innerHTML = Object.entries(h.checks).map(([name, check]) => `
        <div class="health-item">
          <span>${name}</span>
          <span class="${check.status === 'ok' ? 'status-ok' : 'status-err'}">
            ${check.status === 'ok' ? '✓ ok' : '✗ ' + (check.detail || 'error')}
            ${check.version ? `<span style="color:#64748b;font-weight:400"> v${check.version}</span>` : ''}
          </span>
        </div>`).join('');

      // Simulated pipeline (swap for real GitHub Actions API in production)
      simulatePipeline();

      // Activity feed
      const feed = document.getElementById('activityFeed');
      feed.innerHTML = a.slice(0, 20).map(l => `
        <div class="act-item">
          <span class="act-action">${l.action}</span>
          <span class="act-detail"> — ${l.detail || ''}</span>
          <span style="float:right;color:#475569">${l.timestamp.substring(11,19)}</span>
        </div>`).join('');

      // Last update
      document.getElementById('lastUpdate').textContent =
        'Updated ' + new Date().toLocaleTimeString();
      document.getElementById('liveDot').style.background = '#22c55e';

    } catch (err) {
      document.getElementById('liveDot').style.background = '#ef4444';
      document.getElementById('lastUpdate').textContent = 'Error polling metrics';
    }
  }

  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  // Simulated CI pipeline status (replace with GitHub Actions REST API call)
  function simulatePipeline() {
    const stages = [
      ['pipeTestStatus',   'pipeTest',   'pass'],
      ['pipeLintStatus',   'pipeLint',   'pass'],
      ['pipeDockerStatus', 'pipeDocker', 'pass'],
      ['pipeDeployStatus', 'pipeDeploy', 'pass'],
    ];
    stages.forEach(([sid, stepId, status]) => {
      const el = document.getElementById(sid);
      if (!el) return;
      el.textContent = status === 'pass' ? '✓ pass' : status === 'fail' ? '✗ fail' : '⟳ running';
      el.className   = 'pipe-status pipe-' + status;
    });
  }

  // ── Boot ──────────────────────────────────────────────────────────────────
  initCharts();
  refresh();
  setInterval(refresh, POLL_MS);
})();
