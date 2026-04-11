/**
 * panel-home.js — Lógica del panel principal unificado
 *
 * Configuración inyectada desde el template via window.PANEL_CONFIG:
 *   bioReadiness      {number}  Score de readiness del cliente
 *   emergencyUrl      {string}  URL para entrenamiento de emergencia
 *   ratiosFuerza      {object}  Datos del radar de balance de fuerza
 *   gamiWidgetUrl     {string}  URL del widget de gamificación
 */

document.addEventListener('DOMContentLoaded', function () {
    const cfg = window.PANEL_CONFIG || {};

    // ── animateLoLBars (también expuesto globalmente para toggleDashboardMode) ──
    window.animateLoLBars = function () {
        document.querySelectorAll('#full-mode-container .lol-stat-bar-fill').forEach(function (el) {
            el.style.width = '0';
            requestAnimationFrame(function () {
                var w = parseFloat(el.getAttribute('data-width') || 60);
                el.style.transition = 'width 1.2s cubic-bezier(0.4,0,0.2,1)';
                el.style.width = Math.min(100, Math.max(0, w)) + '%';
            });
        });
    };

    // ── ACWR Gauge (función reutilizable) ────────────────────────────────────
    function animarAcwrGauge(cardSelector, arcId, needleId) {
        try {
            const card = document.querySelector(cardSelector);
            if (!card) return;
            const acwr = parseFloat(card.dataset.acwr) || 0;
            const zona = card.dataset.zona || 'baja_carga';
            const L = Math.PI * 90;
            const clamp = Math.min(Math.max(acwr, 0), 2.0);
            const COLORS = { optima: '#22c55e', cuidado: '#f59e0b', riesgo_alto: '#ef4444', baja_carga: '#64748b' };
            const color = COLORS[zona] || '#64748b';

            const activeArc = document.getElementById(arcId);
            if (activeArc) {
                activeArc.setAttribute('stroke', color);
                setTimeout(() => {
                    activeArc.style.transition = 'stroke-dasharray 1.2s cubic-bezier(.4,0,.2,1)';
                    activeArc.setAttribute('stroke-dasharray', `${(clamp / 2) * L} 10000`);
                }, 150);
            }

            const needle = document.getElementById(needleId);
            if (needle) {
                const deg = (clamp / 2) * 180 - 90;
                setTimeout(() => { needle.style.transform = `rotate(${deg}deg)`; }, 200);
            }
        } catch (e) { console.error('ACWR gauge error:', e); }
    }
    animarAcwrGauge('#acwr-card-focus', 'acwr-active-arc-f', 'acwr-needle-f');
    animarAcwrGauge('.acwr-card:not(#acwr-card-focus)', 'acwr-active-arc', 'acwr-needle');

    // ── ACWR Chart ───────────────────────────────────────────────────────────
    try {
        const cvDash = document.getElementById('acwrChartDash');
        if (cvDash && typeof Chart !== 'undefined') {
            let raw = [];
            try { raw = JSON.parse(cvDash.dataset.acwr || '[]'); } catch (e) {}

            const labels = raw.map(r => r.fecha || '');
            const vals = raw.map(r => parseFloat(r.acwr) || 0);
            const today = new Date().toISOString().slice(0, 10);
            const todayIdx = labels.lastIndexOf(today) >= 0 ? labels.lastIndexOf(today) : labels.length - 1;
            const currentVal = vals[todayIdx] || 0;

            new Chart(cvDash, {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        {
                            data: vals,
                            borderColor: '#00d4a0',
                            backgroundColor: 'rgba(0,212,160,0.07)',
                            fill: true, tension: 0.4,
                            pointRadius: vals.map((_, i) => i === todayIdx ? 6 : 0),
                            pointBackgroundColor: vals.map((_, i) =>
                                i === todayIdx
                                    ? (currentVal >= 1.3 ? '#ef4444' : currentVal >= 0.8 ? '#22c55e' : '#f59e0b')
                                    : 'transparent'
                            ),
                            pointBorderColor: '#fff',
                            pointBorderWidth: 2,
                        },
                        { data: labels.map(() => 0.8), borderColor: 'rgba(34,197,94,.25)', borderDash: [4, 4], borderWidth: 1, pointRadius: 0, fill: false },
                        { data: labels.map(() => 1.3), borderColor: 'rgba(245,158,11,.25)', borderDash: [4, 4], borderWidth: 1, pointRadius: 0, fill: false },
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: ctx => {
                                    if (ctx.datasetIndex > 0) return null;
                                    const v = ctx.raw;
                                    const z = v >= 1.3 ? 'Riesgo' : v >= 0.8 ? 'Óptimo' : 'Precaución';
                                    return `ACWR ${v.toFixed(2)} — ${z}`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: { min: 0, max: 2, grid: { color: 'rgba(255,255,255,.05)' }, ticks: { stepSize: 0.5, color: 'rgba(255,255,255,.3)', font: { size: 9 } } },
                        x: { grid: { display: false }, ticks: { maxTicksLimit: 5, color: 'rgba(255,255,255,.3)', font: { size: 9 } } },
                    }
                }
            });

            const marker = document.getElementById('acwr-track-marker');
            if (marker) {
                const pct = Math.min(Math.max(currentVal / 2.0, 0), 1) * 100;
                setTimeout(() => { marker.style.left = pct + '%'; }, 300);
            }
        }
    } catch (e) { console.error('ACWR chart dash error:', e); }

    // ── Confirmación entrenamiento de emergencia ─────────────────────────────
    try {
        window.confirmarEntrenoExtra = function () {
            const readiness = cfg.bioReadiness || 50;
            const riskLevel = readiness < 50 ? 'ALTO' : (readiness < 70 ? 'MEDIO' : 'BAJO');
            const msg = `⚠️ ADVERTENCIA: Tu Readiness actual es del ${readiness}%.\n\nNivel de riesgo: ${riskLevel}\n\nEntrenar hoy puede comprometer tu recuperación y aumentar el riesgo de lesión.\n\nSe generará una rutina de emergencia Bio-Safe de bajo impacto.\n\n¿Deseas continuar?`;
            if (confirm(msg)) {
                window.location.href = cfg.emergencyUrl || '#';
            }
        };
    } catch (e) { console.error('Error in confirmarEntrenoExtra:', e); }

    // ── GYM / HYROX Mode Switcher ────────────────────────────────────────────
    try {
        const btnGym = document.getElementById('btnGym');
        const btnHyrox = document.getElementById('btnHyrox');
        const heroGymFocus = document.getElementById('heroGymFocus');
        const heroHyroxFocus = document.getElementById('heroHyroxFocus');
        const heroGymBtn = document.getElementById('heroGymBtn');
        const heroHyroxBtn = document.getElementById('heroHyroxBtn');
        const heroGym = document.getElementById('heroGym');
        const heroHyrox = document.getElementById('heroHyrox');
        const focusMode = document.getElementById('focus-mode-container');
        const fullMode = document.getElementById('full-mode-container');

        window.toggleDashboardMode = function () {
            if (focusMode && focusMode.classList.contains('view-hidden')) {
                focusMode.classList.remove('view-hidden');
                if (fullMode) fullMode.classList.add('view-hidden');
                localStorage.setItem('dashboard_view_preference', 'focus');
            } else {
                if (focusMode) focusMode.classList.add('view-hidden');
                if (fullMode) fullMode.classList.remove('view-hidden');
                localStorage.setItem('dashboard_view_preference', 'full');
                if (window.animateLoLBars) setTimeout(window.animateLoLBars, 80);
            }
        };

        if (btnGym && btnHyrox) {
            function updateModeUI(mode) {
                const isGym = mode === 'gym';
                const showEl = (el) => { if (el) { el.classList.remove('hidden'); el.style.display = 'block'; } };
                const hideEl = (el) => { if (el) { el.classList.add('hidden'); el.style.display = 'none'; } };
                const showFlex = (el) => { if (el) { el.classList.remove('hidden'); el.style.display = 'flex'; } };

                if (isGym) {
                    showEl(heroGymFocus); hideEl(heroHyroxFocus);
                    showFlex(heroGymBtn); hideEl(heroHyroxBtn);
                    if (heroGym) heroGym.style.display = 'block';
                    if (heroHyrox) heroHyrox.style.display = 'none';
                    btnGym.className = 'mode-btn active-gym';
                    btnHyrox.className = 'mode-btn';
                } else {
                    hideEl(heroGymFocus); showEl(heroHyroxFocus);
                    hideEl(heroGymBtn); showFlex(heroHyroxBtn);
                    if (heroGym) heroGym.style.display = 'none';
                    if (heroHyrox) heroHyrox.style.display = 'block';
                    btnHyrox.className = 'mode-btn active-hyrox';
                    btnGym.className = 'mode-btn';
                }
                localStorage.setItem('dashboard_mode', mode);
            }

            btnGym.addEventListener('click', () => updateModeUI('gym'));
            btnHyrox.addEventListener('click', () => updateModeUI('hyrox'));

            const savedMode = localStorage.getItem('dashboard_mode');
            if (savedMode === 'hyrox') updateModeUI('hyrox');

            const savedView = localStorage.getItem('dashboard_view_preference');
            if (savedView === 'full' && focusMode && fullMode) {
                focusMode.classList.add('view-hidden');
                fullMode.classList.remove('view-hidden');
                if (window.animateLoLBars) setTimeout(window.animateLoLBars, 120);
            }
        }
    } catch (e) { console.error('Error in Mode Switcher:', e); }

    // ── Radar de Balance de Fuerza ───────────────────────────────────────────
    try {
        function createRadarChart(canvasId) {
            const ctx = document.getElementById(canvasId);
            if (!ctx || typeof Chart === 'undefined') return;
            const rf = cfg.ratiosFuerza || {};
            new Chart(ctx, {
                type: 'radar',
                data: {
                    labels: ['Empuje V.', 'Tracción V.', 'Empuje H.', 'Tracción H.', 'Dominancia R.', 'Dominancia C.'],
                    datasets: [{
                        label: 'Balance Actual',
                        data: [
                            rf.empujeVertical || 0, rf.traccionVertical || 0,
                            rf.empujeHorizontal || 0, rf.traccionHorizontal || 0,
                            rf.dominanciaRodilla || 0, rf.dominanciaCadera || 0,
                        ],
                        backgroundColor: 'rgba(34,211,238,0.2)',
                        borderColor: '#22d3ee',
                        pointBackgroundColor: '#22d3ee',
                        borderWidth: 2,
                    }]
                },
                options: {
                    scales: {
                        r: {
                            angleLines: { color: 'rgba(255,255,255,0.1)' },
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            pointLabels: { color: '#94a3b8', font: { size: 10 } },
                            ticks: { display: false },
                            suggestedMin: 0, suggestedMax: 100,
                        }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }
        createRadarChart('ratiosFuerzaChartFull');
    } catch (e) { console.error('Error in Radar Charts:', e); }

    // ── Widget de Gamificación (fetch) ────────────────────────────────────────
    try {
        const gamiWidget = document.getElementById('hero-panel-widget');
        if (gamiWidget && cfg.gamiWidgetUrl) {
            fetch(cfg.gamiWidgetUrl)
                .then(r => r.text())
                .then(html => { gamiWidget.innerHTML = html; })
                .catch(err => console.error('Error loading gami widget:', err));
        }
    } catch (e) { console.error('Error in Gami Widget:', e); }
});
