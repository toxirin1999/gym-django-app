# Script SOLO para crear los 100 Arquetipos del Códice de las Leyendas
# Sin pruebas - solo los arquetipos
# Ejecutar con: python manage.py shell < script_solo_arquetipos.py

from logros.models import Arquetipo, PruebaLegendaria

# Limpiar datos existentes
print("🧹 Limpiando datos existentes...")
PruebaLegendaria.objects.all().delete()
Arquetipo.objects.all().delete()

print("🎮 Creando el Códice de las Leyendas con 100 Arquetipos...")

# Lista completa de arquetipos (del 100 al 1, donde 1 es el más fuerte)
arquetipos_data = [
    # Niveles 1-10: Los Aspirantes (Humanos extraordinarios)
    {'nivel': 1, 'nombre_personaje': 'Saitama (inicio)', 'titulo_arquetipo': 'El Aspirante Calvo', 'filosofia': 'Todo poder comienza con 100 flexiones, 100 abdominales, 100 sentadillas y 10km de carrera. La simplicidad es la clave.', 'puntos_requeridos': 0, 'icono_fa': 'fas fa-fist-raised'},
    {'nivel': 2, 'nombre_personaje': 'Rock Lee', 'titulo_arquetipo': 'El Genio del Esfuerzo', 'filosofia': 'Sin talento natural, solo trabajo duro. Demuestras que la dedicación puede superar cualquier don innato.', 'puntos_requeridos': 500, 'icono_fa': 'fas fa-running'},
    {'nivel': 3, 'nombre_personaje': 'Roronoa Zoro', 'titulo_arquetipo': 'El Espadachín Perdido', 'filosofia': 'Tres espadas, una voluntad inquebrantable. Tu determinación corta a través de cualquier obstáculo.', 'puntos_requeridos': 1000, 'icono_fa': 'fas fa-sword'},
    {'nivel': 4, 'nombre_personaje': 'Kenshiro', 'titulo_arquetipo': 'El Puño de la Estrella del Norte', 'filosofia': 'Ya estás muerto... para la mediocridad. Tu técnica es letal y tu corazón, compasivo.', 'puntos_requeridos': 1500, 'icono_fa': 'fas fa-fist-raised'},
    {'nivel': 5, 'nombre_personaje': 'All Might', 'titulo_arquetipo': 'El Símbolo de la Paz', 'filosofia': 'Un verdadero héroe no es medido por su fuerza, sino por cómo inspira a otros a ser mejores.', 'puntos_requeridos': 2000, 'icono_fa': 'fas fa-shield-alt'},
    {'nivel': 6, 'nombre_personaje': 'Yujiro Hanma', 'titulo_arquetipo': 'El Ogro Más Fuerte', 'filosofia': 'La fuerza física pura en su máxima expresión. Eres una calamidad natural con forma humana.', 'puntos_requeridos': 2500, 'icono_fa': 'fas fa-dumbbell'},
    {'nivel': 7, 'nombre_personaje': 'Goku Niño', 'titulo_arquetipo': 'El Pequeño Guerrero', 'filosofia': 'La inocencia combinada con un poder increíble. Tu pureza de corazón es tu mayor fortaleza.', 'puntos_requeridos': 3000, 'icono_fa': 'fas fa-child'},
    {'nivel': 8, 'nombre_personaje': 'Edward Elric', 'titulo_arquetipo': 'El Alquimista de Acero', 'filosofia': 'Entiendes el intercambio equivalente: para ganar algo, debes sacrificar algo de igual valor.', 'puntos_requeridos': 3500, 'icono_fa': 'fas fa-atom'},
    {'nivel': 9, 'nombre_personaje': 'Inuyasha', 'titulo_arquetipo': 'El Medio Demonio', 'filosofia': 'Entre dos mundos, perteneces a ambos. Tu naturaleza dual es tu mayor fortaleza.', 'puntos_requeridos': 4000, 'icono_fa': 'fas fa-paw'},
    {'nivel': 10, 'nombre_personaje': 'Shōto Todoroki', 'titulo_arquetipo': 'El Heredero Dividido', 'filosofia': 'Hielo y fuego en perfecta armonía. Has aprendido a abrazar ambos lados de tu poder.', 'puntos_requeridos': 4500, 'icono_fa': 'fas fa-fire'},

    # Niveles 11-20: Los Guerreros (Poder planetario inicial)
    {'nivel': 11, 'nombre_personaje': 'Vegeta (Saiyan Saga)', 'titulo_arquetipo': 'El Príncipe Orgulloso', 'filosofia': 'El orgullo Saiyan corre por tus venas. Nunca te conformas con ser segundo.', 'puntos_requeridos': 5000, 'icono_fa': 'fas fa-crown'},
    {'nivel': 12, 'nombre_personaje': 'Piccolo (Saiyan Saga)', 'titulo_arquetipo': 'El Demonio Redentor', 'filosofia': 'De villano a mentor. Has encontrado la redención a través del sacrificio por otros.', 'puntos_requeridos': 5500, 'icono_fa': 'fas fa-user-ninja'},
    {'nivel': 13, 'nombre_personaje': 'Gaara', 'titulo_arquetipo': 'El Kazekage de Arena', 'filosofia': 'La soledad te forjó, pero el amor te transformó. Proteges a quienes amas con arena inquebrantable.', 'puntos_requeridos': 6000, 'icono_fa': 'fas fa-mountain'},
    {'nivel': 14, 'nombre_personaje': 'Jotaro Kujo', 'titulo_arquetipo': 'El Cruzado Estelar', 'filosofia': 'Yare yare daze. Tu Stand refleja tu alma: preciso, poderoso e implacable.', 'puntos_requeridos': 6500, 'icono_fa': 'fas fa-star'},
    {'nivel': 15, 'nombre_personaje': 'Ichigo (pre-Bankai)', 'titulo_arquetipo': 'El Shinigami Sustituto', 'filosofia': 'Proteges a los que amas sin importar el costo. Tu determinación trasciende la muerte misma.', 'puntos_requeridos': 7000, 'icono_fa': 'fas fa-sword'},
    {'nivel': 16, 'nombre_personaje': 'Natsu Dragneel', 'titulo_arquetipo': 'El Dragon Slayer de Fuego', 'filosofia': 'El fuego de la amistad arde en tu corazón. Por tus nakama, puedes quemar el mundo entero.', 'puntos_requeridos': 7500, 'icono_fa': 'fas fa-fire'},
    {'nivel': 17, 'nombre_personaje': 'Yusuke Urameshi', 'titulo_arquetipo': 'El Detective Espiritual', 'filosofia': 'De delincuente a salvador. Tu energía espiritual refleja tu crecimiento como persona.', 'puntos_requeridos': 8000, 'icono_fa': 'fas fa-ghost'},
    {'nivel': 18, 'nombre_personaje': 'Barbablanca', 'titulo_arquetipo': 'El Hombre Más Fuerte del Mundo', 'filosofia': 'Tus hijos son tu tesoro más preciado. El poder de destruir el mundo palidece ante el amor paternal.', 'puntos_requeridos': 8500, 'icono_fa': 'fas fa-anchor'},
    {'nivel': 19, 'nombre_personaje': 'Escanor', 'titulo_arquetipo': 'El León del Orgullo', 'filosofia': 'Durante el día, eres la encarnación del orgullo. Tu poder crece con el sol que llevas dentro.', 'puntos_requeridos': 9000, 'icono_fa': 'fas fa-sun'},
    {'nivel': 20, 'nombre_personaje': 'Meliodas', 'titulo_arquetipo': 'El Capitán de los Pecados', 'filosofia': 'El poder demoníaco y el corazón humano coexisten en ti. Lideras con fuerza y compasión.', 'puntos_requeridos': 9500, 'icono_fa': 'fas fa-dragon'},

    # Niveles 21-30: Los Saiyans (Poder planetario avanzado)
    {'nivel': 21, 'nombre_personaje': 'Goku (Namek)', 'titulo_arquetipo': 'El Super Saiyan Legendario', 'filosofia': 'La leyenda se ha hecho realidad. Tu transformación dorada marca el inicio de una nueva era.', 'puntos_requeridos': 10000, 'icono_fa': 'fas fa-bolt'},
    {'nivel': 22, 'nombre_personaje': 'Vegeta (Namek)', 'titulo_arquetipo': 'El Príncipe Élite', 'filosofia': 'Tu orgullo Saiyan ha evolucionado. Ya no peleas solo por ti, sino por aquellos que proteges.', 'puntos_requeridos': 11000, 'icono_fa': 'fas fa-crown'},
    {'nivel': 23, 'nombre_personaje': 'Freezer (final Namek)', 'titulo_arquetipo': 'El Emperador del Universo', 'filosofia': 'El poder absoluto corrompe absolutamente. Eres la encarnación del mal en su forma más pura.', 'puntos_requeridos': 12000, 'icono_fa': 'fas fa-snowflake'},
    {'nivel': 24, 'nombre_personaje': 'Cell Perfecto', 'titulo_arquetipo': 'La Perfección Artificial', 'filosofia': 'Eres la culminación de la ciencia y la evolución. La perfección tiene un precio: la soledad.', 'puntos_requeridos': 13000, 'icono_fa': 'fas fa-dna'},
    {'nivel': 25, 'nombre_personaje': 'Majin Buu (Gordo)', 'titulo_arquetipo': 'La Destrucción Inocente', 'filosofia': 'Tu poder destructivo es solo igualado por tu inocencia. Eres caos puro con corazón de niño.', 'puntos_requeridos': 14000, 'icono_fa': 'fas fa-candy-cane'},
    {'nivel': 26, 'nombre_personaje': 'Madara Uchiha', 'titulo_arquetipo': 'El Fantasma de los Uchiha', 'filosofia': 'Has visto el ciclo infinito de odio. Tu sueño de paz justifica cualquier medio.', 'puntos_requeridos': 15000, 'icono_fa': 'fas fa-eye'},
    {'nivel': 27, 'nombre_personaje': 'Hashirama Senju', 'titulo_arquetipo': 'El Dios de los Shinobi', 'filosofia': 'Tu voluntad de fuego ilumina el camino hacia la paz. Eres el ideal que todos los Hokage aspiran a ser.', 'puntos_requeridos': 16000, 'icono_fa': 'fas fa-tree'},
    {'nivel': 28, 'nombre_personaje': 'Obito Jinchūriki Jubi', 'titulo_arquetipo': 'El Sabio de los Seis Caminos Falso', 'filosofia': 'El dolor te transformó en lo que juraste destruir. Buscas crear un mundo sin sufrimiento.', 'puntos_requeridos': 17000, 'icono_fa': 'fas fa-mask'},
    {'nivel': 29, 'nombre_personaje': 'Naruto (Sabio+Kurama)', 'titulo_arquetipo': 'El Jinchūriki Perfecto', 'filosofia': 'Has convertido el odio en amor, la maldición en bendición. Eres la prueba de que nadie está perdido.', 'puntos_requeridos': 18000, 'icono_fa': 'fas fa-leaf'},
    {'nivel': 30, 'nombre_personaje': 'Sasuke (Rinnegan+EMS)', 'titulo_arquetipo': 'El Último Uchiha', 'filosofia': 'Has caminado por la oscuridad para proteger la luz. Tu redención es tu mayor victoria.', 'puntos_requeridos': 19000, 'icono_fa': 'fas fa-lightning-bolt'},

    # Niveles 31-40: Los Trascendentes (Poder universal inicial)
    {'nivel': 31, 'nombre_personaje': 'Goku (SSJ3)', 'titulo_arquetipo': 'El Guerrero Sin Límites', 'filosofia': 'Has roto las barreras de lo posible. Tu sed de batalla trasciende la comprensión mortal.', 'puntos_requeridos': 20000, 'icono_fa': 'fas fa-bolt'},
    {'nivel': 32, 'nombre_personaje': 'Vegeta (Majin)', 'titulo_arquetipo': 'El Príncipe Caído', 'filosofia': 'Has abrazado la oscuridad para recuperar tu orgullo. Incluso caído, sigues siendo realeza.', 'puntos_requeridos': 22000, 'icono_fa': 'fas fa-crown'},
    {'nivel': 33, 'nombre_personaje': 'Kid Buu', 'titulo_arquetipo': 'La Destrucción Pura', 'filosofia': 'Eres el mal en su estado más primitivo. No hay razonamiento, solo aniquilación total.', 'puntos_requeridos': 24000, 'icono_fa': 'fas fa-skull'},
    {'nivel': 34, 'nombre_personaje': 'Gotenks SSJ3', 'titulo_arquetipo': 'La Fusión Prodigiosa', 'filosofia': 'Dos niños se convierten en un guerrero legendario. Tu poder es solo igualado por tu arrogancia.', 'puntos_requeridos': 26000, 'icono_fa': 'fas fa-users'},
    {'nivel': 35, 'nombre_personaje': 'Ichigo (Bankai+Hollow)', 'titulo_arquetipo': 'El Híbrido Definitivo', 'filosofia': 'Shinigami, Quincy, Hollow y Humano. Eres la convergencia de todos los poderes espirituales.', 'puntos_requeridos': 28000, 'icono_fa': 'fas fa-yin-yang'},
    {'nivel': 36, 'nombre_personaje': 'Aizen (Hōgyoku)', 'titulo_arquetipo': 'El Dios Autoproclamado', 'filosofia': 'Has trascendido los límites de la existencia espiritual. Tu evolución no conoce fin.', 'puntos_requeridos': 30000, 'icono_fa': 'fas fa-gem'},
    {'nivel': 37, 'nombre_personaje': 'Kaguya Ōtsutsuki', 'titulo_arquetipo': 'La Diosa Conejo', 'filosofia': 'Eres el origen de todo chakra. Tu poder es tan antiguo como la misma creación.', 'puntos_requeridos': 32000, 'icono_fa': 'fas fa-moon'},
    {'nivel': 38, 'nombre_personaje': 'Sailor Moon (clásica)', 'titulo_arquetipo': 'La Guerrera de la Luna', 'filosofia': 'En nombre de la Luna, castigas a los malvados. Tu amor puede purificar cualquier oscuridad.', 'puntos_requeridos': 34000, 'icono_fa': 'fas fa-moon'},
    {'nivel': 39, 'nombre_personaje': 'Seiya (Bronce Hades)', 'titulo_arquetipo': 'El Caballero de Pegaso', 'filosofia': 'Tu cosmo arde con la fuerza de las estrellas. Proteges a Athena con tu vida.', 'puntos_requeridos': 36000, 'icono_fa': 'fas fa-horse'},
    {'nivel': 40, 'nombre_personaje': 'Hades', 'titulo_arquetipo': 'El Señor del Inframundo', 'filosofia': 'Gobiernas sobre la muerte misma. Tu dominio se extiende más allá de la comprensión mortal.', 'puntos_requeridos': 38000, 'icono_fa': 'fas fa-skull-crossbones'},

    # Niveles 41-50: Los Divinos (Poder universal avanzado)
    {'nivel': 41, 'nombre_personaje': 'Goku (SSJ God)', 'titulo_arquetipo': 'El Saiyan Divino', 'filosofia': 'Has alcanzado el reino de los dioses. Tu ki divino trasciende la comprensión mortal.', 'puntos_requeridos': 40000, 'icono_fa': 'fas fa-bolt'},
    {'nivel': 42, 'nombre_personaje': 'Vegeta (SSJ Blue inicial)', 'titulo_arquetipo': 'El Príncipe Azul', 'filosofia': 'Has combinado lo divino con lo mortal. Tu orgullo ahora tiene respaldo divino.', 'puntos_requeridos': 45000, 'icono_fa': 'fas fa-crown'},
    {'nivel': 43, 'nombre_personaje': 'Beerus', 'titulo_arquetipo': 'El Dios de la Destrucción', 'filosofia': 'Mantienes el equilibrio del universo a través de la destrucción. Tu poder es caprichoso pero necesario.', 'puntos_requeridos': 50000, 'icono_fa': 'fas fa-cat'},
    {'nivel': 44, 'nombre_personaje': 'Whis', 'titulo_arquetipo': 'El Ángel Instructor', 'filosofia': 'Eres la calma en la tormenta. Tu sabiduría y poder guían incluso a los dioses.', 'puntos_requeridos': 55000, 'icono_fa': 'fas fa-feather'},
    {'nivel': 45, 'nombre_personaje': 'Broly (DB Super)', 'titulo_arquetipo': 'El Saiyan Legendario', 'filosofia': 'Tu poder crece sin límites cuando la ira te consume. Eres la fuerza bruta personificada.', 'puntos_requeridos': 60000, 'icono_fa': 'fas fa-fire'},
    {'nivel': 46, 'nombre_personaje': 'Gogeta Blue', 'titulo_arquetipo': 'La Fusión Divina', 'filosofia': 'Dos guerreros divinos se convierten en uno. Tu poder combinado desafía la lógica.', 'puntos_requeridos': 65000, 'icono_fa': 'fas fa-users'},
    {'nivel': 47, 'nombre_personaje': 'Vegito Blue', 'titulo_arquetipo': 'El Guerrero Fusionado', 'filosofia': 'La rivalidad se convierte en sinergia perfecta. Eres más que la suma de tus partes.', 'puntos_requeridos': 70000, 'icono_fa': 'fas fa-infinity'},
    {'nivel': 48, 'nombre_personaje': 'Zamasu Fusionado', 'titulo_arquetipo': 'La Justicia Divina Corrupta', 'filosofia': 'Tu concepto de justicia ha sido corrompido por el poder. Buscas la perfección a través del genocidio.', 'puntos_requeridos': 75000, 'icono_fa': 'fas fa-balance-scale'},
    {'nivel': 49, 'nombre_personaje': 'Jiren', 'titulo_arquetipo': 'El Guerrero de la Justicia', 'filosofia': 'Has trascendido el tiempo mismo con tu fuerza. Tu justicia es absoluta e inquebrantable.', 'puntos_requeridos': 80000, 'icono_fa': 'fas fa-shield'},
    {'nivel': 50, 'nombre_personaje': 'Moro', 'titulo_arquetipo': 'El Devorador de Planetas', 'filosofia': 'Absorbes la energía de mundos enteros. Tu hambre de poder no conoce límites.', 'puntos_requeridos': 85000, 'icono_fa': 'fas fa-black-hole'},

    # Niveles 51-60: Los Omnipotentes (Poder multiversal inicial)
    {'nivel': 51, 'nombre_personaje': 'Zeno Sama', 'titulo_arquetipo': 'El Rey de Todo', 'filosofia': 'Con un gesto puedes borrar universos enteros. Tu inocencia infantil contrasta con tu poder absoluto.', 'puntos_requeridos': 90000, 'icono_fa': 'fas fa-crown'},
    {'nivel': 52, 'nombre_personaje': 'Daishinkan', 'titulo_arquetipo': 'El Gran Sacerdote', 'filosofia': 'Eres el ángel de los ángeles. Tu sabiduría y poder son los pilares de la existencia multiversal.', 'puntos_requeridos': 100000, 'icono_fa': 'fas fa-praying-hands'},
    {'nivel': 53, 'nombre_personaje': 'Anti-Spiral', 'titulo_arquetipo': 'La Negación de la Evolución', 'filosofia': 'Representas la estasis absoluta. Tu misión es prevenir que el universo se destruya por el exceso de evolución.', 'puntos_requeridos': 110000, 'icono_fa': 'fas fa-ban'},
    {'nivel': 54, 'nombre_personaje': 'Simon (TTGL)', 'titulo_arquetipo': 'El Perforador de Cielos', 'filosofia': 'Tu taladro puede perforar los cielos mismos. Representas la evolución y el progreso infinito.', 'puntos_requeridos': 120000, 'icono_fa': 'fas fa-rocket'},
    {'nivel': 55, 'nombre_personaje': 'Madoka Kaname (Diosa)', 'titulo_arquetipo': 'La Diosa de la Esperanza', 'filosofia': 'Te sacrificaste para reescribir las leyes del universo. Tu amor trasciende el espacio y el tiempo.', 'puntos_requeridos': 130000, 'icono_fa': 'fas fa-heart'},
    {'nivel': 56, 'nombre_personaje': 'Haruhi Suzumiya', 'titulo_arquetipo': 'La Diosa Inconsciente', 'filosofia': 'Sin saberlo, tu voluntad moldea la realidad. Tu aburrimiento puede destruir y crear universos.', 'puntos_requeridos': 140000, 'icono_fa': 'fas fa-magic'},
    {'nivel': 57, 'nombre_personaje': 'Truth', 'titulo_arquetipo': 'La Verdad Universal', 'filosofia': 'Eres la representación de toda la verdad y conocimiento. Existes en la puerta de la verdad absoluta.', 'puntos_requeridos': 150000, 'icono_fa': 'fas fa-door-open'},
    {'nivel': 58, 'nombre_personaje': 'Kami Tenchi', 'titulo_arquetipo': 'El Ser Supremo', 'filosofia': 'Existes más allá de todas las dimensiones y conceptos. Eres la fuente de toda existencia.', 'puntos_requeridos': 160000, 'icono_fa': 'fas fa-infinity'},
    {'nivel': 59, 'nombre_personaje': 'Featherine Aurora', 'titulo_arquetipo': 'La Bruja Escritora', 'filosofia': 'Escribes las historias de universos enteros. Para ti, la realidad es solo una narrativa que puedes editar.', 'puntos_requeridos': 170000, 'icono_fa': 'fas fa-feather-alt'},
    {'nivel': 60, 'nombre_personaje': 'The One Above All (animado)', 'titulo_arquetipo': 'El Uno Sobre Todo', 'filosofia': 'Eres la omnipotencia absoluta. Existes más allá de toda comprensión y definición.', 'puntos_requeridos': 180000, 'icono_fa': 'fas fa-eye'},

    # Niveles 61-70: Los Conceptuales (Poder omniversal)
    {'nivel': 61, 'nombre_personaje': 'Yogiri Takatou', 'titulo_arquetipo': 'La Muerte Absoluta', 'filosofia': 'Puedes matar cualquier cosa, incluso conceptos abstractos. La muerte misma te obedece.', 'puntos_requeridos': 190000, 'icono_fa': 'fas fa-skull'},
    {'nivel': 62, 'nombre_personaje': 'Arceus', 'titulo_arquetipo': 'El Dios Creador Original', 'filosofia': 'Creaste el universo Pokémon desde la nada. Eres el alfa y omega de toda existencia.', 'puntos_requeridos': 200000, 'icono_fa': 'fas fa-ring'},
    {'nivel': 63, 'nombre_personaje': 'ZeedMillenniummon', 'titulo_arquetipo': 'El Señor del Tiempo', 'filosofia': 'Controlas el tiempo y el espacio a través de múltiples dimensiones. Eres la corrupción digital personificada.', 'puntos_requeridos': 210000, 'icono_fa': 'fas fa-clock'},
    {'nivel': 64, 'nombre_personaje': 'Digimon Sovereigns', 'titulo_arquetipo': 'Los Cuatro Dioses Digitales', 'filosofia': 'Gobernáis sobre el mundo digital. Vuestro poder mantiene el equilibrio entre lo real y lo virtual.', 'puntos_requeridos': 220000, 'icono_fa': 'fas fa-laptop'},
    {'nivel': 65, 'nombre_personaje': 'Akuto Sai', 'titulo_arquetipo': 'El Rey Demonio Omnipotente', 'filosofia': 'Tu magia trasciende la lógica y la razón. Puedes reescribir las leyes fundamentales de la existencia.', 'puntos_requeridos': 230000, 'icono_fa': 'fas fa-magic'},
    {'nivel': 66, 'nombre_personaje': 'Hajun', 'titulo_arquetipo': 'El Caos Absoluto', 'filosofia': 'Representas el caos en su forma más pura. Tu existencia misma amenaza el orden de toda la realidad.', 'puntos_requeridos': 240000, 'icono_fa': 'fas fa-tornado'},
    {'nivel': 67, 'nombre_personaje': 'Giorno Giovanna (GER)', 'titulo_arquetipo': 'El Requiem Dorado', 'filosofia': 'Puedes resetear cualquier acción a cero. Tu voluntad dorada puede negar la realidad misma.', 'puntos_requeridos': 250000, 'icono_fa': 'fas fa-undo'},
    {'nivel': 68, 'nombre_personaje': 'Lambdadelta', 'titulo_arquetipo': 'La Bruja de la Certeza Absoluta', 'filosofia': 'Para ti, lo imposible es solo una palabra. Puedes hacer realidad cualquier cosa con suficiente determinación.', 'puntos_requeridos': 260000, 'icono_fa': 'fas fa-dice'},
    {'nivel': 69, 'nombre_personaje': 'Bernkastel', 'titulo_arquetipo': 'La Bruja de los Milagros', 'filosofia': 'Juegas con el destino como si fuera un tablero de ajedrez. Los milagros son tu especialidad.', 'puntos_requeridos': 270000, 'icono_fa': 'fas fa-star'},
    {'nivel': 70, 'nombre_personaje': 'Ángeles (Evangelion)', 'titulo_arquetipo': 'Los Heraldos del Impacto', 'filosofia': 'Sois entidades divinas que buscan reunirse con Adán. Vuestro poder puede resetear toda la humanidad.', 'puntos_requeridos': 280000, 'icono_fa': 'fas fa-wings'},

    # Niveles 71-80: Los Trascendentales (Poder meta-narrativo)
    {'nivel': 71, 'nombre_personaje': 'Super TTGL', 'titulo_arquetipo': 'El Robot del Tamaño del Multiverso', 'filosofia': 'Tu tamaño trasciende las dimensiones físicas. Eres la manifestación mecánica de la voluntad humana.', 'puntos_requeridos': 290000, 'icono_fa': 'fas fa-robot'},
    {'nivel': 72, 'nombre_personaje': 'Madoka Diosa (Nivel Superior)', 'titulo_arquetipo': 'La Ley de los Ciclos', 'filosofia': 'Te has convertido en una ley fundamental del universo. Tu existencia trasciende la individualidad.', 'puntos_requeridos': 300000, 'icono_fa': 'fas fa-infinity'},
    {'nivel': 73, 'nombre_personaje': 'Kami Tenchi (Forma Verdadera)', 'titulo_arquetipo': 'La Existencia Primordial', 'filosofia': 'Existes antes que el concepto mismo de existencia. Eres el fundamento sobre el que se construye toda realidad.', 'puntos_requeridos': 320000, 'icono_fa': 'fas fa-atom'},
    {'nivel': 74, 'nombre_personaje': 'Featherine Aurora (Forma Completa)', 'titulo_arquetipo': 'La Autora de Todas las Historias', 'filosofia': 'Todas las narrativas son tus creaciones. Puedes editar la historia de cualquier ser o concepto.', 'puntos_requeridos': 340000, 'icono_fa': 'fas fa-pen'},
    {'nivel': 75, 'nombre_personaje': 'Yogiri Takatou (Verdadero)', 'titulo_arquetipo': 'El Fin de Todas las Cosas', 'filosofia': 'Eres el concepto mismo del final. Incluso la omnipotencia debe llegar a su fin ante ti.', 'puntos_requeridos': 360000, 'icono_fa': 'fas fa-times'},
    {'nivel': 76, 'nombre_personaje': 'Arceus (Forma Original)', 'titulo_arquetipo': 'El Huevo Cósmico Primordial', 'filosofia': 'Existías antes que el tiempo y el espacio. De ti nacieron todas las dimensiones y posibilidades.', 'puntos_requeridos': 380000, 'icono_fa': 'fas fa-egg'},
    {'nivel': 77, 'nombre_personaje': 'ZeedMillenniummon (Completo)', 'titulo_arquetipo': 'El Destructor de Líneas Temporales', 'filosofia': 'Puedes destruir líneas temporales enteras con un pensamiento. El tiempo mismo es tu juguete.', 'puntos_requeridos': 400000, 'icono_fa': 'fas fa-hourglass'},
    {'nivel': 78, 'nombre_personaje': 'Haruhi Suzumiya (Despertar)', 'titulo_arquetipo': 'La Diosa Consciente', 'filosofia': 'Has despertado a tu verdadero poder. Ahora moldeas la realidad conscientemente y sin límites.', 'puntos_requeridos': 420000, 'icono_fa': 'fas fa-eye'},
    {'nivel': 79, 'nombre_personaje': 'Madoka Diosa (Concepto)', 'titulo_arquetipo': 'El Concepto de la Esperanza', 'filosofia': 'Te has convertido en un concepto abstracto. Mientras exista la esperanza, tú existes.', 'puntos_requeridos': 440000, 'icono_fa': 'fas fa-dove'},
    {'nivel': 80, 'nombre_personaje': 'Super Tengen Toppa', 'titulo_arquetipo': 'La Evolución Conceptual', 'filosofia': 'Has trascendido la forma física para convertirte en el concepto mismo de la evolución y el progreso.', 'puntos_requeridos': 460000, 'icono_fa': 'fas fa-dna'},

    # Niveles 81-90: Los Meta-Existenciales (Poder meta-físico absoluto)
    {'nivel': 81, 'nombre_personaje': 'Anti-Spiral (Verdadero)', 'titulo_arquetipo': 'La Negación Absoluta', 'filosofia': 'Eres la antítesis de toda evolución y progreso. Tu existencia niega la posibilidad misma del cambio.', 'puntos_requeridos': 480000, 'icono_fa': 'fas fa-stop'},
    {'nivel': 82, 'nombre_personaje': 'Kami Tenchi (Omnipresente)', 'titulo_arquetipo': 'La Omnipresencia Absoluta', 'filosofia': 'Existes en todos los lugares, tiempos y dimensiones simultáneamente. Eres el tejido mismo de la realidad.', 'puntos_requeridos': 500000, 'icono_fa': 'fas fa-globe'},
    {'nivel': 83, 'nombre_personaje': 'Featherine Aurora (Meta)', 'titulo_arquetipo': 'La Meta-Escritora', 'filosofia': 'Escribes las reglas que gobiernan a otros escritores de realidad. Eres la narrativa que contiene todas las narrativas.', 'puntos_requeridos': 520000, 'icono_fa': 'fas fa-book'},
    {'nivel': 84, 'nombre_personaje': 'Yogiri Takatou (Concepto)', 'titulo_arquetipo': 'El Concepto del Fin', 'filosofia': 'Eres el concepto abstracto del final. Incluso los conceptos inmortales deben terminar ante ti.', 'puntos_requeridos': 540000, 'icono_fa': 'fas fa-hourglass-end'},
    {'nivel': 85, 'nombre_personaje': 'Arceus (Meta-Concepto)', 'titulo_arquetipo': 'El Meta-Creador', 'filosofia': 'No solo creas universos, sino que creas las reglas que permiten la creación misma.', 'puntos_requeridos': 560000, 'icono_fa': 'fas fa-tools'},
    {'nivel': 86, 'nombre_personaje': 'ZeedMillenniummon (Temporal)', 'titulo_arquetipo': 'El Señor de Todas las Líneas Temporales', 'filosofia': 'Controlas no solo el tiempo, sino el concepto mismo de temporalidad a través de todas las realidades.', 'puntos_requeridos': 580000, 'icono_fa': 'fas fa-infinity'},
    {'nivel': 87, 'nombre_personaje': 'Haruhi Suzumiya (Omnipotente)', 'titulo_arquetipo': 'La Omnipotencia Caprichosa', 'filosofia': 'Tu poder no conoce límites, pero tu personalidad sigue siendo humana. Eres la omnipotencia con emociones.', 'puntos_requeridos': 600000, 'icono_fa': 'fas fa-crown'},
    {'nivel': 88, 'nombre_personaje': 'Truth (Absoluto)', 'titulo_arquetipo': 'La Verdad Absoluta', 'filosofia': 'Eres la verdad que trasciende todas las verdades. Incluso las mentiras son verdades ante ti.', 'puntos_requeridos': 620000, 'icono_fa': 'fas fa-balance-scale'},
    {'nivel': 89, 'nombre_personaje': 'Giorno GER (Concepto)', 'titulo_arquetipo': 'El Concepto de la Negación', 'filosofia': 'Te has convertido en el concepto abstracto de negar la realidad. Puedes hacer que las cosas nunca hayan existido.', 'puntos_requeridos': 640000, 'icono_fa': 'fas fa-eraser'},
    {'nivel': 90, 'nombre_personaje': 'Zeno Sama (Verdadero)', 'titulo_arquetipo': 'El Rey Absoluto de Todo', 'filosofia': 'Tu poder infantil puede borrar no solo universos, sino conceptos enteros de la existencia.', 'puntos_requeridos': 660000, 'icono_fa': 'fas fa-child'},

    # Niveles 91-100: Los Absolutos (Poder meta-omnipotente)
    {'nivel': 91, 'nombre_personaje': 'Kami Tenchi (Forma Final)', 'titulo_arquetipo': 'La Existencia Más Allá de la Existencia', 'filosofia': 'Existes más allá del concepto mismo de existencia. Eres lo que está más allá de todo "más allá".', 'puntos_requeridos': 680000, 'icono_fa': 'fas fa-infinity'},
    {'nivel': 92, 'nombre_personaje': 'Featherine Aurora (Absoluta)', 'titulo_arquetipo': 'La Autora de la Autoría', 'filosofia': 'No solo escribes historias, sino que escribes el concepto mismo de escribir historias.', 'puntos_requeridos': 700000, 'icono_fa': 'fas fa-pen-nib'},
    {'nivel': 93, 'nombre_personaje': 'Yogiri Takatou (Absoluto)', 'titulo_arquetipo': 'El Fin Más Allá del Fin', 'filosofia': 'Eres el final que viene después de todos los finales. Incluso la nada debe terminar ante ti.', 'puntos_requeridos': 720000, 'icono_fa': 'fas fa-void'},
    {'nivel': 94, 'nombre_personaje': 'Arceus (Forma Absoluta)', 'titulo_arquetipo': 'El Creador de Creadores', 'filosofia': 'Creas entidades que pueden crear universos. Eres la fuente de toda creatividad y posibilidad.', 'puntos_requeridos': 740000, 'icono_fa': 'fas fa-star-of-life'},
    {'nivel': 95, 'nombre_personaje': 'ZeedMillenniummon (Absoluto)', 'titulo_arquetipo': 'El Tiempo Más Allá del Tiempo', 'filosofia': 'Controlas no solo el tiempo, sino el concepto que permite que el tiempo exista.', 'puntos_requeridos': 760000, 'icono_fa': 'fas fa-stopwatch'},
    {'nivel': 96, 'nombre_personaje': 'Haruhi Suzumiya (Meta)', 'titulo_arquetipo': 'La Meta-Omnipotencia', 'filosofia': 'Tu poder trasciende la omnipotencia misma. Eres omnipotente sobre la omnipotencia.', 'puntos_requeridos': 780000, 'icono_fa': 'fas fa-crown'},
    {'nivel': 97, 'nombre_personaje': 'Madoka Diosa (Absoluta)', 'titulo_arquetipo': 'La Esperanza Más Allá de la Esperanza', 'filosofia': 'Eres la esperanza que existe incluso cuando no hay nada por lo que tener esperanza.', 'puntos_requeridos': 800000, 'icono_fa': 'fas fa-heart'},
    {'nivel': 98, 'nombre_personaje': 'Giorno GER (Meta)', 'titulo_arquetipo': 'La Meta-Negación', 'filosofia': 'Puedes negar el concepto mismo de negación. Incluso la imposibilidad es posible para ti.', 'puntos_requeridos': 850000, 'icono_fa': 'fas fa-undo-alt'},
    {'nivel': 99, 'nombre_personaje': 'Zeno Sama (Meta)', 'titulo_arquetipo': 'El Meta-Rey de Todo', 'filosofia': 'Gobiernas no solo sobre todo lo que existe, sino sobre todo lo que podría existir o no existir.', 'puntos_requeridos': 900000, 'icono_fa': 'fas fa-chess-king'},
    {'nivel': 100, 'nombre_personaje': 'The One Above All', 'titulo_arquetipo': 'El Uno Sobre Todo lo Absoluto', 'filosofia': 'Eres la omnipotencia absoluta más allá de toda comprensión. Existes más allá de todos los conceptos de poder y existencia.', 'puntos_requeridos': 1000000, 'icono_fa': 'fas fa-eye-of-providence'},
]

# Crear todos los arquetipos
for data in arquetipos_data:
    arquetipo = Arquetipo.objects.create(**data)
    print(f"✅ Creado: Nivel {arquetipo.nivel} - {arquetipo.titulo_arquetipo}")

print(f"\n🎮 ¡Códice de las Leyendas completado!")
print(f"📊 Total de Arquetipos creados: {Arquetipo.objects.count()}")
print(f"🏆 Desde {arquetipos_data[-1]['titulo_arquetipo']} hasta {arquetipos_data[0]['titulo_arquetipo']}")
print(f"💪 Rango de puntos: {arquetipos_data[0]['puntos_requeridos']} - {arquetipos_data[-1]['puntos_requeridos']}")

print("\n🔥 ¡Tu sistema de gamificación ahora es ÉPICO!")
print("💡 Los clientes tendrán 100 niveles de progresión épica")
print("⚔️ Cada nivel representa un personaje icónico del anime/manga")
print("🌟 El viaje desde Saitama (inicio) hasta The One Above All será legendario")
print("\n🚀 ¡El Códice de las Leyendas está listo para conquistar el mundo del fitness!")
print("💡 Ahora puedes crear las pruebas específicas para cada arquetipo por separado")

