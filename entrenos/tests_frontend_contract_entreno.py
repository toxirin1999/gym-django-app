from pathlib import Path

from django.template.loader import render_to_string
from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parent


class EntrenamientoActivoContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source = (ROOT / "templates/entrenos/entrenamiento_activo.html").read_text()

    def test_finalizar_se_habilita_desde_una_serie_y_al_completar_no_hay_pill_activa(self):
        self.assertIn("const puedeFinalizar=comp>=1;", self.source)
        self.assertIn("btnFinal.disabled=!puedeFinalizar;", self.source)
        self.assertIn("if(comp>=total && total>0)", self.source)
        self.assertIn("pill.classList.add('hecha')", self.source)

    def test_cierre_distingue_revision_de_guardado_definitivo(self):
        """El CTA fijo abre una revisión; solo el modal confirma el guardado."""
        self.assertIn('id="btn-mostrar-resumen"', self.source)
        self.assertIn('<span>Revisar y finalizar</span>', self.source)
        self.assertIn('id="btn-confirmar-guardar">Guardar entrenamiento</button>', self.source)

    def test_calculadora_unica_no_afirma_igualdad_si_hay_resto(self):
        self.assertEqual(self.source.count("function calcularDesgloseDiscos("), 1)
        self.assertIn("0.5,0.25", self.source)
        self.assertIn("No representable con los discos disponibles", self.source)
        self.assertNotIn("const sizes=[20,15,10,5,2.5,1];", self.source)

    def test_objetivo_tope_no_mezcla_rango_original_en_superficies(self):
        self.assertIn('data-reps-min="{% if ejercicio.sugerencia_tope %}{{ ejercicio.reps_objetivo }}', self.source)
        self.assertIn('data-reps-max="{% if ejercicio.sugerencia_tope %}{{ ejercicio.reps_objetivo }}', self.source)
        self.assertIn('Objetivo de tope: {{ ejercicio.reps_sugeridas_tope }} reps', self.source)
        self.assertIn('🔝 Tope · {{ ejercicio.reps_sugeridas_tope }} {% if ejercicio.usa_distancia %}m', self.source)

    def test_tiempo_no_se_suma_como_repeticiones_en_modal(self):
        self.assertIn("const usaTiempo = document.getElementById('card-'+fid)?.dataset.usaTiempo === '1';", self.source)
        self.assertIn("usaTiempo,", self.source)
        self.assertIn("segundos:cantidad", self.source)
        self.assertIn("segundosTrabajo+=m.segundos", self.source)
        self.assertIn("segundosTrabajo+' s'", self.source)

    def test_descripcion_rpe_temporal_no_habla_de_reps_en_reserva(self):
        self.assertIn("const RPE_DESC_TIEMPO=", self.source)
        self.assertIn("descripcionRPE(fidSn,valor)", self.source)
        self.assertIn("control técnico sostenible", self.source)

    def test_registro_distingue_rpe_aproximacion_y_resultado_del_plan(self):
        self.assertIn("aria-pressed=\"false\"", self.source)
        self.assertIn("b.setAttribute('aria-pressed'", self.source)
        self.assertIn('name="{{ ejercicio.form_id }}_aproximacion_{{ sn }}"', self.source)
        self.assertIn("serie.esAproximacion", self.source)
        self.assertIn("resultadoPlanSerie", self.source)
        self.assertIn("Por debajo del rango", self.source)
        self.assertIn("Serie de trabajo", self.source)
        self.assertIn("Marcar como aproximación", self.source)
        self.assertIn("Es aproximación", self.source)
        self.assertIn("No cuenta como trabajo", self.source)
        self.assertIn("actualizarControlAproximacion", self.source)
        # El pie fijo incluye la barra de sesión, el área segura y una zona de
        # respiración para que la última serie nunca quede tapada.
        self.assertIn("padding-bottom:calc(128px + env(safe-area-inset-bottom) + 32px)", self.source)
        self.assertIn("padding-bottom:calc(96px + env(safe-area-inset-bottom))", self.source)

    def test_feedback_de_serie_separa_tecnica_y_cumplimiento(self):
        self.assertIn("function feedbackSerieHTML", self.source)
        self.assertIn('class="serie-feedback"', self.source)
        self.assertIn('class="serie-technique"', self.source)
        self.assertIn("Técnica: buena", self.source)
        self.assertIn("Por debajo del rango", self.source)

    def test_estimacion_1rm_solo_aparece_tras_guardar_serie_real(self):
        self.assertIn('id="orm-module-{{ ejercicio.form_id }}" hidden', self.source)
        self.assertIn("if(!esAproximacion)actualizarORM(fid,sn);", self.source)
        self.assertNotIn("calcularDiscosInline(fid,sn,peso);\n    actualizarORM(fid,sn);", self.source)
        self.assertIn("series de trabajo ya guardadas", self.source)

    def test_cierre_de_ejercicio_es_local_y_ofrece_continuar(self):
        self.assertIn("function resumenDeEjercicio", self.source)
        self.assertIn("Ejercicio exigente registrado", self.source)
        self.assertIn("Continuar con ", self.source)
        self.assertNotIn("setTimeout(()=>{if(STATE.ejActual===ejIdxAtCompletion)navEjercicio(1);},2000);", self.source)

    def test_distancia_con_carga_mantiene_el_peso_en_la_ejecucion(self):
        self.assertIn("{% if ejercicio.usa_peso or ejercicio.usa_distancia %}", self.source)
        self.assertIn("kg · {{ ejercicio.repeticiones_anterior }} m", self.source)

    def test_distancia_no_se_presenta_ni_autoregula_como_repeticiones(self):
        self.assertIn("{% elif ejercicio.usa_distancia %}<span class=\"chip-n\">{{ ejercicio.repeticiones }} m</span>", self.source)
        self.assertIn("🔝 Tope · {{ ejercicio.reps_sugeridas_tope }} {% if ejercicio.usa_distancia %}m", self.source)
        self.assertIn("const usaDistancia = panelSig.dataset.usaDistancia === '1';", self.source)
        self.assertIn("if (!usaPeso || usaDistancia) return;", self.source)

    def test_referencia_ultima_sesion_es_parte_del_flujo_de_registro(self):
        """La referencia queda entre carga/reps y RPE, no oculta en historial."""
        referencia = self.source.index('class="peso-ultima-vez"')
        rpe = self.source.index('{# RPE — grid de botones táctiles #}')
        self.assertLess(referencia, rpe)
        self.assertIn('peso-ultima-vez__label">Última vez', self.source)
        self.assertIn('peso-ultima-vez__value', self.source)
        self.assertIn('peso-ultima-vez__cue', self.source)
        self.assertIn('aria-label="Referencia de la última sesión"', self.source)
        self.assertIn('repeticiones_anterior|floatformat:"0"', self.source)

    def test_composicion_activa_conserva_jerarquia_del_mockup_aprobado(self):
        """La UI compacta sigue exponiendo la secuencia visual de decisión."""
        self.assertIn('ACTIVE WORKOUT COMPOSITION', self.source)
        self.assertIn('.ex-header-combo::after', self.source)
        self.assertIn('.peso-reps-grid{grid-template-columns:1fr', self.source)
        self.assertIn('.peso-ultima-vez__rpe', self.source)
        self.assertIn('grid-auto-flow:column', self.source)
        self.assertIn('.contingencia-grid .btn-tope-maquina.activo', self.source)

    def test_navegacion_solo_muestra_flecha_aplicable(self):
        self.assertIn('function actualizarNavegacion()', self.source)
        self.assertIn('const hayAnterior=STATE.ejActual>0;', self.source)
        self.assertIn('const haySiguiente=STATE.ejActual<cards.length-1;', self.source)
        self.assertIn('anterior.hidden=!hayAnterior;', self.source)
        self.assertIn('siguiente.hidden=!haySiguiente;', self.source)


class BriefingRenderContractTests(SimpleTestCase):
    def test_dead_hang_se_renderiza_en_segundos_sin_kg_reps_ni_calentamiento(self):
        html = render_to_string("entrenos/briefing_entrenamiento.html", {
            "ejercicios": [{
                "nombre": "Dead Hang", "series": 3, "repeticiones": 45,
                "tipo_progresion": "progresion_tiempo", "usa_tiempo": True,
                "usa_peso": False, "peso_kg": 80, "peso_recomendado_kg": 80,
                "aproximaciones": None, "alertas": [],
            }],
            "briefing": {"mensajes": [], "instrucciones": [], "necesita_deload": False},
            "cambios_plan": [], "puede_iniciar_sesion": True, "url_sesion": "/",
        })
        row = html[html.index("Dead Hang"):html.index("Dead Hang") + 1800]
        self.assertIn("45 s", row)
        self.assertNotIn("45 reps", row)
        self.assertNotIn("80 kg", row)
        self.assertNotIn("Calentamiento", row)
