from pathlib import Path
from unittest import TestCase


TEMPLATE = (
    Path(__file__).resolve().parent
    / "templates"
    / "entrenos"
    / "entrenamiento_activo.html"
)


class EdicionSeriesUIRegressionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source = TEMPLATE.read_text(encoding="utf-8")
        cls.guardar = cls.source.split("function guardarSeriePanel", 1)[1].split(
            "function editarSeriePanel", 1
        )[0]
        cls.editar = cls.source.split("function editarSeriePanel", 1)[1].split(
            "function detectarPR", 1
        )[0]
        cls.sincronizar = cls.source.split(
            "function sincronizarSeriesConfirmadasConFormulario", 1
        )[1].split("document.getElementById('btn-confirmar-guardar')", 1)[0]
        cls.confirmar = cls.source.split(
            "document.getElementById('btn-confirmar-guardar')", 1
        )[1].split("// Aviso al salir sin guardar", 1)[0]

    def test_editar_preserva_state_y_filas_posteriores(self):
        self.assertNotIn(".splice(", self.editar)
        self.assertNotIn("fila.remove()", self.editar)
        self.assertNotIn("Renumerar filas posteriores", self.editar)
        self.assertIn("_serieEnEdicion[fid] = sn", self.editar)

    def test_guardar_edicion_reemplaza_por_numero_sin_crecer(self):
        self.assertIn("const esEdicion = _serieEnEdicion[fid] === sn", self.guardar)
        self.assertIn("STATE.seriesCompletadas[fid][sn-1] =", self.guardar)
        self.assertIn("if(esEdicion)", self.guardar)
        self.assertNotIn("STATE.seriesCompletadas[fid].push(", self.guardar)

        reemplazo = self.guardar.index("STATE.seriesCompletadas[fid][sn-1] =")
        checkpoint = self.guardar.index("guardarCheckpoint()")
        fin_edicion = self.guardar.index("if(esEdicion)", checkpoint)
        self.assertLess(reemplazo, checkpoint)
        self.assertLess(checkpoint, fin_edicion)

    def test_guardar_edicion_actualiza_log_y_no_inicia_descanso(self):
        buscar_fila = self.guardar.index("querySelector('[data-sn=\"'+sn+'\"]')")
        crear_fila = self.guardar.index("document.createElement('div')")
        self.assertLess(buscar_fila, crear_fila)

        fin_edicion = self.guardar.index("if(esEdicion)", crear_fila)
        iniciar_descanso = self.guardar.index("iniciarDescanso(")
        self.assertLess(fin_edicion, iniciar_descanso)
        self.assertIn("delete _serieEnEdicion[fid]", self.guardar[fin_edicion:iniciar_descanso])
        self.assertIn("return", self.guardar[fin_edicion:iniciar_descanso])

    def test_confirmar_sincroniza_state_antes_de_construir_formdata(self):
        sincronizar = self.confirmar.index(
            "sincronizarSeriesConfirmadasConFormulario(form)"
        )
        construir_formdata = self.confirmar.index("new FormData(form)")
        self.assertLess(sincronizar, construir_formdata)

    def test_sincronizacion_copia_la_serie_confirmada_a_campos_nombrados(self):
        self.assertIn("Object.entries(STATE.seriesCompletadas", self.sincronizar)
        self.assertIn("serie.peso", self.sincronizar)
        self.assertIn("serie.reps", self.sincronizar)
        self.assertIn("serie.rpe", self.sincronizar)
        self.assertIn("peso-'+fid+'-'+sn", self.sincronizar)
        self.assertIn("reps-hid-'+fid+'-'+sn", self.sincronizar)
        self.assertIn("rpe-hid-'+fid+'-'+sn", self.sincronizar)
        self.assertIn("check-'+fid+'-'+sn", self.sincronizar)
        self.assertIn("checkbox.checked = true", self.sincronizar)
