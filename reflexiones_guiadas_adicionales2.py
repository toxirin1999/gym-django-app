# ============================================
# 20 REFLEXIONES GUIADAS ADICIONALES
# Script para cargar en la base de datos
# ============================================

from diario.models import ReflexionGuiadaTema
from datetime import date

reflexiones = [
    # 1. DÍA MUNDIAL DEL AGUA (22 de marzo)
    {
        'titulo': 'El Agua: Fuente de Vida y Reflexión',
        'slug': 'dia-mundial-del-agua',
        'fecha_activacion': date(2025, 3, 22),
        'es_recurrente': True,
        'contexto': '''El agua cubre el 71% de nuestro planeta, pero solo el 2.5% es agua dulce y apenas el 0.3% es accesible para el consumo humano. Más de 2,000 millones de personas viven en países con estrés hídrico, y para 2050 se estima que la mitad de la población mundial enfrentará escasez de agua.

Los estoicos valoraban profundamente los elementos naturales. Veían en el agua un recordatorio de la fluidez necesaria en la vida: adaptarse, fluir alrededor de los obstáculos, y siempre encontrar el camino hacia adelante. El agua no lucha contra la roca, simplemente la rodea o, con paciencia infinita, la erosiona.

Hoy reflexionamos sobre nuestra relación con este recurso vital. ¿Lo valoramos? ¿Lo desperdiciamos? ¿Somos conscientes de nuestro privilegio al tener acceso a agua potable?''',
        'cita_filosofica': 'Nada es más suave ni más flexible que el agua, pero nada puede resistirla.',
        'autor_cita': 'Lao Tzu',
        'pregunta_1': '¿Cuándo fue la última vez que realmente apreciaste tener acceso a agua limpia? ¿Qué privilegios das por sentado?',
        'pregunta_2': '¿De qué formas podrías ser más consciente de tu consumo de agua? ¿Qué pequeños cambios podrías implementar?',
        'pregunta_3': '¿Cómo puedes aplicar la filosofía del agua a tu vida: ser flexible, persistente, y fluir alrededor de obstáculos?',
        'accion_sugerida': 'Hoy, cada vez que uses agua, toma un momento para agradecer. Investiga una organización que trabaje en acceso al agua potable y considera apoyarla.',
        'categoria': 'naturaleza',
        'icono': 'fa-tint',
        'color': '#2196F3',
        'activa': True,
    },

    # 2. DÍA INTERNACIONAL DE LA FELICIDAD (20 de marzo)
    {
        'titulo': 'Eudaimonia: La Verdadera Felicidad',
        'slug': 'dia-internacional-felicidad',
        'fecha_activacion': date(2025, 3, 20),
        'es_recurrente': True,
        'contexto': '''En 2012, la ONU estableció el 20 de marzo como el Día Internacional de la Felicidad, reconociendo que la búsqueda de la felicidad es un objetivo humano fundamental. Pero, ¿qué es realmente la felicidad?

Los griegos distinguían entre "hedonia" (placer momentáneo) y "eudaimonia" (florecimiento humano). Los estoicos enseñaban que la verdadera felicidad no viene de circunstancias externas, sino del cultivo de la virtud y el vivir de acuerdo con la naturaleza.

Aristóteles definió la eudaimonia como "la actividad del alma de acuerdo con la virtud". No es un estado que se alcanza, sino una forma de vivir. No es sentirse bien todo el tiempo, sino vivir bien consistentemente.

La ciencia moderna confirma esta sabiduría antigua: las personas más felices no son las que persiguen el placer, sino las que encuentran significado, cultivan relaciones profundas, y contribuyen a algo más grande que ellas mismas.''',
        'cita_filosofica': 'La felicidad depende de nosotros mismos.',
        'autor_cita': 'Aristóteles',
        'pregunta_1': '¿Qué te hace verdaderamente feliz a largo plazo, más allá de los placeres momentáneos?',
        'pregunta_2': '¿Estás persiguiendo hedonia (placer) o eudaimonia (florecimiento)? ¿Cuál es la diferencia en tu vida?',
        'pregunta_3': '¿Qué virtudes necesitas cultivar para vivir una vida más plena y significativa?',
        'accion_sugerida': 'Escribe tres cosas que te dan significado profundo (no placer superficial) y comprométete a dedicarles más tiempo esta semana.',
        'categoria': 'filosofia',
        'icono': 'fa-smile',
        'color': '#FFD700',
        'activa': True,
    },

    # 3. DÍA MUNDIAL DE LA POESÍA (21 de marzo)
    {
        'titulo': 'La Belleza de las Palabras',
        'slug': 'dia-mundial-poesia',
        'fecha_activacion': date(2025, 3, 21),
        'es_recurrente': True,
        'contexto': '''La poesía es una de las formas más antiguas de expresión humana. Desde los himnos homéricos hasta los haikus japoneses, la poesía ha sido el vehículo para expresar lo inexpresable: el amor, el dolor, la belleza, la trascendencia.

Marco Aurelio, aunque emperador y filósofo, apreciaba profundamente la poesía. Sus "Meditaciones" están llenas de imágenes poéticas y reflexiones líricas sobre la naturaleza efímera de la vida.

La poesía nos obliga a desacelerar, a saborear cada palabra, a encontrar significado en la economía del lenguaje. En un mundo de información rápida y superficial, la poesía es un acto de resistencia contemplativa.

Escribir o leer poesía es un ejercicio estoico: nos conecta con nuestras emociones profundas, nos ayuda a procesar experiencias difíciles, y nos recuerda la belleza que existe incluso en el sufrimiento.''',
        'cita_filosofica': 'La poesía es la revelación de un sentimiento que el poeta cree que es interior y personal, pero que el lector reconoce como propio.',
        'autor_cita': 'Salvatore Quasimodo',
        'pregunta_1': '¿Cuándo fue la última vez que leíste o escribiste algo poético? ¿Qué te impide hacerlo más seguido?',
        'pregunta_2': '¿Hay alguna experiencia o emoción en tu vida que solo podría expresarse poéticamente, no literalmente?',
        'pregunta_3': '¿Qué belleza has ignorado hoy por estar apurado o distraído?',
        'accion_sugerida': 'Lee un poema que te conmueva. O mejor aún, intenta escribir un poema corto (aunque sea de 4 líneas) sobre algo que estés sintiendo hoy.',
        'categoria': 'personal',
        'icono': 'fa-feather',
        'color': '#9C27B0',
        'activa': True,
    },

    # 4. DÍA MUNDIAL DE LA CREATIVIDAD (21 de abril)
    {
        'titulo': 'Creatividad: El Fuego Interior',
        'slug': 'dia-mundial-creatividad',
        'fecha_activacion': date(2025, 4, 21),
        'es_recurrente': True,
        'contexto': '''La creatividad no es solo para artistas. Es la capacidad humana fundamental de imaginar posibilidades, resolver problemas de formas nuevas, y expresar nuestra perspectiva única del mundo.

Los estoicos valoraban la creatividad como expresión de nuestra naturaleza racional. Marco Aurelio escribió sus "Meditaciones" no como tratado filosófico, sino como ejercicio creativo de autoexploración. Séneca escribió tragedias. Epicteto usaba metáforas y analogías creativas para enseñar.

La neurociencia moderna muestra que la creatividad no es un don mágico, sino una habilidad que se cultiva. Requiere dos cosas: espacio mental (tiempo sin distracciones) y permiso para fallar (experimentar sin juicio).

En un mundo que valora la eficiencia y la productividad, la creatividad es un acto de rebeldía. Es jugar sin propósito, explorar sin destino, crear sin garantía de éxito.''',
        'cita_filosofica': 'La creatividad es la inteligencia divirtiéndose.',
        'autor_cita': 'Albert Einstein',
        'pregunta_1': '¿Cuándo fue la última vez que creaste algo solo por el placer de crear, sin preocuparte por el resultado?',
        'pregunta_2': '¿Qué te impide ser más creativo? ¿Miedo al fracaso? ¿Falta de tiempo? ¿Autocrítica excesiva?',
        'pregunta_3': '¿Qué forma de creatividad te llama pero has ignorado? (Escribir, dibujar, cocinar, construir, componer...)',
        'accion_sugerida': 'Dedica 30 minutos hoy a crear algo, lo que sea, sin juzgarte. No tiene que ser "bueno", solo tiene que ser tuyo.',
        'categoria': 'personal',
        'icono': 'fa-palette',
        'color': '#FF5722',
        'activa': True,
    },

    # 5. DÍA INTERNACIONAL DEL TRABAJO (1 de mayo)
    {
        'titulo': 'El Significado del Trabajo',
        'slug': 'dia-internacional-trabajo',
        'fecha_activacion': date(2025, 5, 1),
        'es_recurrente': True,
        'contexto': '''El Día Internacional del Trabajo conmemora las luchas históricas por derechos laborales justos. Pero también nos invita a reflexionar sobre el significado del trabajo en nuestras vidas.

Los estoicos tenían una visión única del trabajo. Epicteto, que fue esclavo, enseñaba que la libertad no viene de las circunstancias externas sino de nuestra actitud interna. Marco Aurelio, emperador con enormes responsabilidades, se recordaba cada mañana que su trabajo era servir al bien común.

El trabajo puede ser fuente de significado o de sufrimiento. La diferencia no está tanto en qué hacemos, sino en cómo lo hacemos y por qué lo hacemos. ¿Trabajamos solo por dinero? ¿Por estatus? ¿Por contribuir? ¿Por crecer?

Viktor Frankl, sobreviviente del Holocausto, descubrió que incluso en los trabajos más degradantes, encontrar significado era la diferencia entre desesperación y dignidad.''',
        'cita_filosofica': 'Elige un trabajo que ames y no tendrás que trabajar ni un día de tu vida.',
        'autor_cita': 'Confucio',
        'pregunta_1': '¿Qué significado encuentras en tu trabajo actual? Si no encuentras ninguno, ¿qué necesitaría cambiar?',
        'pregunta_2': '¿Trabajas para vivir o vives para trabajar? ¿Cuál es el balance correcto para ti?',
        'pregunta_3': '¿Cómo contribuye tu trabajo al bien común? Si no lo hace, ¿debería hacerlo?',
        'accion_sugerida': 'Identifica una forma en que tu trabajo, por pequeña que sea, beneficia a otros. Enfócate en eso cuando te sientas desmotivado.',
        'categoria': 'personal',
        'icono': 'fa-briefcase',
        'color': '#795548',
        'activa': True,
    },

    # 6. DÍA MUNDIAL SIN TABACO (31 de mayo)
    {
        'titulo': 'Liberarse de las Cadenas',
        'slug': 'dia-mundial-sin-tabaco',
        'fecha_activacion': date(2025, 5, 31),
        'es_recurrente': True,
        'contexto': '''El tabaco mata a más de 8 millones de personas cada año. Pero más allá de las estadísticas, el tabaquismo representa algo profundamente filosófico: la lucha entre lo que sabemos que es correcto y lo que hacemos.

Epicteto enseñaba sobre el concepto de "prohairesis" - nuestra capacidad de elección. Decía que somos verdaderamente libres solo cuando nuestras acciones están alineadas con nuestra razón, no controladas por impulsos o adicciones.

Las adicciones, ya sea al tabaco, alcohol, comida, tecnología o cualquier otra cosa, son formas de esclavitud autoimpuesta. No porque seamos débiles, sino porque somos humanos. Pero los estoicos creían que podemos liberarnos mediante la práctica consciente y la comprensión de nuestros patrones.

Esta reflexión no es solo para fumadores. Todos tenemos "tabaco" en nuestras vidas: hábitos que sabemos que nos dañan pero repetimos. ¿Cuál es el tuyo?''',
        'cita_filosofica': 'No es libre quien no obtiene el dominio sobre sí mismo.',
        'autor_cita': 'Pitágoras',
        'pregunta_1': '¿Qué hábito o adicción (grande o pequeña) te controla más de lo que te gustaría admitir?',
        'pregunta_2': '¿Qué función cumple ese hábito en tu vida? ¿Qué dolor evita o qué vacío llena?',
        'pregunta_3': '¿Qué necesitarías para liberarte? ¿Apoyo? ¿Alternativas más sanas? ¿Confrontar emociones difíciles?',
        'accion_sugerida': 'Identifica tu "tabaco" personal. No necesitas dejarlo hoy, pero sí necesitas nombrarlo y entender por qué lo haces.',
        'categoria': 'salud',
        'icono': 'fa-smoking-ban',
        'color': '#E91E63',
        'activa': True,
    },

    # 7. DÍA MUNDIAL DEL MEDIO AMBIENTE (5 de junio)
    {
        'titulo': 'Vivir de Acuerdo con la Naturaleza',
        'slug': 'dia-mundial-medio-ambiente',
        'fecha_activacion': date(2025, 6, 5),
        'es_recurrente': True,
        'contexto': '''Los estoicos tenían un principio fundamental: "vivir de acuerdo con la naturaleza". Pero no se referían solo a reciclar o plantar árboles (aunque eso ayuda). Se referían a entender nuestro lugar en el cosmos y actuar en armonía con él.

Marco Aurelio escribió: "Todo está entrelazado, y el vínculo es sagrado". Entendía que somos parte de un sistema más grande, no sus dueños. Cada acción tiene consecuencias que se propagan como ondas en un estanque.

Hoy enfrentamos una crisis ambiental sin precedentes: cambio climático, extinción masiva de especies, contaminación, deforestación. Pero el problema no es solo técnico o político. Es filosófico. Hemos olvidado que somos naturaleza, no algo separado de ella.

La pregunta no es solo "¿qué puedo hacer por el medio ambiente?" sino "¿cómo puedo vivir de forma que honre mi conexión con todo lo que existe?"''',
        'cita_filosofica': 'La naturaleza no hace nada en vano.',
        'autor_cita': 'Aristóteles',
        'pregunta_1': '¿Cuándo fue la última vez que realmente te sentiste conectado con la naturaleza? ¿Qué sentiste?',
        'pregunta_2': '¿De qué formas tu estilo de vida está en conflicto con el bienestar del planeta? Sé honesto.',
        'pregunta_3': '¿Qué cambio concreto, por pequeño que sea, podrías hacer para vivir más en armonía con la naturaleza?',
        'accion_sugerida': 'Pasa al menos 20 minutos hoy en contacto directo con la naturaleza (parque, jardín, incluso una planta). Observa sin distracciones.',
        'categoria': 'naturaleza',
        'icono': 'fa-leaf',
        'color': '#4CAF50',
        'activa': True,
    },

    # 8. DÍA INTERNACIONAL DE LA AMISTAD (30 de julio)
    {
        'titulo': 'Philia: El Amor de la Amistad',
        'slug': 'dia-internacional-amistad',
        'fecha_activacion': date(2025, 7, 30),
        'es_recurrente': True,
        'contexto': '''Los griegos tenían múltiples palabras para "amor": eros (pasión), storge (familiar), agape (incondicional), y philia (amistad). Aristóteles dedicó dos libros enteros de su Ética a Nicomaquea a la amistad, considerándola esencial para una vida buena.

Distinguía tres tipos de amistad: de utilidad (nos beneficiamos mutuamente), de placer (disfrutamos estar juntos), y de virtud (nos ayudamos mutuamente a ser mejores personas). Solo la última es verdadera y duradera.

Los estoicos valoraban profundamente la amistad. Séneca escribió cartas extensas a su amigo Lucilio, explorando juntos las grandes preguntas de la vida. Marco Aurelio dedicó el primer libro de sus Meditaciones a agradecer a las personas que lo formaron.

En la era de las redes sociales, tenemos más "amigos" que nunca pero nos sentimos más solos. ¿Cuántas de nuestras amistades son de utilidad o placer, y cuántas son de virtud?''',
        'cita_filosofica': 'Un amigo es un alma que habita en dos cuerpos.',
        'autor_cita': 'Aristóteles',
        'pregunta_1': '¿Quiénes son tus verdaderos amigos, aquellos que te hacen mejor persona? ¿Cuándo fue la última vez que lo expresaste?',
        'pregunta_2': '¿Eres el tipo de amigo que quisieras tener? ¿Qué podrías mejorar?',
        'pregunta_3': '¿Has descuidado alguna amistad importante por estar ocupado? ¿Qué podrías hacer al respecto?',
        'accion_sugerida': 'Contacta hoy a un amigo verdadero que no hayas visto en un tiempo. No por mensaje, sino por llamada o en persona. Dile por qué valoras su amistad.',
        'categoria': 'social',
        'icono': 'fa-user-friends',
        'color': '#FF9800',
        'activa': True,
    },

    # 9. DÍA INTERNACIONAL DE LA JUVENTUD (12 de agosto)
    {
        'titulo': 'La Sabiduría de la Juventud',
        'slug': 'dia-internacional-juventud',
        'fecha_activacion': date(2025, 8, 12),
        'es_recurrente': True,
        'contexto': '''Hay un prejuicio cultural que asocia juventud con inexperiencia y vejez con sabiduría. Pero los estoicos sabían que la sabiduría no es cuestión de edad sino de reflexión.

Marco Aurelio se convirtió en emperador a los 40 años, pero sus escritos muestran una madurez que muchos nunca alcanzan. Epicteto enseñaba que podemos ser viejos tontos o jóvenes sabios. La diferencia está en nuestra disposición a aprender y cuestionar.

Los jóvenes de hoy enfrentan desafíos únicos: crisis climática, incertidumbre económica, sobrecarga de información, presión de redes sociales. Pero también tienen algo que generaciones anteriores no tuvieron: acceso sin precedentes a conocimiento y conexión global.

Esta reflexión es para todos, jóvenes y no tan jóvenes. Para los jóvenes: ¿cómo estás usando tu energía y potencial? Para los mayores: ¿qué puedes aprender de la perspectiva joven?''',
        'cita_filosofica': 'No dejes que nadie menosprecie tu juventud, sino sé ejemplo en palabra, conducta, amor, fe y pureza.',
        'autor_cita': '1 Timoteo 4:12',
        'pregunta_1': '¿Qué sabiduría has adquirido en tu vida hasta ahora, sin importar tu edad?',
        'pregunta_2': '¿Qué estás haciendo con tu potencial? ¿Lo estás desperdiciando o cultivando?',
        'pregunta_3': '¿Qué legado quieres dejar? ¿Qué estás construyendo hoy que importará en 10, 20, 50 años?',
        'accion_sugerida': 'Escribe una carta a tu yo del futuro (5 o 10 años). ¿Qué esperas haber logrado? ¿Qué tipo de persona esperas ser?',
        'categoria': 'personal',
        'icono': 'fa-seedling',
        'color': '#8BC34A',
        'activa': True,
    },

    # 10. DÍA INTERNACIONAL DE LA PAZ (21 de septiembre)
    {
        'titulo': 'Paz Interior, Paz Exterior',
        'slug': 'dia-internacional-paz',
        'fecha_activacion': date(2025, 9, 21),
        'es_recurrente': True,
        'contexto': '''La paz mundial parece un sueño imposible. Guerras, conflictos, violencia... el sufrimiento humano causado por humanos parece no tener fin. Pero los estoicos enseñaban algo radical: la paz exterior comienza con la paz interior.

Marco Aurelio, quien pasó gran parte de su reinado en guerras, escribió: "Puedes tener paz en cualquier momento retirándote a tu interior". No era escapismo, sino reconocer que no podemos controlar el mundo, pero sí podemos controlar nuestra respuesta a él.

La paz no es ausencia de conflicto, sino presencia de justicia, compasión y entendimiento. Y eso comienza en nosotros. ¿Cómo podemos pedir paz en el mundo si no tenemos paz con nosotros mismos? ¿Cómo podemos exigir justicia si somos injustos en nuestras relaciones cercanas?

Gandhi dijo: "Sé el cambio que quieres ver en el mundo". Los estoicos dirían: "Cultiva la paz interior y naturalmente crearás paz exterior".''',
        'cita_filosofica': 'La paz comienza con una sonrisa.',
        'autor_cita': 'Madre Teresa',
        'pregunta_1': '¿Tienes paz interior? ¿Qué conflictos internos te mantienen en guerra contigo mismo?',
        'pregunta_2': '¿Hay alguna relación en tu vida donde necesites hacer las paces? ¿Qué te detiene?',
        'pregunta_3': '¿Cómo contribuyes a la paz o al conflicto en tu entorno inmediato (familia, trabajo, comunidad)?',
        'accion_sugerida': 'Practica 10 minutos de meditación hoy. Luego, realiza un acto de paz: perdona a alguien, resuelve un conflicto, o simplemente sé amable con un extraño.',
        'categoria': 'social',
        'icono': 'fa-dove',
        'color': '#00BCD4',
        'activa': True,
    },

    # 11. DÍA MUNDIAL DE LA ALIMENTACIÓN (16 de octubre)
    {
        'titulo': 'Alimentar el Cuerpo, Nutrir el Alma',
        'slug': 'dia-mundial-alimentacion',
        'fecha_activacion': date(2025, 10, 16),
        'es_recurrente': True,
        'contexto': '''Más de 800 millones de personas en el mundo sufren hambre crónica, mientras que en países desarrollados luchamos contra la obesidad y trastornos alimenticios. Nuestra relación con la comida está rota.

Los estoicos practicaban el ayuno voluntario no por ascetismo, sino para apreciar lo que tienen y prepararse para la escasez. Séneca escribió: "Establece ciertos días en los que te contentarás con muy poco, para que cuando llegue la pobreza real, no te tome por sorpresa".

Pero la comida es más que nutrición física. Es cultura, conexión, ritual. Compartir comida es uno de los actos más humanos. En muchas tradiciones, comer juntos es sagrado.

La pregunta no es solo "¿qué como?" sino "¿cómo como?" ¿Con gratitud o con prisa? ¿Con conciencia o con distracción? ¿Solo o en comunidad?''',
        'cita_filosofica': 'Que tu alimento sea tu medicina, y tu medicina sea tu alimento.',
        'autor_cita': 'Hipócrates',
        'pregunta_1': '¿Cuándo fue la última vez que comiste con plena conciencia, saboreando cada bocado, sin distracciones?',
        'pregunta_2': '¿Tu relación con la comida es saludable? ¿Comes para vivir o vives para comer? ¿Usas la comida para llenar vacíos emocionales?',
        'pregunta_3': '¿Eres consciente del privilegio de tener acceso a comida? ¿Cómo podrías ayudar a quienes no lo tienen?',
        'accion_sugerida': 'Hoy, come al menos una comida sin pantallas, sin prisa, con gratitud. Si es posible, compártela con alguien que ames.',
        'categoria': 'salud',
        'icono': 'fa-utensils',
        'color': '#FF5722',
        'activa': True,
    },

    # 12. DÍA MUNDIAL DE LA FILOSOFÍA (tercer jueves de noviembre - usaremos 21 nov)
    {
        'titulo': 'El Amor a la Sabiduría',
        'slug': 'dia-mundial-filosofia',
        'fecha_activacion': date(2025, 11, 21),
        'es_recurrente': True,
        'contexto': '''La palabra "filosofía" viene del griego "philos" (amor) y "sophia" (sabiduría). No es acumular conocimiento, sino amar la búsqueda de la verdad.

Sócrates, el padre de la filosofía occidental, decía que "una vida sin examen no vale la pena vivirla". No porque la vida no examinada sea mala, sino porque desperdiciaríamos nuestro potencial humano único: la capacidad de reflexionar sobre nuestra existencia.

La filosofía no es abstracta o irrelevante. Es profundamente práctica. Los estoicos la llamaban "el arte de vivir". Cada decisión que tomas refleja una filosofía, consciente o no. ¿Prefieres placer o significado? ¿Éxito o integridad? ¿Aprobación o autenticidad?

En un mundo de respuestas rápidas y certezas superficiales, la filosofía nos enseña a hacer mejores preguntas. No para tener todas las respuestas, sino para vivir con las preguntas correctas.''',
        'cita_filosofica': 'El asombro es el principio de la sabiduría.',
        'autor_cita': 'Sócrates',
        'pregunta_1': '¿Cuál es tu filosofía de vida? Si tuvieras que resumir tus principios fundamentales en 3-5 frases, ¿cuáles serían?',
        'pregunta_2': '¿Qué pregunta filosófica te mantiene despierto por la noche? ¿Qué misterio de la existencia te fascina?',
        'pregunta_3': '¿Vives de acuerdo con tu filosofía declarada, o hay una brecha entre lo que crees y lo que haces?',
        'accion_sugerida': 'Lee un texto filosófico hoy, aunque sea breve. O mejor aún, ten una conversación filosófica profunda con alguien.',
        'categoria': 'filosofia',
        'icono': 'fa-brain',
        'color': '#673AB7',
        'activa': True,
    },

    # 13. DÍA INTERNACIONAL DEL VOLUNTARIADO (5 de diciembre)
    {
        'titulo': 'El Servicio como Virtud',
        'slug': 'dia-internacional-voluntariado',
        'fecha_activacion': date(2025, 12, 5),
        'es_recurrente': True,
        'contexto': '''Los estoicos creían que somos inherentemente sociales. Marco Aurelio escribió: "Lo que no beneficia a la colmena no puede beneficiar a la abeja". Servir a otros no es altruismo sacrificial, sino reconocer nuestra interconexión.

El voluntariado moderno mueve a más de 1,000 millones de personas en el mundo, contribuyendo billones de dólares en valor económico. Pero el verdadero valor no es económico, sino existencial. Servir nos saca de nuestra burbuja egocéntrica y nos recuerda que somos parte de algo más grande.

Paradójicamente, ayudar a otros es una de las mejores formas de ayudarnos a nosotros mismos. La investigación muestra que el voluntariado reduce depresión, aumenta satisfacción de vida, y hasta mejora la salud física. No porque sea transaccional, sino porque estamos diseñados para contribuir.

La pregunta no es "¿tengo tiempo para ser voluntario?" sino "¿puedo darme el lujo de no serlo?"''',
        'cita_filosofica': 'El mejor modo de encontrarse a uno mismo es perderse en el servicio de los demás.',
        'autor_cita': 'Mahatma Gandhi',
        'pregunta_1': '¿Cuándo fue la última vez que ayudaste a alguien sin esperar nada a cambio? ¿Cómo te sentiste?',
        'pregunta_2': '¿Qué causa o comunidad necesita tu ayuda? ¿Qué habilidades únicas podrías ofrecer?',
        'pregunta_3': '¿Qué te impide ser más generoso con tu tiempo? ¿Son razones válidas o excusas?',
        'accion_sugerida': 'Investiga una organización local que necesite voluntarios. No necesitas comprometerte hoy, solo explora las posibilidades.',
        'categoria': 'social',
        'icono': 'fa-hands-helping',
        'color': '#FF9800',
        'activa': True,
    },

    # 14. SOLSTICIO DE VERANO (21 de junio)
    {
        'titulo': 'El Día Más Largo del Año',
        'slug': 'solsticio-verano',
        'fecha_activacion': date(2025, 6, 21),
        'es_recurrente': True,
        'contexto': '''El solsticio de verano marca el día más largo del año en el hemisferio norte. Desde tiempos ancestrales, los humanos han celebrado este momento como símbolo de abundancia, luz y vida.

Los estoicos veían los ciclos naturales como maestros. Así como el sol alcanza su punto máximo y luego comienza a declinar, todo en la vida tiene su apogeo y su caída. No con tristeza, sino con aceptación. Es la naturaleza de las cosas.

Este es un momento para celebrar la luz, pero también para recordar que la oscuridad vendrá. No para temer el invierno, sino para apreciar el verano. Para guardar energía, como las plantas que florecen ahora sabiendo que el frío llegará.

Heráclito enseñaba que "todo fluye". El sol que hoy está en su máximo esplendor, mañana comenzará su descenso. Y eso está bien. Es el orden natural. Resistirlo es sufrir innecesariamente.''',
        'cita_filosofica': 'Haz como el sol: sal cada día y brilla, sin esperar agradecimiento.',
        'autor_cita': 'Proverbio',
        'pregunta_1': '¿Qué está en su "solsticio" en tu vida ahora mismo? ¿Qué está en su punto máximo?',
        'pregunta_2': '¿Estás aprovechando este momento de abundancia o lo das por sentado?',
        'pregunta_3': '¿Cómo puedes prepararte para los "inviernos" inevitables de la vida sin vivir con miedo?',
        'accion_sugerida': 'Pasa tiempo al sol hoy. Literalmente. Siente su calor en tu piel y agradece esta estrella que hace posible toda la vida en la Tierra.',
        'categoria': 'naturaleza',
        'icono': 'fa-sun',
        'color': '#FFC107',
        'activa': True,
    },

    # 15. DÍA MUNDIAL DE LA GRATITUD (21 de septiembre - fecha alternativa)
    {
        'titulo': 'La Práctica de la Gratitud',
        'slug': 'dia-mundial-gratitud',
        'fecha_activacion': date(2025, 11, 27),
        'es_recurrente': True,
        'contexto': '''La gratitud era una práctica central en el estoicismo. Marco Aurelio comenzaba cada día agradeciendo a las personas que lo habían formado. Epicteto enseñaba que la felicidad no viene de tener lo que queremos, sino de querer lo que tenemos.

La ciencia moderna confirma lo que los estoicos sabían: la gratitud es una de las prácticas más poderosas para el bienestar mental. Personas que practican gratitud regularmente reportan mayor felicidad, mejor salud, relaciones más fuertes, y mayor resiliencia ante adversidades.

Pero la gratitud no es solo decir "gracias". Es una forma de ver el mundo. Es reconocer que todo lo que tenemos es un regalo temporal, no un derecho permanente. Es apreciar lo ordinario como extraordinario.

El opuesto de la gratitud no es la ingratitud, sino la expectativa. Cuando esperamos que las cosas buenas nos sucedan, dejamos de apreciarlas cuando llegan.''',
        'cita_filosofica': 'No es el hombre que tiene poco, sino el que desea más, quien es pobre.',
        'autor_cita': 'Séneca',
        'pregunta_1': '¿Qué tres cosas en tu vida das por sentado pero deberías agradecer profundamente?',
        'pregunta_2': '¿A quién en tu vida no has agradecido lo suficiente? ¿Qué te impide hacerlo?',
        'pregunta_3': '¿Cómo cambiaría tu vida si vieras cada día como un regalo, no como un derecho?',
        'accion_sugerida': 'Escribe una carta de gratitud a alguien que haya impactado tu vida positivamente. No necesitas enviarla (aunque sería hermoso), pero escríbela con sinceridad.',
        'categoria': 'personal',
        'icono': 'fa-heart',
        'color': '#E91E63',
        'activa': True,
    },

    # 16. DÍA INTERNACIONAL DE LAS PERSONAS CON DISCAPACIDAD (3 de diciembre)
    {
        'titulo': 'Capacidad en la Diversidad',
        'slug': 'dia-personas-discapacidad',
        'fecha_activacion': date(2025, 12, 3),
        'es_recurrente': True,
        'contexto': '''Más de 1,000 millones de personas en el mundo viven con alguna forma de discapacidad. Pero "discapacidad" es un término problemático. ¿Discapacidad para qué? ¿Según quién?

Los estoicos tenían una perspectiva radical: lo único que realmente importa es nuestro carácter, nuestra capacidad de elegir la virtud. Epicteto, quien vivió con una discapacidad física, enseñaba que la verdadera libertad no depende del cuerpo sino de la mente.

La sociedad moderna está comenzando a entender el "modelo social de la discapacidad": las personas no están discapacitadas, la sociedad las discapacita al no ser inclusiva. Un edificio sin rampa no es un problema de la persona en silla de ruedas, es un problema del edificio.

Pero más profundamente, todos estamos "discapacitados" en algún sentido. Todos tenemos limitaciones. La pregunta no es si las tenemos, sino cómo respondemos a ellas.''',
        'cita_filosofica': 'No es lo que te sucede, sino cómo reaccionas a ello lo que importa.',
        'autor_cita': 'Epicteto',
        'pregunta_1': '¿Qué "discapacidades" (limitaciones, miedos, traumas) tienes que no son visibles pero te afectan?',
        'pregunta_2': '¿Cómo juzgas a las personas por sus limitaciones en lugar de apreciar sus capacidades?',
        'pregunta_3': '¿Qué podrías hacer para ser más inclusivo y empático con personas que tienen experiencias diferentes a la tuya?',
        'accion_sugerida': 'Aprende sobre la experiencia de vivir con una discapacidad específica. Lee, escucha, o mejor aún, conversa con alguien que la viva.',
        'categoria': 'social',
        'icono': 'fa-universal-access',
        'color': '#2196F3',
        'activa': True,
    },

    # 17. DÍA INTERNACIONAL DEL PERDÓN (7 de julio - fecha propuesta)
    {
        'titulo': 'El Poder de Soltar',
        'slug': 'dia-internacional-perdon',
        'fecha_activacion': date(2025, 7, 7),
        'es_recurrente': True,
        'contexto': '''Marco Aurelio escribió: "La mejor venganza es no ser como tu enemigo". Los estoicos entendían que el resentimiento es un veneno que bebemos esperando que mate a nuestro enemigo.

El perdón no es decir que lo que pasó estuvo bien. No es reconciliarse con quien te hirió. No es olvidar. El perdón es soltar el resentimiento que te está envenenando. Es liberarte de la prisión emocional donde el pasado te mantiene cautivo.

La investigación psicológica muestra que el perdón reduce estrés, ansiedad y depresión. Mejora la salud cardiovascular. Fortalece relaciones. Pero el mayor beneficio es existencial: te devuelve tu poder. Mientras no perdones, quien te hirió sigue controlándote.

El perdón más difícil no es perdonar a otros, sino perdonarnos a nosotros mismos. Cargamos culpa por errores pasados, decisiones equivocadas, oportunidades perdidas. Pero como dijo Séneca: "Errar es humano, perseverar en el error es diabólico".''',
        'cita_filosofica': 'Aferrarse al enojo es como beber veneno y esperar que la otra persona muera.',
        'autor_cita': 'Buda',
        'pregunta_1': '¿A quién necesitas perdonar pero no has podido? ¿Qué te detiene?',
        'pregunta_2': '¿Qué error de tu pasado no te has perdonado? ¿Por qué sigues castigándote?',
        'pregunta_3': '¿Cómo sería tu vida si soltaras todo ese resentimiento y culpa? ¿Qué ganarías?',
        'accion_sugerida': 'Escribe una carta de perdón (a alguien más o a ti mismo). No necesitas enviarla. Luego, quémala como símbolo de soltar.',
        'categoria': 'personal',
        'icono': 'fa-hand-holding-heart',
        'color': '#9C27B0',
        'activa': True,
    },

    # 18. DÍA MUNDIAL DE LA POBLACIÓN (11 de julio)
    {
        'titulo': 'Somos 8 Mil Millones',
        'slug': 'dia-mundial-poblacion',
        'fecha_activacion': date(2025, 7, 11),
        'es_recurrente': True,
        'contexto': '''En noviembre de 2022, la población mundial alcanzó 8,000 millones de personas. Es un número difícil de comprender. Si contaras una persona por segundo, te tomaría más de 250 años contar a todos.

Marco Aurelio, gobernando un imperio de millones, se recordaba constantemente: "Pronto serás cenizas o huesos, un mero nombre o ni siquiera eso". No con pesimismo, sino con perspectiva. Somos una gota en un océano de humanidad.

Pero cada gota importa. Cada una de esas 8,000 millones de personas tiene sueños, miedos, esperanzas, dolor. Cada una es el protagonista de su propia historia. Cada una merece dignidad.

El desafío de nuestra era es balancear dos verdades: somos insignificantes en la escala cósmica, pero infinitamente valiosos en la escala humana. Somos muchos, pero cada uno cuenta.''',
        'cita_filosofica': 'En la vida de cada hombre hay un momento en que debe decidir si va a vivir entre los muchos o entre los pocos.',
        'autor_cita': 'Proverbio',
        'pregunta_1': '¿Te sientes insignificante en un mundo de 8,000 millones? ¿Cómo afecta eso tu sentido de propósito?',
        'pregunta_2': '¿Cómo puedes contribuir al bienestar colectivo sin perderte en la masa?',
        'pregunta_3': '¿Ves a los demás como números o como personas? ¿Cómo puedes cultivar más empatía en un mundo tan poblado?',
        'accion_sugerida': 'Hoy, realmente mira a las personas que encuentres. No como extras en tu película, sino como protagonistas de las suyas.',
        'categoria': 'social',
        'icono': 'fa-globe',
        'color': '#00BCD4',
        'activa': True,
    },

    # 19. DÍA INTERNACIONAL DE LA ALFABETIZACIÓN (8 de septiembre)
    {
        'titulo': 'El Poder de las Letras',
        'slug': 'dia-internacional-alfabetizacion',
        'fecha_activacion': date(2025, 9, 8),
        'es_recurrente': True,
        'contexto': '''Más de 770 millones de adultos en el mundo no saben leer ni escribir. La mayoría son mujeres. La alfabetización no es solo una habilidad técnica, es una puerta a la libertad.

Epicteto, quien fue esclavo, valoraba profundamente la educación como camino a la libertad interior. No podía controlar su situación externa, pero podía educar su mente. Eventualmente, su sabiduría lo liberó de formas que la abolición de la esclavitud no podría.

Leer y escribir nos conecta con la humanidad a través del tiempo y el espacio. Puedo leer las palabras de Marco Aurelio escritas hace 2,000 años y sentir que me habla directamente. Puedo escribir estas palabras y quizás alguien las lea en 100 años.

Si estás leyendo esto, tienes un privilegio que millones no tienen. ¿Qué estás haciendo con él?''',
        'cita_filosofica': 'Una vez que aprendes a leer, serás libre para siempre.',
        'autor_cita': 'Frederick Douglass',
        'pregunta_1': '¿Qué libro ha cambiado tu vida? ¿Por qué? ¿Se lo has recomendado a alguien?',
        'pregunta_2': '¿Lees para escapar o para crecer? ¿Qué tipo de contenido consumes mayormente?',
        'pregunta_3': '¿Cómo podrías usar tu alfabetización para ayudar a otros? ¿Enseñar? ¿Escribir? ¿Compartir conocimiento?',
        'accion_sugerida': 'Lee algo profundo hoy, no entretenimiento superficial. Luego, escribe una reflexión sobre lo que aprendiste.',
        'categoria': 'personal',
        'icono': 'fa-book-reader',
        'color': '#3F51B5',
        'activa': True,
    },

    # 20. DÍA INTERNACIONAL DE LA TOLERANCIA (16 de noviembre)
    {
        'titulo': 'Más Allá de la Tolerancia',
        'slug': 'dia-internacional-tolerancia',
        'fecha_activacion': date(2025, 11, 16),
        'es_recurrente': True,
        'contexto': '''La palabra "tolerancia" es problemática. Tolerar implica soportar algo desagradable. ¿Es eso lo mejor que podemos aspirar? Los estoicos nos invitan a algo más profundo: comprensión.

Marco Aurelio escribió: "Cuando te despiertes por la mañana, piensa en qué precioso privilegio es estar vivo: respirar, pensar, disfrutar, amar". Pero también escribió: "Hoy me encontraré con personas entrometidas, ingratas, arrogantes, deshonestas, celosas y huraños". Su solución no era tolerarlas, sino entenderlas.

Vivimos en tiempos polarizados. Nos dividimos por política, religión, raza, género, nacionalidad. Pero los estoicos enseñaban cosmopolitismo: somos ciudadanos del cosmos, todos parte de la misma familia humana.

La tolerancia es el mínimo. La comprensión es el objetivo. El amor es el ideal. No amor romántico, sino reconocer la humanidad compartida en cada persona, incluso en aquellos con quienes profundamente discrepamos.''',
        'cita_filosofica': 'En lo esencial, unidad; en lo dudoso, libertad; en todo, caridad.',
        'autor_cita': 'San Agustín',
        'pregunta_1': '¿A quién "toleras" pero no comprendes? ¿Qué te impide intentar entender su perspectiva?',
        'pregunta_2': '¿En qué áreas eres intolerante? ¿Son principios no negociables o prejuicios sin examinar?',
        'pregunta_3': '¿Cómo puedes construir puentes en lugar de muros, incluso con personas muy diferentes a ti?',
        'accion_sugerida': 'Ten una conversación genuina con alguien que piense muy diferente a ti. No para convencer, sino para entender. Escucha más de lo que hablas.',
        'categoria': 'social',
        'icono': 'fa-hands',
        'color': '#FF9800',
        'activa': True,
    },
]

# Función para cargar las reflexiones
def cargar_reflexiones_adicionales():
    """
    Ejecuta este script para cargar las 20 reflexiones adicionales.
    """
    contador = 0
    for reflexion_data in reflexiones:
        reflexion, created = ReflexionGuiadaTema.objects.get_or_create(
            slug=reflexion_data['slug'],
            defaults=reflexion_data
        )
        if created:
            contador += 1
            print(f"✓ Creada: {reflexion_data['titulo']}")
        else:
            print(f"- Ya existe: {reflexion_data['titulo']}")
    
    print(f"\n{contador} reflexiones nuevas creadas exitosamente.")
    print(f"Total de reflexiones en la base de datos: {ReflexionGuiadaTema.objects.count()}")

# Para ejecutar este script:
# python manage.py shell
# >>> exec(open('reflexiones_guiadas_adicionales.py').read())
# >>> cargar_reflexiones_adicionales()

