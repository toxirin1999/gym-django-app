# analytics/sistema_educacion_helms.py

from typing import Dict, List
from dataclasses import dataclass
from enum import Enum


class NivelEducativo(Enum):
    PRINCIPIANTE = "principiante"
    INTERMEDIO = "intermedio"
    AVANZADO = "avanzado"


@dataclass
class ContenidoEducativo:
    titulo: str
    explicacion_simple: str
    explicacion_detallada: str
    ejemplos: List[str]


class SistemaEducacionHelms:
    def __init__(self, nivel_usuario: NivelEducativo = NivelEducativo.PRINCIPIANTE):
        self.nivel_usuario = nivel_usuario
        self.contenidos = self._cargar_contenidos_educativos()

    def _cargar_contenidos_por_nivel(self) -> Dict[str, ContenidoEducativo]:
        # Contenido base que puede ser común o tener pequeñas variaciones
        base_content = {
            'seleccion_ejercicios': ContenidoEducativo(
                titulo="La Selección de Ejercicios",
                explicacion_simple="Los ejercicios de tu plan se eligen para crear un estímulo completo y equilibrado, combinando movimientos compuestos y de aislamiento.",
                explicacion_detallada="Un buen programa se basa en ejercicios 'compuestos' que trabajan múltiples músculos a la vez (como sentadillas o press de banca) y los complementa con ejercicios de 'aislamiento' para enfocarse en músculos específicos (como curl de bíceps).",
                ejemplos=[
                    "Compuestos: Construyen la base de tu fuerza y tamaño.",
                    "Aislamiento: Perfeccionan y dan forma a músculos específicos, corrigiendo puntos débiles."
                ]
            ),
            'tempo': ContenidoEducativo(
                titulo="El Tempo: El Arma Secreta",
                explicacion_simple="El tempo (ej. 2-0-X-0) controla la velocidad de cada repetición para maximizar la tensión en el músculo.",
                explicacion_detallada="El tempo se desglosa en 4 fases: excéntrica (bajada), pausa abajo, concéntrica (subida) y pausa arriba. Controlar la fase de bajada (excéntrica) es clave para el crecimiento muscular.",
                ejemplos=[
                    "Un tempo '2-0-X-0' significa: 2 segundos para bajar el peso, 0 segundos de pausa abajo, subida explosiva ('X') y 0 segundos de pausa arriba.",
                    "Controlar el tempo aumenta el 'tiempo bajo tensión', un factor clave para la hipertrofia."
                ]
            )
        }

        # Contenido específico que varía drásticamente según el nivel
        if self.nivel_usuario == NivelEducativo.PRINCIPIANTE:
            base_content['rpe'] = ContenidoEducativo(
                titulo="Iniciación al Esfuerzo (RPE)",
                explicacion_simple="El RPE es tu 'medidor de esfuerzo' del 1 al 10. Nos ayuda a asegurarnos de que entrenes con la intensidad correcta, ni demasiado suave ni demasiado fuerte.",
                explicacion_detallada="Al principio, el objetivo es aprender a escuchar a tu cuerpo. Un RPE bajo (6-7) es ideal porque te permite centrarte en aprender la técnica perfecta de cada ejercicio sin arriesgarte a una lesión. Es la base para construir una fuerza sólida y duradera.",
                ejemplos=[
                    "RPE 6: 'Podría haber hecho 4 o más repeticiones. El peso se sintió ligero.'",
                    "RPE 7: 'Podría haber hecho 3 repeticiones más. Fue desafiante pero controlado.'",
                    "Tu misión ahora es dominar la técnica, no levantar el máximo peso posible."
                ]
            )
            base_content['volumen'] = ContenidoEducativo(
                titulo="Volumen de Adaptación",
                explicacion_simple="Tu volumen de entrenamiento (series totales) está diseñado para que tu cuerpo se adapte y se haga más fuerte sin agotarse.",
                explicacion_detallada="Como principiante, tus músculos son muy sensibles al estímulo. No necesitas una cantidad enorme de series para crecer. Un volumen moderado es la forma más eficiente de progresar y asegurar una buena recuperación.",
                ejemplos=[
                    "El objetivo es la consistencia, no la extenuación.",
                    "Este volumen te permitirá entrenar con la frecuencia necesaria para aprender los movimientos."
                ]
            )

        elif self.nivel_usuario == NivelEducativo.INTERMEDIO:
            base_content['rpe'] = ContenidoEducativo(
                titulo="Optimizando la Intensidad con RPE",
                explicacion_simple="Ahora que dominas la técnica, el RPE se convierte en tu herramienta para autorregular. Un RPE 8 (dejar 2 repeticiones en recámara) es tu 'zona de dinero' para el crecimiento.",
                explicacion_detallada="Como intermedio, tu capacidad de trabajo es mayor. El RPE te permite entrenar cerca del fallo para maximizar el estímulo, pero sin llegar a él, lo que optimiza la recuperación entre sesiones. Es el equilibrio perfecto entre intensidad y sostenibilidad.",
                ejemplos=[
                    "RPE 8: 'Podría haber hecho 2 repeticiones más, pero con dificultad. La última repetición fue lenta.'",
                    "RPE 9: 'Solo podría haber hecho una repetición más. Estaba al límite.'",
                    "Usa el RPE para decidir si hoy, que te sientes fuerte, puedes añadir una repetición extra o un poco de peso."
                ]
            )
            base_content['volumen'] = ContenidoEducativo(
                titulo="Volumen de Sobrecarga Progresiva",
                explicacion_simple="Tu volumen está calculado para aplicar una sobrecarga progresiva, es decir, hacer un poco más de trabajo a lo largo del tiempo.",
                explicacion_detallada="En esta fase, tu cuerpo ya se ha adaptado al entrenamiento básico. Para seguir creciendo, necesitamos aumentar sistemáticamente el trabajo total (volumen). Este plan lo hace de forma estructurada a lo largo de las semanas.",
                ejemplos=[
                    "El volumen aumentará gradualmente en cada mesociclo.",
                    "Este es el volumen máximo recuperable (MRV) estimado para tu nivel actual."
                ]
            )

        elif self.nivel_usuario == NivelEducativo.AVANZADO:
            base_content['rpe'] = ContenidoEducativo(
                titulo="Maestría del RPE y Gestión de la Fatiga",
                explicacion_simple="Como atleta avanzado, el RPE es tu herramienta de precisión para modular la fatiga del Sistema Nervioso Central (SNC) y decidir cuándo atacar y cuándo retroceder.",
                explicacion_detallada="Tu progreso ya no es lineal. El RPE te permite navegar las fluctuaciones diarias de rendimiento. Un RPE 9 en una fase de fuerza no es el mismo que un RPE 9 en una de hipertrofia. Se trata de gestionar la fatiga acumulada para maximizar la supercompensación a largo plazo.",
                ejemplos=[
                    "En fases de fuerza, un RPE 9 es casi tu máximo absoluto para esas repeticiones (1RM del día).",
                    "En hipertrofia, un RPE 8 te permite acumular un gran volumen sin 'freír' tu SNC.",
                    "Usa el RPE para decidir si hoy es un día para un PR (Récord Personal) o para un trabajo técnico más ligero."
                ]
            )
            base_content['volumen'] = ContenidoEducativo(
                titulo="Volumen Periodizado y MRV",
                explicacion_simple="Tu volumen está periodizado en bloques (mesociclos) para gestionar la fatiga y maximizar la adaptación a largo plazo, fluctuando alrededor de tu Máximo Volumen Recuperable (MRV).",
                explicacion_detallada="Como avanzado, no puedes simplemente añadir más y más volumen. Tu plan alterna fases de acumulación (alto volumen) con fases de intensificación (menor volumen, más peso) y descargas para permitir que tu cuerpo se recupere y supere sus límites anteriores.",
                ejemplos=[
                    "Estás siguiendo una periodización ondulante, donde el volumen y la intensidad cambian semanalmente.",
                    "Las semanas de descarga son cruciales para disipar la fatiga y permitir un nuevo pico de rendimiento."
                ]
            )

        return base_content

    def _cargar_contenidos_educativos(self) -> Dict[str, ContenidoEducativo]:
        # Esta función no cambia, pero la mantenemos
        return {
            'rpe_explicacion': ContenidoEducativo(
                titulo="¿Qué es RPE y cómo usarlo?",
                explicacion_simple="RPE (Ratio de Esfuerzo Percibido) es una escala del 1-10 que mide qué tan difícil se siente un ejercicio.",
                explicacion_detallada="RPE es una herramienta de autorregulación que te permite ajustar la intensidad basándose en cómo te sientes cada día. Un RPE de 7 significa que podrías hacer 3 repeticiones más, RPE 8 significa 2 más, y RPE 9 significa 1 más.",
                ejemplos=[
                    "RPE 7: Terminas la serie sintiendo que podrías hacer 3 repeticiones más.",
                    "RPE 8: Terminas sintiendo que podrías hacer 2 repeticiones más.",
                ]
            ),
            'volumen_explicacion': ContenidoEducativo(
                titulo="¿Por qué este volumen de entrenamiento?",
                explicacion_simple="El volumen (número total de series) está calculado según tu nivel de experiencia y objetivos para maximizar resultados sin sobreentrenamiento.",
                explicacion_detallada="El volumen óptimo varía según el nivel de experiencia. Principiantes necesitan menos volumen para progresar, mientras que avanzados requieren más.",
                ejemplos=["Principiante: 10-14 series por grupo muscular por semana.",
                          "Avanzado: 18-22 series por grupo muscular por semana."]
            ),
        }

    def explicar_decision_ejercicio(self, ejercicio: str) -> str:
        # Esta función tampoco cambia
        explicaciones_base = {
            # --- Ejercicios Fundamentales (ya existentes) ---
            'press_banca': "El press de banca es un ejercicio fundamental para desarrollar el pecho, hombros y tríceps, clave para la fuerza del tren superior.",
            'sentadilla': "La sentadilla es el rey de los ejercicios para piernas, trabajando cuádriceps, glúteos e isquiotibiales de forma integrada.",
            'peso_muerto': "El peso muerto trabaja toda la cadena posterior (espalda, glúteos, isquios) y es excelente para desarrollar fuerza general.",
            'press_militar': "El press militar es el constructor principal de fuerza y masa para los hombros, con gran transferencia a otros levantamientos.",
            'press_inclinado': "El press inclinado enfoca el trabajo en la parte superior del pectoral (haz clavicular), ayudando a crear un pecho más completo y estético.",
            'press_frances': "El press francés es uno de los mejores ejercicios para aislar y desarrollar la cabeza larga del tríceps, clave para el tamaño del brazo.",
            'fondos_triceps': "Los fondos para tríceps son un excelente ejercicio de peso corporal para construir masa y fuerza en los tríceps y el pecho.",

            # --- INICIO DE LAS NUEVAS EXPLICACIONES ---

            # Espalda y Tracción
            'remo_con_barra': "El remo con barra es un constructor de masa fundamental para la espalda media y alta, mejorando la postura y la fuerza de tracción.",
            'dominadas': "Las dominadas son el ejercicio de peso corporal por excelencia para desarrollar la amplitud de la espalda (dorsales) y la fuerza de agarre.",

            # Cadena Posterior e Isquios
            'peso_muerto_rumano': "El peso muerto rumano (RDL) es clave para aislar los isquiotibiales y glúteos, mejorando la flexibilidad y la fuerza de la cadera.",
            'curl_femoral': "El curl femoral aísla directamente los isquiotibiales, un complemento crucial a los ejercicios compuestos para prevenir desequilibrios y lesiones.",
            'hip_thrust': "El hip thrust es el ejercicio más efectivo para aislar y fortalecer los glúteos, lo que mejora la potencia en sentadillas y peso muerto.",

            # Bíceps
            'curl_con_barra': "El curl con barra es el ejercicio base para construir masa en los bíceps, permitiendo mover la mayor cantidad de peso.",
            'curl_con_mancuerna': "El curl con mancuerna permite un movimiento más natural de la muñeca (supinación), logrando una contracción máxima del bíceps.",

            # Piernas (Cuádriceps y Gemelos)
            'prensa': "La prensa de piernas permite aplicar una gran sobrecarga a los cuádriceps con un menor estrés en la espalda baja en comparación con la sentadilla.",
            'sentadilla_bulgara': "La sentadilla búlgara es un ejercicio unilateral excelente para corregir desequilibrios de fuerza y mejorar la estabilidad y el tamaño de glúteos y cuádriceps.",
            'elevaciones_gemelos_parado': "Este ejercicio enfoca el trabajo en el gastrocnemio, la parte más visible del gemelo, para construir tamaño y potencia.",
            'elevaciones_gemelos_sentado': "Al realizarse sentado, este ejercicio aísla el músculo sóleo, que se encuentra debajo del gastrocnemio, para un desarrollo completo de la pantorrilla.",

            # Hombros (Aislamiento)
            'elevaciones_laterales': "Las elevaciones laterales son esenciales para desarrollar la cabeza media del deltoides, lo que crea la apariencia de hombros más anchos y redondos."
        }
        return explicaciones_base.get(ejercicio.lower(),
                                      f"El {ejercicio.title()} es un ejercicio efectivo para tu programa.")

    # ✅ NUEVA FUNCIÓN MEJORADA
    def explicar_parametros_sesion(self, series: int, reps: str, rpe: int) -> Dict[str, str]:
        """
        Genera explicaciones detalladas para los parámetros de una serie.
        """
        explicaciones = {}

        # Explicar Series
        if series <= 3:
            explicaciones[
                'series'] = f"Se programaron {series} series para mantener una alta calidad de movimiento y evitar una fatiga excesiva, ideal para ejercicios de fuerza."
        elif series <= 5:
            explicaciones[
                'series'] = f"Un total de {series} series proporciona un volumen moderado, perfecto para una progresión de hipertrofia sostenible."
        else:
            explicaciones[
                'series'] = f"Este es un volumen alto ({series} series) diseñado para maximizar el estímulo de crecimiento muscular en esta fase."

        # Explicar Repeticiones
        try:
            if '-' in reps:
                rep_min, rep_max = map(int, reps.split('-'))
                if rep_max <= 6:
                    explicaciones[
                        'repeticiones'] = f"El rango de {reps} repeticiones está enfocado en el desarrollo de fuerza máxima."
                elif rep_max <= 12:
                    explicaciones[
                        'repeticiones'] = f"El rango de {reps} repeticiones es el punto óptimo para estimular la hipertrofia (crecimiento muscular)."
                else:
                    explicaciones[
                        'repeticiones'] = f"Un rango de {reps} repeticiones está diseñado para mejorar la resistencia muscular."
            else:
                explicaciones['repeticiones'] = f"Se han programado {reps} repeticiones para este ejercicio."
        except (ValueError, TypeError):
            explicaciones['repeticiones'] = f"Se han programado {reps} repeticiones para este ejercicio."

        # Explicar RPE
        if rpe <= 7:
            explicaciones[
                'rpe'] = f"Un RPE de {rpe} te permite entrenar con una intensidad controlada, dejando varias repeticiones 'en recámara'. Es ideal para acumular volumen de calidad y perfeccionar la técnica."
        elif rpe <= 8:
            explicaciones[
                'rpe'] = f"Entrenar a RPE {rpe} es el punto ideal para la mayoría de series. Es una intensidad alta que estimula grandes adaptaciones sin comprometer en exceso tu capacidad de recuperación."
        else:
            explicaciones[
                'rpe'] = f"Un RPE de {rpe} o más es una intensidad muy alta, reservada para series clave o fases de pico. El objetivo es llevar tu cuerpo al límite para forzar la máxima adaptación."

        return explicaciones


