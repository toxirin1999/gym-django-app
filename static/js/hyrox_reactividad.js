/**
 * hyrox_reactividad.js — Phase Reactividad 1C
 *
 * Capa de reactividad AJAX para guardar sesiones Hyrox sin reload.
 * Tres capas visibles: Recibido → Procesado → Actualizado.
 *
 * Progressive enhancement: si JS no está disponible, el form POST
 * tradicional sigue siendo válido (action ya configurado en el template).
 *
 * Restricciones:
 * - Pulso NO se recalcula en frontend: el JSON del backend es la verdad
 * - No depende de jQuery
 * - No modifica datos en BD
 * - XSS: textContent para datos de usuario, innerHTML solo para estructuras controladas
 */

(function () {
  'use strict';

  /* ── Estado global anti-doble-click ─────────────────────────── */
  var guardando = false;

  /* ── Punto de entrada: interceptar submit del formulario ──────── */
  function init() {
    var form = document.getElementById('formRegistrarEntrenamiento')
               || document.getElementById('rb-form');
    if (!form) return;

    // Agregar id canónico si solo tiene rb-form
    if (!form.id || form.id !== 'formRegistrarEntrenamiento') {
      form.id = 'formRegistrarEntrenamiento';
    }

    form.addEventListener('submit', handleAjaxSave);
  }

  /**
   * handleAjaxSave — Controller principal del flujo AJAX.
   * Reemplaza el submit tradicional cuando JS está disponible.
   */
  function handleAjaxSave(event) {
    // Anti-doble-click
    if (guardando) {
      event.preventDefault();
      return;
    }

    event.preventDefault();

    var form = event.target || event.currentTarget;
    var btnGuardar = form.querySelector('[data-submit-btn]')
                     || form.querySelector('.rb-wiz-btn--submit');

    // Extraer objective_id y session_id de la URL
    var urlMatch = window.location.pathname.match(/\/registrar-entrenamiento\/(\d+)\/(\d+)\//);
    var objective_id, session_id;

    if (urlMatch) {
      objective_id = urlMatch[1];
      session_id   = urlMatch[2];
    } else {
      var urlMatch2 = window.location.pathname.match(/\/registrar-entrenamiento\/(\d+)\//);
      if (urlMatch2) {
        objective_id = urlMatch2[1];
        var sesionEl = document.querySelector('[data-session-id]');
        session_id   = sesionEl ? sesionEl.getAttribute('data-session-id') : null;
      }
    }

    if (!objective_id || !session_id) {
      mostrarError('No se pudo identificar la sesión. Usa el botón de abajo para guardar de forma tradicional.', form);
      return;
    }

    var apiUrl = '/hyrox/api/guardar-sesion/' + objective_id + '/' + session_id + '/';

    // Fase 1: Recibido — deshabilitar, spinner
    guardando = true;
    setBotonEstado(btnGuardar, 'guardando');
    mostrarEstadoGuardado('guardando');

    var formData = new FormData(form);

    fetch(apiUrl, {
      method: 'POST',
      body: formData,
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(function (response) {
      if (!response.ok) {
        // El servidor respondió con 4xx/5xx
        return response.json().then(function (data) {
          throw { status: response.status, data: data };
        }).catch(function (err) {
          if (err.status) throw err;
          throw { status: response.status, data: { error: 'Error del servidor (' + response.status + ')' } };
        });
      }
      return response.json();
    })
    .then(function (payload) {
      if (!payload.success) {
        var msg = (payload.error) || 'El servidor rechazó la sesión.';
        throw { status: 400, data: payload, mensajeUsuario: msg };
      }

      // Fase 2: Procesado — confirmación antes de actualizar
      setBotonEstado(btnGuardar, 'guardado');
      mostrarEstadoGuardado('guardado');

      // Fase 3: Actualizado — esperar y aplicar cambios
      setTimeout(function () {
        mostrarEstadoGuardado('actualizando');

        setTimeout(function () {
          updateDashboardFromJSON(payload);
          mostrarMensajes(payload.messages || []);

          // Redirigir al dashboard tras confirmar la actualización
          setTimeout(function () {
            window.location.href = '/hyrox/dashboard/';
          }, 1200);
        }, 500);
      }, 800);
    })
    .catch(function (err) {
      guardando = false;
      setBotonEstado(btnGuardar, 'error');
      limpiarEstadoGuardado();

      var mensajeUsuario;
      if (err && err.mensajeUsuario) {
        mensajeUsuario = err.mensajeUsuario;
      } else if (err && err.data && err.data.error) {
        mensajeUsuario = err.data.error;
      } else if (err instanceof TypeError) {
        // Network error / timeout
        mensajeUsuario = 'Sin conexión. Comprueba tu red e intenta de nuevo.';
      } else {
        mensajeUsuario = 'Error inesperado al guardar.';
      }

      mostrarError(mensajeUsuario, form);
    });
  }

  /* ── Fase 2: Actualización selectiva del dashboard ────────────── */

  /**
   * updateDashboardFromJSON — Actualiza el dashboard con datos del payload.
   * Principio: si un campo falta en el JSON, se ignora sin romper.
   * No recalcula nada: el backend es la fuente de verdad.
   */
  function updateDashboardFromJSON(payload) {
    if (!payload || typeof payload !== 'object') return;

    // 1. Mensajes (ya gestionados por mostrarMensajes, se llama por separado)

    // 2. Readiness score
    if (payload.readiness_score !== undefined) {
      actualizarReadiness(payload.readiness_score);
    }

    // 3. Pulso (bloque completo, renderizado desde JSON)
    if (payload.pulso && typeof payload.pulso === 'object') {
      actualizarPulso(payload.pulso);
    }

    // 4. Hyrox decision
    if (payload.hyrox_decision && typeof payload.hyrox_decision === 'object') {
      actualizarHyroxDecision(payload.hyrox_decision);
    }

    // 5. Próximas sesiones
    if (Array.isArray(payload.sesiones_proximas)) {
      actualizarSesionesProximas(payload.sesiones_proximas);
    }
  }

  function actualizarReadiness(score) {
    // Selector canónico: data-readiness (añadido en dashboard.html)
    var targets = document.querySelectorAll('[data-readiness]');
    targets.forEach(function (el) {
      el.textContent = score;
    });

    // Selector legacy: data-readiness-score (ya existía)
    var legacyTargets = document.querySelectorAll('[data-readiness-score]');
    legacyTargets.forEach(function (el) {
      el.textContent = score + '%';
      el.setAttribute('data-readiness-score', score);
    });

    // Barra de readiness si existe
    var barFill = document.querySelector('.rb-rd-bar-fill');
    if (barFill) {
      barFill.style.width = Math.min(100, score) + '%';
    }

    // Color semáforo
    var color = score >= 70 ? 'var(--ok)' :
                score >= 45 ? 'var(--warn)' : 'var(--danger)';

    // Número grande rb-rd-num
    var rdNum = document.querySelector('.rb-rd-num');
    if (rdNum) rdNum.style.color = color;
  }

  function actualizarPulso(pulsoData) {
    var card = document.getElementById('pulso-card');
    if (!card) return;

    var estado = pulsoData.pulso || 'silencioso';
    var postura = (pulsoData.postura && pulsoData.postura.estructura) || 'minima';

    // Actualizar clases del card
    card.className = 'pulso-card pulso-' + estado + ' pulso-' + postura;

    // Badge de estado
    var badge = card.querySelector('.pulso-state-badge');
    if (badge) {
      badge.className = 'pulso-state-badge pulso-' + estado;
      if (estado === 'protegiendo') {
        badge.innerHTML = '<i class="fas fa-shield"></i> Protegiendo';
      } else if (estado === 'progresando') {
        badge.innerHTML = '<i class="fas fa-arrow-up"></i> Progresando';
      } else {
        badge.innerHTML = '<i class="fas fa-circle"></i> Silencioso';
      }
    }

    // Mensaje del pulso
    var msg = card.querySelector('.pulso-msg');
    if (msg && pulsoData.contexto) {
      // textContent para evitar XSS — contexto es texto plano del backend
      msg.textContent = pulsoData.contexto;
    }

    // Badge inline en la sección de decision
    var hdBadge = document.querySelector('.hd-pulso-badge');
    if (hdBadge) {
      hdBadge.className = 'hd-pulso-badge hd-pulso--' + estado;
      if (estado === 'protegiendo') {
        hdBadge.innerHTML = '<i class="fas fa-shield"></i> Protegiendo';
      } else if (estado === 'progresando') {
        hdBadge.innerHTML = '<i class="fas fa-arrow-up"></i> Progresando';
      } else {
        hdBadge.innerHTML = '<i class="fas fa-circle"></i> Silencioso';
      }
    }
  }

  function actualizarHyroxDecision(decision) {
    var wrapper = document.getElementById('hyrox-decision-buttons');
    if (!wrapper) return;

    // Solo actualizar el CTA principal para evitar re-renderizar toda la sección
    var actionEl = wrapper.querySelector('.hd-decision-action');
    if (actionEl) {
      var puede = decision.puede_ejecutar_plan;
      if (puede !== undefined) {
        if (puede) {
          actionEl.classList.remove('is-disabled');
        } else {
          actionEl.classList.add('is-disabled');
        }
      }
    }

    // Actualizar clase del contenedor decision
    var decisionSection = document.querySelector('.hd-decision');
    if (decisionSection && decision.estado) {
      // Eliminar clases previas de estado
      var clases = Array.from(decisionSection.classList);
      clases.forEach(function (c) {
        if (c.startsWith('hd-decision--')) {
          decisionSection.classList.remove(c);
        }
      });
      decisionSection.classList.add('hd-decision--' + decision.estado);
    }
  }

  function actualizarSesionesProximas(sesiones) {
    var container = document.getElementById('sesiones-proximas-list');
    if (!container) return;

    if (sesiones.length === 0) {
      container.textContent = 'Sin sesiones próximas programadas.';
      return;
    }

    // Construir lista simple con datos del servidor
    var html = '';
    sesiones.forEach(function (s) {
      // Usar textContent indirectamente para campos de usuario
      var fechaSegura  = String(s.fecha  || '').replace(/[<>&"']/g, '');
      var tituloSeguro = String(s.titulo || '').replace(/[<>&"']/g, '');
      var estadoSeguro = String(s.estado || '').replace(/[<>&"']/g, '');

      html += '<div class="rb-dia rb-dia--proxima" style="margin-bottom:6px;">'
            + '<div class="rb-dia-body">'
            + '<div class="rb-dia-tipo">' + fechaSegura + '</div>'
            + '<div class="rb-dia-title">' + tituloSeguro + '</div>'
            + '<div class="rb-dia-acts">' + estadoSeguro + '</div>'
            + '</div></div>';
    });
    container.innerHTML = html;
  }

  /* ── Toast notifications ─────────────────────────────────────── */

  /**
   * mostrarMensajes — Renderiza array de mensajes como toasts temporales.
   * @param {Array} messages — [{level: 'success'|'info'|'warning'|'error', text: '...'}]
   */
  function mostrarMensajes(messages) {
    if (!Array.isArray(messages) || messages.length === 0) return;

    var container = obtenerOCrearContenedorMensajes();

    messages.forEach(function (msg, i) {
      var level = msg.level || 'info';
      var text  = msg.text  || '';

      var toast = document.createElement('div');
      toast.className = 'hx-toast hx-toast--' + level;
      toast.style.cssText = [
        'position:relative',
        'display:flex',
        'align-items:flex-start',
        'gap:8px',
        'padding:12px 14px',
        'border-radius:4px',
        'font-family:-apple-system,system-ui,sans-serif',
        'font-size:13px',
        'line-height:1.4',
        'box-shadow:0 4px 12px rgba(0,0,0,.15)',
        'animation:hxToastIn .25s ease both',
        'max-width:380px',
        'word-break:break-word'
      ].join(';');

      var bg, borderColor;
      if (level === 'success') {
        bg = '#0a8854'; borderColor = '#077a4b';
      } else if (level === 'warning') {
        bg = '#b45309'; borderColor = '#92400e';
      } else if (level === 'error') {
        bg = '#b91c1c'; borderColor = '#991b1b';
      } else {
        bg = '#1e40af'; borderColor = '#1d4ed8';
      }
      toast.style.background = bg;
      toast.style.border = '1px solid ' + borderColor;
      toast.style.color = '#fff';

      // textContent para el texto — evita XSS
      var textNode = document.createElement('span');
      textNode.textContent = text;
      toast.appendChild(textNode);

      container.appendChild(toast);

      var duracion = (level === 'warning' || level === 'error') ? 5000 : 3000;
      setTimeout(function () {
        toast.style.animation = 'hxToastOut .2s ease both';
        setTimeout(function () {
          if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 220);
      }, duracion + i * 200);
    });
  }

  function obtenerOCrearContenedorMensajes() {
    var container = document.getElementById('messages-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'messages-container';
      container.style.cssText = [
        'position:fixed',
        'top:20px',
        'right:20px',
        'z-index:9999',
        'display:flex',
        'flex-direction:column',
        'gap:8px',
        'pointer-events:none'
      ].join(';');
      document.body.appendChild(container);
    }
    return container;
  }

  /* ── Error modal ─────────────────────────────────────────────── */

  /**
   * mostrarError — Muestra un panel de error con opciones de reintentar o enviar
   * de forma tradicional.
   */
  function mostrarError(mensaje, form) {
    // Eliminar modal previo si existe
    var previo = document.getElementById('hx-error-modal');
    if (previo) previo.parentNode.removeChild(previo);

    var overlay = document.createElement('div');
    overlay.id = 'hx-error-modal';
    overlay.style.cssText = [
      'position:fixed',
      'inset:0',
      'background:rgba(0,0,0,.55)',
      'z-index:10000',
      'display:flex',
      'align-items:flex-end',
      'justify-content:center',
      'padding:0 16px 16px'
    ].join(';');

    var sheet = document.createElement('div');
    sheet.style.cssText = [
      'background:#1a1a1a',
      'border-radius:12px',
      'padding:24px 20px 28px',
      'width:100%',
      'max-width:480px',
      'box-shadow:0 8px 32px rgba(0,0,0,.4)'
    ].join(';');

    var eyebrow = document.createElement('div');
    eyebrow.style.cssText = 'font-family:-apple-system,sans-serif;font-size:10px;font-weight:700;letter-spacing:.15em;color:#ef4444;text-transform:uppercase;margin-bottom:8px;';
    eyebrow.textContent = 'Error al guardar';

    var titulo = document.createElement('div');
    titulo.style.cssText = 'font-family:-apple-system,sans-serif;font-size:17px;font-weight:700;color:#fff;margin-bottom:8px;line-height:1.3;';
    titulo.textContent = mensaje; // textContent — evita XSS

    var sub = document.createElement('p');
    sub.style.cssText = 'font-family:-apple-system,sans-serif;font-size:13px;color:rgba(255,255,255,.6);line-height:1.5;margin:0 0 20px;';
    sub.textContent = 'Tus datos no se han perdido. Elige cómo continuar.';

    var btnRetry = document.createElement('button');
    btnRetry.style.cssText = 'width:100%;padding:14px;background:#ff6b00;color:#fff;border:none;border-radius:8px;font-family:-apple-system,sans-serif;font-size:14px;font-weight:700;cursor:pointer;margin-bottom:10px;';
    btnRetry.textContent = 'Reintentar';
    btnRetry.addEventListener('click', function () {
      document.body.removeChild(overlay);
      // Simular nuevo intento: re-habilitar botón y disparar submit
      var btnGuardar = form ? (form.querySelector('[data-submit-btn]') || form.querySelector('.rb-wiz-btn--submit')) : null;
      if (btnGuardar) setBotonEstado(btnGuardar, 'listo');
      if (form) {
        // Volver a enviar sin pasar por rbSubmit() — disparar handleAjaxSave directamente
        form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: false }));
      }
    });

    var btnTradicional = document.createElement('button');
    btnTradicional.style.cssText = 'width:100%;padding:14px;background:transparent;color:rgba(255,255,255,.7);border:1.5px solid rgba(255,255,255,.2);border-radius:8px;font-family:-apple-system,sans-serif;font-size:14px;cursor:pointer;';
    btnTradicional.textContent = 'Enviar de forma tradicional';
    btnTradicional.addEventListener('click', function () {
      document.body.removeChild(overlay);
      enviarTradicional(form);
    });

    sheet.appendChild(eyebrow);
    sheet.appendChild(titulo);
    sheet.appendChild(sub);
    sheet.appendChild(btnRetry);
    sheet.appendChild(btnTradicional);
    overlay.appendChild(sheet);
    document.body.appendChild(overlay);

    // Cerrar al clic en el overlay (fuera del sheet)
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) {
        document.body.removeChild(overlay);
      }
    });
  }

  /* ── Fallback POST tradicional ───────────────────────────────── */
  function enviarTradicional(form) {
    if (!form) { window.location.href = '/hyrox/dashboard/'; return; }
    // Quitar el event listener para no interceptar el submit
    form.removeEventListener('submit', handleAjaxSave);
    form.submit();
  }

  /* ── Estado del botón de guardar ────────────────────────────── */
  function setBotonEstado(btn, estado) {
    if (!btn) return;
    var textEl = btn.querySelector('[data-btn-text]') || btn.querySelector('#btnText') || btn;

    if (estado === 'guardando') {
      btn.disabled = true;
      btn.style.opacity = '0.7';
      if (textEl !== btn) {
        textEl.textContent = 'Guardando...';
      } else {
        btn.setAttribute('data-original-text', btn.textContent);
        btn.textContent = 'Guardando...';
      }
      // Spinner inline CSS
      var spinner = btn.querySelector('.hx-spinner');
      if (!spinner) {
        spinner = document.createElement('span');
        spinner.className = 'hx-spinner';
        spinner.style.cssText = 'display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,.4);border-top-color:#fff;border-radius:50%;animation:hxSpin .6s linear infinite;margin-left:8px;vertical-align:middle;flex-shrink:0;';
        btn.appendChild(spinner);
      }
    } else if (estado === 'guardado') {
      btn.disabled = true;
      btn.style.opacity = '1';
      btn.style.background = 'var(--ok, #0a8854)';
      var sp = btn.querySelector('.hx-spinner');
      if (sp) sp.parentNode.removeChild(sp);
      if (textEl !== btn) {
        textEl.textContent = 'Guardado';
      } else {
        btn.textContent = 'Guardado';
      }
    } else if (estado === 'error') {
      btn.disabled = false;
      btn.style.opacity = '1';
      btn.style.background = '';
      var sp2 = btn.querySelector('.hx-spinner');
      if (sp2) sp2.parentNode.removeChild(sp2);
      if (textEl !== btn) {
        textEl.textContent = 'Error — Reintentar';
      } else {
        btn.textContent = 'Error — Reintentar';
      }
    } else {
      // 'listo'
      btn.disabled = false;
      btn.style.opacity = '1';
      btn.style.background = '';
      var sp3 = btn.querySelector('.hx-spinner');
      if (sp3) sp3.parentNode.removeChild(sp3);
      var orig = btn.getAttribute('data-original-text');
      if (orig) {
        if (textEl !== btn) textEl.textContent = orig;
        else btn.textContent = orig;
      }
    }
  }

  /* ── Indicador de estado en pantalla ────────────────────────── */
  var _estadoOverlay = null;

  function mostrarEstadoGuardado(fase) {
    limpiarEstadoGuardado();

    var el = document.createElement('div');
    el.id = 'hx-estado-guardado';
    _estadoOverlay = el;

    el.style.cssText = [
      'position:fixed',
      'bottom:24px',
      'left:50%',
      'transform:translateX(-50%)',
      'z-index:9998',
      'background:rgba(10,10,10,.92)',
      'color:#fff',
      'padding:10px 20px',
      'border-radius:24px',
      'font-family:-apple-system,system-ui,sans-serif',
      'font-size:13px',
      'font-weight:600',
      'letter-spacing:.02em',
      'display:flex',
      'align-items:center',
      'gap:8px',
      'white-space:nowrap',
      'pointer-events:none',
      'animation:hxToastIn .2s ease both'
    ].join(';');

    var dot = document.createElement('span');
    dot.style.cssText = 'width:8px;height:8px;border-radius:50%;flex-shrink:0;';

    var label = document.createElement('span');

    if (fase === 'guardando') {
      dot.style.background = '#f59e0b';
      dot.style.animation = 'hxBlink 1s ease-in-out infinite';
      label.textContent = 'Guardando...';
    } else if (fase === 'guardado') {
      dot.style.background = '#0a8854';
      label.textContent = 'Guardado. Actualizando estado…';
    } else if (fase === 'actualizando') {
      dot.style.background = '#ff6b00';
      dot.style.animation = 'hxBlink 0.7s ease-in-out infinite';
      label.textContent = 'Actualizando dashboard…';
    }

    el.appendChild(dot);
    el.appendChild(label);
    document.body.appendChild(el);
  }

  function limpiarEstadoGuardado() {
    var prev = document.getElementById('hx-estado-guardado');
    if (prev && prev.parentNode) prev.parentNode.removeChild(prev);
    _estadoOverlay = null;
  }

  /* ── CSS keyframes inyectados una sola vez ───────────────────── */
  function inyectarCSS() {
    if (document.getElementById('hx-reactividad-styles')) return;
    var style = document.createElement('style');
    style.id = 'hx-reactividad-styles';
    style.textContent = [
      '@keyframes hxSpin { to { transform: rotate(360deg); } }',
      '@keyframes hxToastIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }',
      '@keyframes hxToastOut { from { opacity:1; transform:translateY(0); } to { opacity:0; transform:translateY(8px); } }',
      '@keyframes hxBlink { 0%,100%{opacity:1} 50%{opacity:.3} }'
    ].join('\n');
    document.head.appendChild(style);
  }

  /**
   * handleAjaxSaveFromData — Entry point alternativo para el wizard de registro.
   * Llamado por rbConfirmSave() cuando el form usa type="button" (no submit event).
   * @param {HTMLFormElement} form
   * @param {string} apiUrl
   */
  function handleAjaxSaveFromData(form, apiUrl) {
    if (guardando) return;
    if (!form || !apiUrl) return;

    var btnGuardar = form.querySelector('[data-submit-btn]')
                     || form.querySelector('.rb-wiz-btn--submit');

    guardando = true;
    setBotonEstado(btnGuardar, 'guardando');
    mostrarEstadoGuardado('guardando');

    var formData = new FormData(form);

    fetch(apiUrl, {
      method: 'POST',
      body: formData,
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(function (response) {
      if (!response.ok) {
        return response.json().then(function (data) {
          throw { status: response.status, data: data };
        }).catch(function (err) {
          if (err.status) throw err;
          throw { status: response.status, data: { error: 'Error del servidor (' + response.status + ')' } };
        });
      }
      return response.json();
    })
    .then(function (payload) {
      if (!payload.success) {
        var msg = payload.error || 'El servidor rechazó la sesión.';
        throw { status: 400, data: payload, mensajeUsuario: msg };
      }

      setBotonEstado(btnGuardar, 'guardado');
      mostrarEstadoGuardado('guardado');

      setTimeout(function () {
        mostrarEstadoGuardado('actualizando');

        setTimeout(function () {
          updateDashboardFromJSON(payload);
          mostrarMensajes(payload.messages || []);

          setTimeout(function () {
            window.location.href = '/hyrox/dashboard/';
          }, 1200);
        }, 500);
      }, 800);
    })
    .catch(function (err) {
      guardando = false;
      setBotonEstado(btnGuardar, 'error');
      limpiarEstadoGuardado();

      var mensajeUsuario;
      if (err && err.mensajeUsuario) {
        mensajeUsuario = err.mensajeUsuario;
      } else if (err && err.data && err.data.error) {
        mensajeUsuario = err.data.error;
      } else if (err instanceof TypeError) {
        mensajeUsuario = 'Sin conexión. Comprueba tu red e intenta de nuevo.';
      } else {
        mensajeUsuario = 'Error inesperado al guardar.';
      }

      mostrarError(mensajeUsuario, form);
    });
  }

  /* ── API pública (usada por el template del dashboard) ────────── */
  window.updateDashboardFromJSON    = updateDashboardFromJSON;
  window.hyroxReactividad = {
    init:                  init,
    handleAjaxSave:        handleAjaxSave,
    handleAjaxSaveFromData: handleAjaxSaveFromData,
    mostrarMensajes:       mostrarMensajes,
    mostrarError:          mostrarError,
    enviarTradicional:     enviarTradicional
  };

  /* ── Inicialización ──────────────────────────────────────────── */
  inyectarCSS();

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

}());
