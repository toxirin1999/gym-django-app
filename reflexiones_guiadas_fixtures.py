# ============================================
# SCRIPT PARA CREAR LAS PRIMERAS 10 REFLEXIONES GUIADAS
# Ejecutar este código en el shell de Django o crear un comando de management
# ============================================

"""
Para ejecutar este script:

1. Desde el shell de Django:
   python manage.py shell
   exec(open('reflexiones_guiadas_fixtures.py').read())

2. O crear un comando de management:
   python manage.py cargar_reflexiones_guiadas
"""

from diario.models import ReflexionGuiadaTema
from datetime import date


def crear_reflexiones_guiadas():
    """Crea las primeras 10 reflexiones guiadas temáticas"""

    reflexiones = [
        # 1. DÍA MUNDIAL CONTRA EL CÁNCER
        {
            'titulo': 'Día Mundial contra el Cáncer',
            'slug': 'dia-mundial-cancer',
            'fecha_activacion': date(2025, 2, 4),
            'es_recurrente': True,
            'contexto': '''El cáncer es una de las principales causas de mortalidad en el mundo, pero también es un recordatorio de la fragilidad y la fortaleza del espíritu humano. Millones de personas enfrentan esta enfermedad cada año con valentía extraordinaria, demostrando que el coraje no es la ausencia de miedo, sino la capacidad de actuar a pesar de él.

Los estoicos enseñaban que no podemos controlar lo que nos sucede, pero sí cómo respondemos. Muchos pacientes de cáncer encuentran significado y propósito incluso en medio del sufrimiento, transformando su experiencia en una oportunidad de crecimiento personal y conexión profunda con lo que realmente importa.

Hoy es un día para reflexionar sobre nuestra propia mortalidad, apreciar la salud cuando la tenemos, y honrar a quienes luchan contra esta enfermedad con dignidad y esperanza.''',
            'cita_filosofica': 'No podemos elegir nuestras circunstancias externas, pero siempre podemos elegir cómo responder a ellas.',
            'autor_cita': 'Epicteto',
            'pregunta_1': '¿Qué aspectos de tu salud das por sentado que podrías perder mañana?',
            'pregunta_2': '¿Cómo responderías si te enfrentaras a un diagnóstico grave? ¿Qué valores te guiarían?',
            'pregunta_3': '¿Conoces a alguien que haya enfrentado el cáncer con valentía? ¿Qué aprendiste de su ejemplo?',
            'pregunta_4': '¿Qué pequeña acción puedes hacer hoy para cuidar mejor de tu salud física y mental?',
            'pregunta_5': '',
            'accion_sugerida': 'Hoy, dedica 10 minutos a investigar sobre prevención del cáncer o dona a una organización que apoye la investigación oncológica. También puedes enviar un mensaje de apoyo a alguien que esté luchando contra esta enfermedad.',
            'categoria': 'salud',
            'icono': 'fa-ribbon',
            'color': '#E91E63',
        },

        # 2. DÍA INTERNACIONAL DE LA MUJER
        {
            'titulo': 'Día Internacional de la Mujer',
            'slug': 'dia-internacional-mujer',
            'fecha_activacion': date(2025, 3, 8),
            'es_recurrente': True,
            'contexto': '''El Día Internacional de la Mujer conmemora la lucha por la igualdad, el reconocimiento y el ejercicio efectivo de los derechos de las mujeres. A lo largo de la historia, las mujeres han enfrentado discriminación sistemática, pero también han demostrado una resiliencia y fortaleza extraordinarias.

Desde las sufragistas que lucharon por el derecho al voto, hasta las científicas, filósofas, artistas y líderes que han transformado el mundo, las mujeres han contribuido de manera invaluable al progreso humano, a menudo sin el reconocimiento que merecían.

Hoy es un día para reflexionar sobre la justicia, la equidad y el respeto. Los estoicos valoraban la virtud de la justicia (dikaiosyne) como fundamental para una sociedad floreciente. La igualdad de género no es solo un derecho humano, es una condición necesaria para el florecimiento colectivo.''',
            'cita_filosofica': 'La justicia consiste en dar a cada uno lo que le corresponde según su dignidad como ser humano.',
            'autor_cita': 'Marco Aurelio',
            'pregunta_1': '¿Qué mujeres en tu vida han sido modelos de fortaleza, sabiduría o coraje?',
            'pregunta_2': '¿De qué formas, conscientes o inconscientes, podrías estar perpetuando desigualdades de género?',
            'pregunta_3': '¿Qué puedes hacer en tu esfera de influencia para promover la igualdad y el respeto?',
            'pregunta_4': '¿Cómo te gustaría que tus hijas, hermanas o futuras generaciones de mujeres vivan en el mundo?',
            'pregunta_5': '',
            'accion_sugerida': 'Hoy, lee sobre una mujer histórica que admires y que quizás no reciba suficiente reconocimiento. Comparte su historia con alguien. También puedes reflexionar sobre cómo puedes ser un mejor aliado en la lucha por la igualdad.',
            'categoria': 'social',
            'icono': 'fa-venus',
            'color': '#9C27B0',
        },

        # 3. DÍA MUNDIAL DE LA SALUD
        {
            'titulo': 'Día Mundial de la Salud',
            'slug': 'dia-mundial-salud',
            'fecha_activacion': date(2025, 4, 7),
            'es_recurrente': True,
            'contexto': '''La salud es uno de nuestros bienes más preciados, y sin embargo, a menudo la damos por sentada hasta que la perdemos. El Día Mundial de la Salud nos invita a reflexionar sobre el bienestar físico, mental y social, y sobre las desigualdades en el acceso a la atención médica que existen en el mundo.

Los estoicos entendían que el cuerpo es el vehículo del alma. Séneca escribió: "No es que tengamos poco tiempo, sino que perdemos mucho". La salud nos da tiempo de calidad para vivir de acuerdo con nuestros valores y propósitos.

La salud no es solo la ausencia de enfermedad, sino un estado de completo bienestar. Esto incluye cuidar nuestra mente tanto como nuestro cuerpo, cultivar relaciones significativas, y vivir con propósito.''',
            'cita_filosofica': 'Debes tener un cuerpo sano para tener una mente sana.',
            'autor_cita': 'Juvenal (Mens sana in corpore sano)',
            'pregunta_1': '¿Qué hábitos de salud has estado posponiendo que sabes que deberías adoptar?',
            'pregunta_2': '¿Cómo está tu salud mental en este momento? ¿Qué necesitas para cuidarla mejor?',
            'pregunta_3': '¿Qué relación tienes con tu cuerpo? ¿Lo tratas con respeto y gratitud?',
            'pregunta_4': '¿Qué pequeño cambio podrías hacer hoy que mejore tu bienestar a largo plazo?',
            'pregunta_5': '',
            'accion_sugerida': 'Hoy, programa una cita médica que has estado posponiendo (chequeo general, dentista, etc.). También puedes dedicar 15 minutos a una actividad que nutra tu salud mental: meditación, caminata en la naturaleza, o una conversación profunda con alguien que te importa.',
            'categoria': 'salud',
            'icono': 'fa-heartbeat',
            'color': '#4CAF50',
        },

        # 4. DÍA DE LA TIERRA
        {
            'titulo': 'Día de la Tierra',
            'slug': 'dia-de-la-tierra',
            'fecha_activacion': date(2025, 4, 22),
            'es_recurrente': True,
            'contexto': '''El Día de la Tierra nos recuerda que somos parte de un ecosistema interconectado, no sus dueños. Nuestro planeta enfrenta desafíos sin precedentes: cambio climático, pérdida de biodiversidad, contaminación. Pero también es un día de esperanza y acción.

Los estoicos enseñaban que vivimos en un cosmos ordenado (kosmos) del cual somos parte integral. Marco Aurelio escribió: "Todo está entrelazado, y el lazo es sagrado". Nuestra conexión con la naturaleza no es opcional; es fundamental para nuestra supervivencia y bienestar.

Cuidar de la Tierra no es solo un acto de responsabilidad ambiental, es un acto de justicia hacia las futuras generaciones y hacia todas las formas de vida con las que compartimos este planeta.''',
            'cita_filosofica': 'La naturaleza no hace nada en vano. Somos parte de ella, no sus conquistadores.',
            'autor_cita': 'Aristóteles',
            'pregunta_1': '¿Cuándo fue la última vez que pasaste tiempo en la naturaleza sin distracciones tecnológicas?',
            'pregunta_2': '¿Qué hábitos de consumo tuyos tienen un impacto negativo en el medio ambiente?',
            'pregunta_3': '¿Qué legado ambiental quieres dejar para las futuras generaciones?',
            'pregunta_4': '¿Cómo puedes vivir de forma más alineada con el ritmo natural de la Tierra?',
            'pregunta_5': '',
            'accion_sugerida': 'Hoy, pasa al menos 20 minutos en contacto con la naturaleza (un parque, un jardín, incluso observar el cielo). También puedes comprometerte a un cambio sostenible: reducir plásticos de un solo uso, compostar, usar transporte público, o plantar un árbol.',
            'categoria': 'naturaleza',
            'icono': 'fa-globe-americas',
            'color': '#2E7D32',
        },

        # 5. DÍA MUNDIAL DE LA SALUD MENTAL
        {
            'titulo': 'Día Mundial de la Salud Mental',
            'slug': 'dia-mundial-salud-mental',
            'fecha_activacion': date(2025, 10, 10),
            'es_recurrente': True,
            'contexto': '''La salud mental es tan importante como la salud física, pero durante mucho tiempo ha sido estigmatizada y descuidada. Millones de personas en el mundo luchan con ansiedad, depresión, trauma y otros desafíos mentales, a menudo en silencio.

Los estoicos practicaban lo que hoy llamaríamos "higiene mental". Marco Aurelio escribía cada noche en su diario, examinando sus pensamientos y emociones. Epicteto enseñaba a distinguir entre lo que está en nuestro control (nuestros juicios, reacciones) y lo que no lo está (eventos externos).

Cuidar de nuestra salud mental no es debilidad, es sabiduría. Pedir ayuda cuando la necesitamos no es fracaso, es coraje. Y crear espacios seguros donde otros puedan compartir sus luchas es un acto de compasión.''',
            'cita_filosofica': 'No son las cosas las que nos perturban, sino nuestros juicios sobre las cosas.',
            'autor_cita': 'Epicteto',
            'pregunta_1': '¿Cómo está tu salud mental en este momento? Sé honesto contigo mismo.',
            'pregunta_2': '¿Qué pensamientos recurrentes te causan más sufrimiento? ¿Son realmente ciertos?',
            'pregunta_3': '¿Tienes a alguien con quien puedas hablar abiertamente sobre tus luchas internas?',
            'pregunta_4': '¿Qué prácticas te ayudan a mantener el equilibrio mental? ¿Las estás haciendo regularmente?',
            'pregunta_5': '¿Cómo puedes ser más compasivo contigo mismo cuando enfrentas dificultades emocionales?',
            'accion_sugerida': 'Hoy, dedica 10 minutos a una práctica de mindfulness o meditación. Si has estado luchando con tu salud mental, considera buscar ayuda profesional. También puedes enviar un mensaje a alguien preguntándole cómo está realmente, creando un espacio seguro para la vulnerabilidad.',
            'categoria': 'salud',
            'icono': 'fa-brain',
            'color': '#00BCD4',
        },

        # 6. SOLSTICIO DE INVIERNO (HEMISFERIO NORTE)
        {
            'titulo': 'Solsticio de Invierno: La Noche Más Larga',
            'slug': 'solsticio-invierno',
            'fecha_activacion': date(2025, 12, 21),
            'es_recurrente': True,
            'contexto': '''El solsticio de invierno marca la noche más larga del año, pero también el punto de inflexión: a partir de ahora, los días comenzarán a alargarse nuevamente. Desde tiempos antiguos, este momento ha sido celebrado como un símbolo de renacimiento y esperanza.

Los estoicos valoraban la observación de los ciclos naturales como una forma de conectar con el orden del cosmos. Así como la naturaleza atraviesa períodos de oscuridad antes de la luz, nosotros también experimentamos inviernos personales: momentos de dificultad, pérdida o confusión.

Pero así como el solsticio nos recuerda que la luz siempre regresa, nuestras propias "noches oscuras del alma" también son temporales. La clave está en confiar en el proceso, mantener la esperanza, y recordar que después del invierno siempre viene la primavera.''',
            'cita_filosofica': 'El impedimento para la acción hace avanzar la acción. Lo que se interpone en el camino se convierte en el camino.',
            'autor_cita': 'Marco Aurelio',
            'pregunta_1': '¿Qué "invierno personal" estás atravesando en este momento de tu vida?',
            'pregunta_2': '¿Qué lecciones has aprendido de períodos oscuros anteriores que superaste?',
            'pregunta_3': '¿Cómo puedes encontrar significado o crecimiento incluso en medio de la dificultad?',
            'pregunta_4': '¿Qué "luz" (esperanza, propósito, conexión) puedes cultivar mientras esperas que pase el invierno?',
            'pregunta_5': '',
            'accion_sugerida': 'Hoy, enciende una vela como símbolo de la luz que siempre regresa. Escribe sobre un desafío que estés enfrentando y cómo puedes transformarlo en una oportunidad de crecimiento. También puedes pasar tiempo en silencio, honrando los ciclos naturales de la vida.',
            'categoria': 'naturaleza',
            'icono': 'fa-snowflake',
            'color': '#607D8B',
        },

        # 7. NACIMIENTO DE MARCO AURELIO
        {
            'titulo': 'Nacimiento de Marco Aurelio: El Emperador Filósofo',
            'slug': 'nacimiento-marco-aurelio',
            'fecha_activacion': date(2025, 4, 26),
            'es_recurrente': True,
            'contexto': '''Marco Aurelio (121-180 d.C.) fue emperador de Roma y uno de los más grandes filósofos estoicos. A pesar de tener el poder absoluto, eligió vivir con humildad, disciplina y servicio. Sus "Meditaciones" son un testimonio de su lucha diaria por ser una mejor persona.

Lo extraordinario de Marco Aurelio es que escribía para sí mismo, no para la posteridad. Sus reflexiones eran un ejercicio de autoexamen: recordarse a sí mismo sus principios cuando el poder podría haberlo corrompido, mantener la perspectiva cuando las responsabilidades lo abrumaban, y cultivar la compasión cuando otros lo decepcionaban.

Su vida nos enseña que la grandeza no está en el poder que tenemos, sino en cómo lo usamos. Que el liderazgo verdadero es servicio. Y que la filosofía no es teoría abstracta, sino práctica diaria.''',
            'cita_filosofica': 'La felicidad de tu vida depende de la calidad de tus pensamientos.',
            'autor_cita': 'Marco Aurelio',
            'pregunta_1': '¿Qué poder o influencia tienes en tu vida (por pequeña que sea) y cómo la estás usando?',
            'pregunta_2': '¿Qué principios te guían cuando enfrentas decisiones difíciles?',
            'pregunta_3': '¿Cómo puedes servir mejor a quienes dependen de ti (familia, equipo, comunidad)?',
            'pregunta_4': '¿Qué pensamientos recurrentes están afectando la calidad de tu vida?',
            'pregunta_5': '',
            'accion_sugerida': 'Hoy, lee un pasaje de las "Meditaciones" de Marco Aurelio y reflexiona sobre cómo aplicarlo a tu vida actual. También puedes identificar un área donde tienes influencia y preguntarte: "¿Estoy usando este poder para servir o para mi ego?"',
            'categoria': 'filosofia',
            'icono': 'fa-crown',
            'color': '#795548',
        },

        # 8. DÍA MUNDIAL DE LA PREVENCIÓN DEL SUICIDIO
        {
            'titulo': 'Día Mundial de la Prevención del Suicidio',
            'slug': 'dia-prevencion-suicidio',
            'fecha_activacion': date(2025, 9, 10),
            'es_recurrente': True,
            'contexto': '''El suicidio es una tragedia que afecta a familias y comunidades en todo el mundo. Cada año, cientos de miles de personas toman la decisión de terminar con su vida, a menudo porque sienten que no hay otra salida al dolor que están experimentando.

Pero el suicidio es prevenible. Una conversación, una mano extendida, un momento de conexión genuina puede salvar una vida. El estoicismo nos enseña que incluso en el sufrimiento más profundo, siempre hay una elección sobre cómo responder, y que pedir ayuda es un acto de coraje, no de debilidad.

Hoy es un día para recordar a quienes hemos perdido, para aprender a reconocer las señales de alerta, y para comprometernos a crear comunidades donde nadie tenga que sufrir en silencio.''',
            'cita_filosofica': 'La vida no es esperar a que pase la tormenta, es aprender a bailar bajo la lluvia.',
            'autor_cita': 'Séneca (adaptado)',
            'pregunta_1': '¿Has experimentado pensamientos de desesperanza? ¿Con quién puedes hablar sobre esto?',
            'pregunta_2': '¿Conoces las señales de alerta del suicidio en otras personas? ¿Estás atento a ellas?',
            'pregunta_3': '¿Qué te ha ayudado a superar momentos de profunda dificultad en el pasado?',
            'pregunta_4': '¿Cómo puedes crear un espacio más seguro para que otros compartan sus luchas?',
            'pregunta_5': '',
            'accion_sugerida': 'Hoy, aprende sobre las señales de alerta del suicidio y los recursos de ayuda disponibles en tu país. Si estás luchando, llama a una línea de prevención del suicidio. Si conoces a alguien que podría estar en riesgo, acércate con compasión y pregúntale directamente cómo está.',
            'categoria': 'salud',
            'icono': 'fa-hands-helping',
            'color': '#FF5722',
        },

        # 9. EQUINOCCIO DE PRIMAVERA
        {
            'titulo': 'Equinoccio de Primavera: Balance y Renacimiento',
            'slug': 'equinoccio-primavera',
            'fecha_activacion': date(2025, 3, 20),
            'es_recurrente': True,
            'contexto': '''El equinoccio de primavera marca el momento en que el día y la noche tienen la misma duración, un punto de perfecto equilibrio antes de que la luz comience a dominar. Es un símbolo universal de renacimiento, renovación y nuevos comienzos.

Los estoicos valoraban el concepto de "sophrosyne" (templanza o moderación), que es precisamente sobre encontrar el equilibrio en todas las cosas. Ni exceso ni deficiencia, sino el punto medio virtuoso.

La primavera nos invita a reflexionar sobre qué semillas queremos plantar en nuestras vidas. ¿Qué hábitos, relaciones, proyectos o valores queremos cultivar? Así como la naturaleza se despierta del invierno, nosotros también podemos despertar a nuevas posibilidades.''',
            'cita_filosofica': 'La virtud está en el punto medio entre dos extremos.',
            'autor_cita': 'Aristóteles',
            'pregunta_1': '¿Qué áreas de tu vida están desequilibradas en este momento?',
            'pregunta_2': '¿Qué "semillas" (hábitos, proyectos, relaciones) quieres plantar en esta nueva estación?',
            'pregunta_3': '¿Qué necesitas soltar o "podar" para que lo nuevo pueda crecer?',
            'pregunta_4': '¿Cómo puedes encontrar más balance entre acción y descanso, trabajo y juego, soledad y conexión?',
            'pregunta_5': '',
            'accion_sugerida': 'Hoy, identifica un área de tu vida que necesita más equilibrio y toma una acción concreta para restaurarlo. También puedes plantar literalmente una semilla (una planta, un árbol) como símbolo de tu compromiso con el crecimiento.',
            'categoria': 'naturaleza',
            'icono': 'fa-seedling',
            'color': '#8BC34A',
        },

        # 10. AÑO NUEVO: REFLEXIÓN ANUAL
        {
            'titulo': 'Año Nuevo: Reflexión y Renovación',
            'slug': 'ano-nuevo-reflexion',
            'fecha_activacion': date(2025, 1, 1),
            'es_recurrente': True,
            'contexto': '''El Año Nuevo es un momento simbólico de cierre y apertura, una oportunidad para reflexionar sobre el año que termina y establecer intenciones para el que comienza. Pero los estoicos nos recuerdan que cada día es una oportunidad de comenzar de nuevo.

Séneca escribió: "No es que tengamos poco tiempo, sino que perdemos mucho". El Año Nuevo no es mágico por sí mismo, pero puede ser un catalizador poderoso si lo usamos para hacer un examen honesto de nuestra vida.

En lugar de resoluciones superficiales que abandonaremos en febrero, podemos preguntarnos: ¿Quién quiero ser? ¿Qué valores quiero encarnar? ¿Qué legado quiero construir? Y luego, alinear nuestras acciones diarias con esas respuestas.''',
            'cita_filosofica': 'No cuentes los días, haz que los días cuenten.',
            'autor_cita': 'Muhammad Ali (inspirado en filosofía estoica)',
            'pregunta_1': '¿Qué logros del año pasado te llenan de orgullo? ¿Qué aprendiste de tus fracasos?',
            'pregunta_2': '¿Qué hábitos o patrones del año pasado quieres dejar atrás?',
            'pregunta_3': '¿Quién quieres ser dentro de un año? Descríbete con detalle.',
            'pregunta_4': '¿Qué tres valores quieres que guíen tus decisiones este año?',
            'pregunta_5': '¿Qué pequeña acción puedes hacer hoy que te acerque a la persona que quieres ser?',
            'accion_sugerida': 'Hoy, dedica 30 minutos a escribir una revisión completa del año pasado y establecer intenciones claras para el nuevo año. No hagas una lista de deseos, sino un compromiso con valores y acciones concretas. Comparte tus intenciones con alguien que te haga responsable.',
            'categoria': 'personal',
            'icono': 'fa-calendar-alt',
            'color': '#FF9800',
        },
    ]

    # Crear las reflexiones en la base de datos
    reflexiones_creadas = []
    for reflexion_data in reflexiones:
        reflexion, created = ReflexionGuiadaTema.objects.get_or_create(
            slug=reflexion_data['slug'],
            defaults=reflexion_data
        )
        if created:
            reflexiones_creadas.append(reflexion.titulo)
            print(f"✓ Creada: {reflexion.titulo}")
        else:
            print(f"○ Ya existe: {reflexion.titulo}")

    print(f"\n{len(reflexiones_creadas)} reflexiones guiadas creadas exitosamente.")
    return reflexiones_creadas


# Ejecutar la función si se corre el script directamente
if __name__ == "__main__":
    crear_reflexiones_guiadas()
