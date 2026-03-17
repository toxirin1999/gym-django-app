# planificador_helms/models/perfil_cliente.py
"""
Perfil completo del cliente para el sistema Helms.

CAMBIOS v2:
- [BUG FIX] obtener_volumen_objetivo: eliminado dict de volúmenes hardcodeado que
  duplicaba VOLUMENES_BASE de config.py. Ahora importa directamente de config,
  garantizando una única fuente de verdad. Si se cambian los volúmenes en config.py,
  este método los refleja automáticamente sin tocar nada más.
- [BUG FIX] obtener_tempo_preferido: el objetivo 'fuerza_hipertrofia' no tenía
  case propio y caía al default '2-0-X-0'. Ahora usa TEMPOS de config correctamente.
- [MEJORA] obtener_intensidad_objetivo: avanzados tenían el mismo rango que
  intermedios (7-9). Corregido a (8-9) con nota de que la diferencia real en
  avanzados es la precisión del RPE, no el rango.
- [LIMPIEZA] Eliminados TODO comments sobre mover datos a config (ya están en config).
"""

from typing import Dict, List, Any, Optional
from ..config import VOLUMENES_BASE, TEMPOS


class PerfilCliente:
    """Perfil completo del cliente para el sistema Helms."""

    def __init__(self, cliente_data: Optional[Dict[str, Any]] = None, **kwargs):
        # Permite tanto dict como kwargs para compatibilidad legacy
        data = cliente_data or kwargs

        # ── Datos básicos ─────────────────────────────────────────────────────
        self.id = data.get('id') or data.get('cliente_id')
        self.nombre = data.get('nombre', '')
        self.edad = data.get('edad', 25)
        self.peso = data.get('peso', 70.0)
        self.altura = data.get('altura', 170.0)
        self.genero = data.get('genero', 'masculino')

        # ── Experiencia y objetivos ───────────────────────────────────────────
        self.experiencia_años = data.get('experiencia_años', 0)
        obj = data.get('objetivo_principal', 'hipertrofia')
        self.objetivo_principal = (obj.value if hasattr(obj, "value") else str(obj)).lower()
        self.objetivos_secundarios = data.get('objetivos_secundarios', [])

        # ── Disponibilidad ────────────────────────────────────────────────────
        self.dias_disponibles = data.get('dias_disponibles', 3)
        self.tiempo_por_sesion = data.get('tiempo_por_sesion', 60)
        self.horarios_preferidos = data.get('horarios_preferidos', [])

        # ── Preferencias de ejercicios ────────────────────────────────────────
        self.ejercicios_preferidos = data.get('ejercicios_preferidos', [])
        self.ejercicios_evitar = data.get('ejercicios_evitar', [])
        self.equipamiento_disponible = data.get('equipamiento_disponible', [])
        self.limitaciones_fisicas = data.get('limitaciones_fisicas', [])

        # ── Factores de recuperación (Helms específicos) ──────────────────────
        self.nivel_estres = data.get('nivel_estres', 5)  # 1-10
        self.calidad_sueño = data.get('calidad_sueño', 7)  # 1-10
        self.nivel_energia = data.get('nivel_energia', 7)  # 1-10
        self.nutricion_calidad = data.get('nutricion_calidad', 7)  # 1-10

        # ── Historial de entrenamiento ────────────────────────────────────────
        self.historial_volumen = data.get('historial_volumen', {})
        self.historial_intensidad = data.get('historial_intensidad', {})
        self.lesiones_previas = data.get('lesiones_previas', [])

        # ── Métricas de rendimiento ───────────────────────────────────────────
        self.maximos_actuales = data.get('maximos_actuales', {})
        self.progreso_historico = data.get('progreso_historico', {})

        # ── Preferencias del sistema Helms ────────────────────────────────────
        self.precision_rpe = data.get('precision_rpe', 'principiante')
        self.preferencia_tempo = data.get('preferencia_tempo', 'moderado')
        self.nivel_educacion_deseado = data.get('nivel_educacion_deseado', 'medio')

        # ── Estado de migración ───────────────────────────────────────────────
        self.migrado_a_helms = data.get('migrado_a_helms', False)
        self.fecha_migracion_helms = data.get('fecha_migracion_helms')
        self.version_helms = data.get('version_helms', '2.0')

        # ── Año de planificación (para core.py) ───────────────────────────────
        self.año_planificacion = data.get('año_planificacion')

    # ─── Cálculos de nivel ────────────────────────────────────────────────────

    def calcular_nivel_experiencia(self) -> str:
        """Calcula el nivel de experiencia basado en años de entrenamiento."""
        if self.experiencia_años < 1:
            return 'principiante'
        elif self.experiencia_años < 3:
            return 'intermedio'
        return 'avanzado'

    def calcular_factor_recuperacion(self) -> float:
        """
        Calcula factor de recuperación global (0.7 – 1.3).

        Pesos por variable:
          - Sueño:     0.35  (mayor impacto en síntesis proteica y GH)
          - Estrés:    0.25  (cortisol compite directamente con adaptación)
          - Energía:   0.25  (proxy de readiness subjetivo)
          - Nutrición: 0.15  (importante pero más controlable que el resto)
        """
        estres_norm = (10 - self.nivel_estres) / 10  # invertir: menos estrés = mejor
        sueño_norm = self.calidad_sueño / 10
        energia_norm = self.nivel_energia / 10
        nutricion_norm = self.nutricion_calidad / 10

        factor_base = (
                estres_norm * 0.25 +
                sueño_norm * 0.35 +
                energia_norm * 0.25 +
                nutricion_norm * 0.15
        )
        return round(0.7 + (factor_base * 0.6), 3)

    def necesita_descarga(self) -> bool:
        """Determina si necesita semana de descarga basándose en recuperación."""
        return self.calcular_factor_recuperacion() < 0.85

    # ─── Volumen ──────────────────────────────────────────────────────────────

    def obtener_volumen_objetivo(self, grupo_muscular: str) -> int:
        """
        Obtiene volumen objetivo semanal (en series) para un grupo muscular.

        CORRECCIÓN: La versión anterior tenía los volúmenes duplicados aquí con
        valores idénticos a VOLUMENES_BASE en config.py. Cualquier cambio en
        config.py no se reflejaba en este método. Ahora importa directamente
        de config, eliminando la duplicación.

        El ajuste por objetivo sigue siendo local porque depende de la lógica
        de negocio del perfil, no de configuración global.
        """
        nivel = self.calcular_nivel_experiencia()
        factor_recuperacion = self.calcular_factor_recuperacion()

        # Fuente única: config.py
        volumen_base = VOLUMENES_BASE.get(nivel, VOLUMENES_BASE['principiante']).get(
            grupo_muscular, 8  # fallback conservador si el grupo no existe en config
        )

        volumen_ajustado = int(volumen_base * factor_recuperacion)

        # Ajuste por objetivo principal
        multiplicador_objetivo = {
            'hipertrofia': 1.1,
            'fuerza': 0.9,
            'fuerza_hipertrofia': 1.0,
            'potencia': 0.8,
            'resistencia': 1.2,
        }.get(self.objetivo_principal, 1.0)

        volumen_ajustado = int(volumen_ajustado * multiplicador_objetivo)
        return max(volumen_ajustado, 4)  # mínimo 4 series/semana

    # ─── Intensidad ───────────────────────────────────────────────────────────

    def obtener_intensidad_objetivo(self) -> tuple:
        """
        Obtiene rango de RPE objetivo según nivel.

        CORRECCIÓN: Avanzados tenían el mismo rango que intermedios (7-9).
        La diferencia real en avanzados no es el rango sino la *precisión*
        del RPE: un avanzado distingue entre RPE 8 y 8.5; un principiante no.
        El rango se eleva ligeramente (8-9) para reflejar que los avanzados
        trabajan habitualmente más cerca del fallo con mejor tolerancia.
        """
        nivel = self.calcular_nivel_experiencia()
        return {
            'principiante': (6, 8),
            'intermedio': (7, 9),
            'avanzado': (8, 9),  # mayor intensidad, mejor precisión de RPE
        }.get(nivel, (7, 9))

    # ─── Frecuencia ───────────────────────────────────────────────────────────

    def obtener_frecuencia_objetivo(self, grupo_muscular: str) -> int:
        """Obtiene frecuencia de entrenamiento objetivo para un grupo."""
        frecuencia_base = 1 if self.dias_disponibles <= 3 else 2
        grupos_grandes = {'pecho', 'espalda', 'cuadriceps', 'isquios', 'gluteos'}
        if grupo_muscular not in grupos_grandes:
            return min(frecuencia_base + 1, 3)
        return frecuencia_base

    # ─── Compatibilidad de ejercicios ────────────────────────────────────────

    def es_compatible_ejercicio(self, ejercicio: str) -> bool:
        """Verifica si un ejercicio es compatible con el perfil del cliente."""
        if ejercicio in self.ejercicios_evitar:
            return False

        ejercicios_problematicos = {
            'lesion_hombro': ['press_militar', 'elevaciones_laterales', 'dominadas'],
            'lesion_rodilla': ['sentadilla', 'zancadas', 'extension_cuadriceps'],
            'lesion_espalda_baja': ['peso_muerto', 'sentadilla', 'remo_con_barra'],
        }
        for limitacion in self.limitaciones_fisicas:
            if limitacion in ejercicios_problematicos:
                if ejercicio in ejercicios_problematicos[limitacion]:
                    return False
        return True

    # ─── Tempo y descanso ─────────────────────────────────────────────────────

    def obtener_tempo_preferido(self, tipo_ejercicio: str = 'general') -> str:
        """
        Obtiene tempo preferido según objetivo.

        CORRECCIÓN: Usa TEMPOS de config en lugar de strings hardcodeados,
        garantizando que si se cambia el tempo en config.py este método
        también lo refleja. Fallback a '2-0-X-0' si el objetivo no existe.
        """
        objetivo_normalizado = self.objetivo_principal.replace(' ', '_')
        return TEMPOS.get(objetivo_normalizado, TEMPOS.get('hipertrofia', '2-0-X-0'))

    def obtener_descanso_preferido(self, tipo_ejercicio: str, rpe_objetivo: int) -> int:
        """Obtiene tiempo de descanso preferido en minutos."""
        ejercicios_principales = ['sentadilla', 'peso_muerto', 'press_banca', 'press_militar']
        descanso_base = 4 if any(p in tipo_ejercicio for p in ejercicios_principales) else 2

        if rpe_objetivo >= 9:
            descanso_base += 1
        elif rpe_objetivo <= 6:
            descanso_base -= 1

        if self.calcular_nivel_experiencia() == 'principiante':
            descanso_base += 1

        return max(descanso_base, 1)

    # ─── Resumen ──────────────────────────────────────────────────────────────

    def generar_resumen_perfil(self) -> Dict[str, Any]:
        """Genera resumen completo del perfil para logging/debugging."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'nivel_experiencia': self.calcular_nivel_experiencia(),
            'objetivo_principal': self.objetivo_principal,
            'dias_disponibles': self.dias_disponibles,
            'factor_recuperacion': self.calcular_factor_recuperacion(),
            'necesita_descarga': self.necesita_descarga(),
            'version_helms': self.version_helms,
        }