# --- Función Helper para integrar en las vistas ---
def agregar_educacion_a_plan(plan: Dict) -> Dict:
    """
    Enriquece un plan de entrenamiento con explicaciones contextuales.
    """
    sistema_educacion = SistemaEducacionHelms()

    # Agregar explicaciones generales al plan (como antes)
    plan['educacion'] = {
        'rpe': sistema_educacion.contenidos['rpe_explicacion'],
        'volumen': sistema_educacion.contenidos['volumen_explicacion']
    }

    # ✅ LÓGICA MEJORADA: Agregar explicaciones específicas a cada ejercicio
    if 'entrenos_por_fecha' in plan:
        for fecha, entreno in plan['entrenos_por_fecha'].items():
            if 'ejercicios' in entreno:
                for ejercicio in entreno['ejercicios']:
                    # Explicación del ejercicio
                    ejercicio['explicacion_ejercicio'] = sistema_educacion.explicar_decision_ejercicio(
                        ejercicio.get('nombre', 'Ejercicio')
                    )
                    # Explicación de los parámetros
                    ejercicio['explicacion_parametros'] = sistema_educacion.explicar_parametros_sesion(
                        ejercicio.get('series', 3),
                        ejercicio.get('repeticiones', '8-12'),
                        ejercicio.get('rpe_objetivo', 8)
                    )
    return plan
