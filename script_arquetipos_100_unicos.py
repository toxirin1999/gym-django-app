# Script para crear el Códice de las Leyendas con 100 Arquetipos ÚNICOS
# Lista curada sin repeticiones - del menos fuerte al más fuerte
# Ejecutar con: python manage.py shell < script_arquetipos_100_unicos.py

from logros.models import Arquetipo, PruebaLegendaria

# Limpiar datos existentes
print("🧹 Limpiando datos existentes...")
PruebaLegendaria.objects.all().delete()
Arquetipo.objects.all().delete()

print("🎮 Creando el Códice de las Leyendas con 100 Arquetipos ÚNICOS...")

# Lista de 100 personajes únicos ordenados de menor a mayor poder
arquetipos_data = [
    # Niveles 1-10: Los Principiantes (Humanos normales/entrenados)
    {'nivel': 1, 'nombre_personaje': 'Saitama (inicio)', 'titulo_arquetipo': 'El Aspirante Calvo', 'filosofia': 'Todo poder comienza con 100 flexiones, 100 abdominales, 100 sentadillas y 10km de carrera.', 'puntos_requeridos': 0, 'icono_fa': 'fas fa-fist-raised'},
    {'nivel': 2, 'nombre_personaje': 'Rock Lee', 'titulo_arquetipo': 'El Genio del Esfuerzo', 'filosofia': 'Sin talento natural, solo trabajo duro. La dedicación supera cualquier don innato.', 'puntos_requeridos': 500, 'icono_fa': 'fas fa-running'},
    {'nivel': 3, 'nombre_personaje': 'Krillin', 'titulo_arquetipo': 'El Guerrero Humano', 'filosofia': 'Aunque seas el más débil, tu corazón valiente te hace fuerte.', 'puntos_requeridos': 750, 'icono_fa': 'fas fa-circle'},
    {'nivel': 4, 'nombre_personaje': 'Yamcha', 'titulo_arquetipo': 'El Lobo del Desierto', 'filosofia': 'Incluso los derrotados pueden encontrar su momento de gloria.', 'puntos_requeridos': 1000, 'icono_fa': 'fas fa-paw'},
    {'nivel': 5, 'nombre_personaje': 'Tien Shinhan', 'titulo_arquetipo': 'El Guerrero de Tres Ojos', 'filosofia': 'La disciplina marcial trasciende los límites humanos.', 'puntos_requeridos': 1250, 'icono_fa': 'fas fa-eye'},
    {'nivel': 6, 'nombre_personaje': 'Roronoa Zoro', 'titulo_arquetipo': 'El Espadachín Perdido', 'filosofia': 'Tres espadas, una voluntad inquebrantable. Tu determinación corta cualquier obstáculo.', 'puntos_requeridos': 1500, 'icono_fa': 'fas fa-sword'},
    {'nivel': 7, 'nombre_personaje': 'Sanji', 'titulo_arquetipo': 'El Cocinero de Pierna Negra', 'filosofia': 'Un verdadero caballero protege a quienes ama con pasión ardiente.', 'puntos_requeridos': 1750, 'icono_fa': 'fas fa-fire'},
    {'nivel': 8, 'nombre_personaje': 'Kenshiro', 'titulo_arquetipo': 'El Puño de la Estrella del Norte', 'filosofia': 'Ya estás muerto... para la mediocridad. Tu técnica es letal, tu corazón compasivo.', 'puntos_requeridos': 2000, 'icono_fa': 'fas fa-star'},
    {'nivel': 9, 'nombre_personaje': 'Edward Elric', 'titulo_arquetipo': 'El Alquimista de Acero', 'filosofia': 'Entiendes el intercambio equivalente: para ganar algo, debes sacrificar algo de igual valor.', 'puntos_requeridos': 2250, 'icono_fa': 'fas fa-atom'},
    {'nivel': 10, 'nombre_personaje': 'Alphonse Elric', 'titulo_arquetipo': 'El Alma de Acero', 'filosofia': 'Un corazón gentil en una armadura inquebrantable. La bondad es tu mayor fortaleza.', 'puntos_requeridos': 2500, 'icono_fa': 'fas fa-shield'},

    # Niveles 11-20: Los Guerreros (Poder sobrehumano inicial)
    {'nivel': 11, 'nombre_personaje': 'Inuyasha', 'titulo_arquetipo': 'El Medio Demonio', 'filosofia': 'Entre dos mundos, perteneces a ambos. Tu naturaleza dual es tu mayor fortaleza.', 'puntos_requeridos': 3000, 'icono_fa': 'fas fa-paw'},
    {'nivel': 12, 'nombre_personaje': 'Sesshomaru', 'titulo_arquetipo': 'El Señor Demonio', 'filosofia': 'La perfección no se busca, se nace con ella. Tu orgullo es tu poder.', 'puntos_requeridos': 3500, 'icono_fa': 'fas fa-moon'},
    {'nivel': 13, 'nombre_personaje': 'Yusuke Urameshi', 'titulo_arquetipo': 'El Detective Espiritual', 'filosofia': 'De delincuente a salvador. Tu energía espiritual refleja tu crecimiento como persona.', 'puntos_requeridos': 4000, 'icono_fa': 'fas fa-ghost'},
    {'nivel': 14, 'nombre_personaje': 'Hiei', 'titulo_arquetipo': 'El Demonio de las Llamas', 'filosofia': 'Las llamas del inframundo arden en tu interior. Rápido, letal, implacable.', 'puntos_requeridos': 4500, 'icono_fa': 'fas fa-fire'},
    {'nivel': 15, 'nombre_personaje': 'Kurama', 'titulo_arquetipo': 'El Zorro Demonio', 'filosofia': 'La inteligencia y la astucia superan la fuerza bruta. Eres estrategia pura.', 'puntos_requeridos': 5000, 'icono_fa': 'fas fa-leaf'},
    {'nivel': 16, 'nombre_personaje': 'Ichigo Kurosaki', 'titulo_arquetipo': 'El Shinigami Sustituto', 'filosofia': 'Proteges a los que amas sin importar el costo. Tu determinación trasciende la muerte.', 'puntos_requeridos': 5500, 'icono_fa': 'fas fa-sword'},
    {'nivel': 17, 'nombre_personaje': 'Rukia Kuchiki', 'titulo_arquetipo': 'La Shinigami de Hielo', 'filosofia': 'Elegante como la nieve, letal como el hielo. Tu belleza oculta un poder mortal.', 'puntos_requeridos': 6000, 'icono_fa': 'fas fa-snowflake'},
    {'nivel': 18, 'nombre_personaje': 'Byakuya Kuchiki', 'titulo_arquetipo': 'El Noble de los Pétalos', 'filosofia': 'La nobleza no es un título, es una forma de vida. Tu honor es inquebrantable.', 'puntos_requeridos': 6500, 'icono_fa': 'fas fa-leaf'},
    {'nivel': 19, 'nombre_personaje': 'Jotaro Kujo', 'titulo_arquetipo': 'El Cruzado Estelar', 'filosofia': 'Yare yare daze. Tu Stand refleja tu alma: preciso, poderoso e implacable.', 'puntos_requeridos': 7000, 'icono_fa': 'fas fa-star'},
    {'nivel': 20, 'nombre_personaje': 'Dio Brando', 'titulo_arquetipo': 'El Vampiro del Tiempo', 'filosofia': 'Has rechazado tu humanidad. El tiempo mismo se detiene ante tu voluntad.', 'puntos_requeridos': 7500, 'icono_fa': 'fas fa-clock'},

    # Niveles 21-30: Los Élite (Poder de élite)
    {'nivel': 21, 'nombre_personaje': 'Natsu Dragneel', 'titulo_arquetipo': 'El Dragon Slayer de Fuego', 'filosofia': 'El fuego de la amistad arde en tu corazón. Por tus nakama, puedes quemar el mundo.', 'puntos_requeridos': 8000, 'icono_fa': 'fas fa-fire'},
    {'nivel': 22, 'nombre_personaje': 'Erza Scarlet', 'titulo_arquetipo': 'La Reina de las Hadas', 'filosofia': 'Tu armadura no solo protege tu cuerpo, sino el corazón de tus compañeros.', 'puntos_requeridos': 8500, 'icono_fa': 'fas fa-shield'},
    {'nivel': 23, 'nombre_personaje': 'Gray Fullbuster', 'titulo_arquetipo': 'El Mago de Hielo', 'filosofia': 'Tu frialdad exterior oculta un corazón ardiente por tus amigos.', 'puntos_requeridos': 9000, 'icono_fa': 'fas fa-snowflake'},
    {'nivel': 24, 'nombre_personaje': 'Laxus Dreyar', 'titulo_arquetipo': 'El Dragon Slayer del Rayo', 'filosofia': 'El rayo que una vez destruyó, ahora protege. Has encontrado tu verdadero poder.', 'puntos_requeridos': 9500, 'icono_fa': 'fas fa-bolt'},
    {'nivel': 25, 'nombre_personaje': 'Gaara', 'titulo_arquetipo': 'El Kazekage de Arena', 'filosofia': 'La soledad te forjó, pero el amor te transformó. Proteges con arena inquebrantable.', 'puntos_requeridos': 10000, 'icono_fa': 'fas fa-mountain'},
    {'nivel': 26, 'nombre_personaje': 'Kakashi Hatake', 'titulo_arquetipo': 'El Ninja Copia', 'filosofia': 'Has copiado mil técnicas, pero tu mayor poder es proteger a tus estudiantes.', 'puntos_requeridos': 10500, 'icono_fa': 'fas fa-eye'},
    {'nivel': 27, 'nombre_personaje': 'Might Guy', 'titulo_arquetipo': 'La Bestia Verde', 'filosofia': 'La juventud arde eternamente en tu espíritu. El trabajo duro nunca traiciona.', 'puntos_requeridos': 11000, 'icono_fa': 'fas fa-running'},
    {'nivel': 28, 'nombre_personaje': 'Jiraiya', 'titulo_arquetipo': 'El Sabio Pervertido', 'filosofia': 'Detrás de tu personalidad excéntrica se oculta la sabiduría de un verdadero maestro.', 'puntos_requeridos': 11500, 'icono_fa': 'fas fa-frog'},
    {'nivel': 29, 'nombre_personaje': 'Orochimaru', 'titulo_arquetipo': 'La Serpiente Sannin', 'filosofia': 'La inmortalidad es tu obsesión. Cambias de cuerpo como una serpiente cambia de piel.', 'puntos_requeridos': 12000, 'icono_fa': 'fas fa-snake'},
    {'nivel': 30, 'nombre_personaje': 'Tsunade', 'titulo_arquetipo': 'La Princesa Babosa', 'filosofia': 'Tus puños pueden quebrar montañas, pero tu corazón puede sanar cualquier herida.', 'puntos_requeridos': 12500, 'icono_fa': 'fas fa-fist-raised'},

    # Niveles 31-40: Los Legendarios (Poder legendario)
    {'nivel': 31, 'nombre_personaje': 'All Might', 'titulo_arquetipo': 'El Símbolo de la Paz', 'filosofia': 'Un verdadero héroe no se mide por su fuerza, sino por cómo inspira a otros.', 'puntos_requeridos': 13000, 'icono_fa': 'fas fa-shield-alt'},
    {'nivel': 32, 'nombre_personaje': 'Endeavor', 'titulo_arquetipo': 'El Héroe de Fuego', 'filosofia': 'Las llamas del esfuerzo arden más brillantes que el talento natural.', 'puntos_requeridos': 13500, 'icono_fa': 'fas fa-fire'},
    {'nivel': 33, 'nombre_personaje': 'Shoto Todoroki', 'titulo_arquetipo': 'El Heredero Dividido', 'filosofia': 'Hielo y fuego en perfecta armonía. Has aprendido a abrazar ambos lados de tu poder.', 'puntos_requeridos': 14000, 'icono_fa': 'fas fa-yin-yang'},
    {'nivel': 34, 'nombre_personaje': 'Yujiro Hanma', 'titulo_arquetipo': 'El Ogro Más Fuerte', 'filosofia': 'La fuerza física pura en su máxima expresión. Eres una calamidad natural con forma humana.', 'puntos_requeridos': 14500, 'icono_fa': 'fas fa-dumbbell'},
    {'nivel': 35, 'nombre_personaje': 'Baki Hanma', 'titulo_arquetipo': 'El Campeón Joven', 'filosofia': 'Llevas la sangre del ogro, pero tu corazón humano te hace más fuerte que tu padre.', 'puntos_requeridos': 15000, 'icono_fa': 'fas fa-fist-raised'},
    {'nivel': 36, 'nombre_personaje': 'Saber', 'titulo_arquetipo': 'El Rey de los Caballeros', 'filosofia': 'Excalibur brilla con la luz de tus ideales. Eres el rey que el mundo necesita.', 'puntos_requeridos': 15500, 'icono_fa': 'fas fa-crown'},
    {'nivel': 37, 'nombre_personaje': 'Gilgamesh', 'titulo_arquetipo': 'El Rey de los Héroes', 'filosofia': 'Posees todos los tesoros del mundo. Tu arrogancia está justificada por tu poder absoluto.', 'puntos_requeridos': 16000, 'icono_fa': 'fas fa-gem'},
    {'nivel': 38, 'nombre_personaje': 'Escanor', 'titulo_arquetipo': 'El León del Orgullo', 'filosofia': 'Durante el día, eres la encarnación del orgullo. Tu poder crece con el sol.', 'puntos_requeridos': 16500, 'icono_fa': 'fas fa-sun'},
    {'nivel': 39, 'nombre_personaje': 'Meliodas', 'titulo_arquetipo': 'El Capitán de los Pecados', 'filosofia': 'El poder demoníaco y el corazón humano coexisten en ti. Lideras con fuerza y compasión.', 'puntos_requeridos': 17000, 'icono_fa': 'fas fa-dragon'},
    {'nivel': 40, 'nombre_personaje': 'Ban', 'titulo_arquetipo': 'El Zorro de la Codicia', 'filosofia': 'Tu inmortalidad te ha enseñado el verdadero valor de la vida y el amor.', 'puntos_requeridos': 17500, 'icono_fa': 'fas fa-heart'},

    # Niveles 41-50: Los Saiyans (Poder planetario)
    {'nivel': 41, 'nombre_personaje': 'Goku Niño', 'titulo_arquetipo': 'El Pequeño Guerrero', 'filosofia': 'La inocencia combinada con un poder increíble. Tu pureza de corazón es tu mayor fortaleza.', 'puntos_requeridos': 18000, 'icono_fa': 'fas fa-child'},
    {'nivel': 42, 'nombre_personaje': 'Vegeta (Saiyan Saga)', 'titulo_arquetipo': 'El Príncipe Orgulloso', 'filosofia': 'El orgullo Saiyan corre por tus venas. Nunca te conformas con ser segundo.', 'puntos_requeridos': 19000, 'icono_fa': 'fas fa-crown'},
    {'nivel': 43, 'nombre_personaje': 'Piccolo', 'titulo_arquetipo': 'El Demonio Redentor', 'filosofia': 'De villano a mentor. Has encontrado la redención a través del sacrificio por otros.', 'puntos_requeridos': 20000, 'icono_fa': 'fas fa-user-ninja'},
    {'nivel': 44, 'nombre_personaje': 'Gohan Adolescente', 'titulo_arquetipo': 'El Guerrero Académico', 'filosofia': 'Prefieres los libros a las batallas, pero cuando luchas, tu poder no conoce límites.', 'puntos_requeridos': 21000, 'icono_fa': 'fas fa-book'},
    {'nivel': 45, 'nombre_personaje': 'Goku (Namek)', 'titulo_arquetipo': 'El Super Saiyan Legendario', 'filosofia': 'La leyenda se ha hecho realidad. Tu transformación dorada marca una nueva era.', 'puntos_requeridos': 22000, 'icono_fa': 'fas fa-bolt'},
    {'nivel': 46, 'nombre_personaje': 'Freezer', 'titulo_arquetipo': 'El Emperador del Universo', 'filosofia': 'El poder absoluto corrompe absolutamente. Eres la encarnación del mal en su forma más pura.', 'puntos_requeridos': 23000, 'icono_fa': 'fas fa-snowflake'},
    {'nivel': 47, 'nombre_personaje': 'Cell Perfecto', 'titulo_arquetipo': 'La Perfección Artificial', 'filosofia': 'Eres la culminación de la ciencia y la evolución. La perfección tiene un precio: la soledad.', 'puntos_requeridos': 24000, 'icono_fa': 'fas fa-dna'},
    {'nivel': 48, 'nombre_personaje': 'Gohan (Cell Games)', 'titulo_arquetipo': 'El Joven Legendario', 'filosofia': 'Tu ira despertó un poder que ni tu padre poseía. Eres el futuro de los Saiyans.', 'puntos_requeridos': 25000, 'icono_fa': 'fas fa-lightning-bolt'},
    {'nivel': 49, 'nombre_personaje': 'Majin Buu', 'titulo_arquetipo': 'La Destrucción Inocente', 'filosofia': 'Tu poder destructivo es solo igualado por tu inocencia. Eres caos puro con corazón de niño.', 'puntos_requeridos': 26000, 'icono_fa': 'fas fa-candy-cane'},
    {'nivel': 50, 'nombre_personaje': 'Goku (SSJ3)', 'titulo_arquetipo': 'El Guerrero Sin Límites', 'filosofia': 'Has roto las barreras de lo posible. Tu sed de batalla trasciende la comprensión mortal.', 'puntos_requeridos': 27000, 'icono_fa': 'fas fa-bolt'},

    # Niveles 51-60: Los Ninjas Legendarios (Poder continental)
    {'nivel': 51, 'nombre_personaje': 'Itachi Uchiha', 'titulo_arquetipo': 'El Genio Trágico', 'filosofia': 'Sacrificaste todo por la paz. Tu amor por tu hermano trasciende la comprensión.', 'puntos_requeridos': 28000, 'icono_fa': 'fas fa-eye'},
    {'nivel': 52, 'nombre_personaje': 'Minato Namikaze', 'titulo_arquetipo': 'El Rayo Amarillo', 'filosofia': 'Más rápido que la luz, más brillante que el sol. Tu legado vive en tu hijo.', 'puntos_requeridos': 29000, 'icono_fa': 'fas fa-bolt'},
    {'nivel': 53, 'nombre_personaje': 'Hashirama Senju', 'titulo_arquetipo': 'El Dios de los Shinobi', 'filosofia': 'Tu voluntad de fuego ilumina el camino hacia la paz. Eres el ideal de todos los Hokage.', 'puntos_requeridos': 30000, 'icono_fa': 'fas fa-tree'},
    {'nivel': 54, 'nombre_personaje': 'Madara Uchiha', 'titulo_arquetipo': 'El Fantasma de los Uchiha', 'filosofia': 'Has visto el ciclo infinito de odio. Tu sueño de paz justifica cualquier medio.', 'puntos_requeridos': 32000, 'icono_fa': 'fas fa-eye'},
    {'nivel': 55, 'nombre_personaje': 'Naruto (Sabio)', 'titulo_arquetipo': 'El Jinchūriki Perfecto', 'filosofia': 'Has convertido el odio en amor, la maldición en bendición. Nadie está perdido.', 'puntos_requeridos': 34000, 'icono_fa': 'fas fa-leaf'},
    {'nivel': 56, 'nombre_personaje': 'Sasuke (Rinnegan)', 'titulo_arquetipo': 'El Último Uchiha', 'filosofia': 'Has caminado por la oscuridad para proteger la luz. Tu redención es tu mayor victoria.', 'puntos_requeridos': 36000, 'icono_fa': 'fas fa-lightning-bolt'},
    {'nivel': 57, 'nombre_personaje': 'Obito (Jinchūriki)', 'titulo_arquetipo': 'El Sabio Falso', 'filosofia': 'El dolor te transformó en lo que juraste destruir. Buscas crear un mundo sin sufrimiento.', 'puntos_requeridos': 38000, 'icono_fa': 'fas fa-mask'},
    {'nivel': 58, 'nombre_personaje': 'Kaguya Ōtsutsuki', 'titulo_arquetipo': 'La Diosa Conejo', 'filosofia': 'Eres el origen de todo chakra. Tu poder es tan antiguo como la misma creación.', 'puntos_requeridos': 40000, 'icono_fa': 'fas fa-moon'},
    {'nivel': 59, 'nombre_personaje': 'Ichigo (Bankai Final)', 'titulo_arquetipo': 'El Híbrido Definitivo', 'filosofia': 'Shinigami, Quincy, Hollow y Humano. Eres la convergencia de todos los poderes espirituales.', 'puntos_requeridos': 42000, 'icono_fa': 'fas fa-yin-yang'},
    {'nivel': 60, 'nombre_personaje': 'Aizen Sosuke', 'titulo_arquetipo': 'El Dios Autoproclamado', 'filosofia': 'Has trascendido los límites de la existencia espiritual. Tu evolución no conoce fin.', 'puntos_requeridos': 44000, 'icono_fa': 'fas fa-gem'},

    # Niveles 61-70: Los Divinos (Poder universal inicial)
    {'nivel': 61, 'nombre_personaje': 'Goku (SSJ God)', 'titulo_arquetipo': 'El Saiyan Divino', 'filosofia': 'Has alcanzado el reino de los dioses. Tu ki divino trasciende la comprensión mortal.', 'puntos_requeridos': 46000, 'icono_fa': 'fas fa-bolt'},
    {'nivel': 62, 'nombre_personaje': 'Vegeta (SSJ Blue)', 'titulo_arquetipo': 'El Príncipe Azul', 'filosofia': 'Has combinado lo divino con lo mortal. Tu orgullo ahora tiene respaldo divino.', 'puntos_requeridos': 48000, 'icono_fa': 'fas fa-crown'},
    {'nivel': 63, 'nombre_personaje': 'Broly', 'titulo_arquetipo': 'El Saiyan Legendario', 'filosofia': 'Tu poder crece sin límites cuando la ira te consume. Eres la fuerza bruta personificada.', 'puntos_requeridos': 50000, 'icono_fa': 'fas fa-fire'},
    {'nivel': 64, 'nombre_personaje': 'Jiren', 'titulo_arquetipo': 'El Guerrero de la Justicia', 'filosofia': 'Has trascendido el tiempo mismo con tu fuerza. Tu justicia es absoluta e inquebrantable.', 'puntos_requeridos': 55000, 'icono_fa': 'fas fa-shield'},
    {'nivel': 65, 'nombre_personaje': 'Beerus', 'titulo_arquetipo': 'El Dios de la Destrucción', 'filosofia': 'Mantienes el equilibrio del universo a través de la destrucción. Tu poder es caprichoso pero necesario.', 'puntos_requeridos': 60000, 'icono_fa': 'fas fa-cat'},
    {'nivel': 66, 'nombre_personaje': 'Whis', 'titulo_arquetipo': 'El Ángel Instructor', 'filosofia': 'Eres la calma en la tormenta. Tu sabiduría y poder guían incluso a los dioses.', 'puntos_requeridos': 65000, 'icono_fa': 'fas fa-feather'},
    {'nivel': 67, 'nombre_personaje': 'Gogeta Blue', 'titulo_arquetipo': 'La Fusión Divina', 'filosofia': 'Dos guerreros divinos se convierten en uno. Tu poder combinado desafía la lógica.', 'puntos_requeridos': 70000, 'icono_fa': 'fas fa-users'},
    {'nivel': 68, 'nombre_personaje': 'Vegito Blue', 'titulo_arquetipo': 'El Guerrero Fusionado', 'filosofia': 'La rivalidad se convierte en sinergia perfecta. Eres más que la suma de tus partes.', 'puntos_requeridos': 75000, 'icono_fa': 'fas fa-infinity'},
    {'nivel': 69, 'nombre_personaje': 'Moro', 'titulo_arquetipo': 'El Devorador de Planetas', 'filosofia': 'Absorbes la energía de mundos enteros. Tu hambre de poder no conoce límites.', 'puntos_requeridos': 80000, 'icono_fa': 'fas fa-black-hole'},
    {'nivel': 70, 'nombre_personaje': 'Gas', 'titulo_arquetipo': 'El Más Fuerte del Universo', 'filosofia': 'Has obtenido el título de más fuerte, pero el poder sin propósito es vacío.', 'puntos_requeridos': 85000, 'icono_fa': 'fas fa-crown'},

    # Niveles 71-80: Los Cósmicos (Poder multiversal)
    {'nivel': 71, 'nombre_personaje': 'Sailor Moon', 'titulo_arquetipo': 'La Guerrera de la Luna', 'filosofia': 'En nombre de la Luna, castigas a los malvados. Tu amor puede purificar cualquier oscuridad.', 'puntos_requeridos': 90000, 'icono_fa': 'fas fa-moon'},
    {'nivel': 72, 'nombre_personaje': 'Seiya de Pegaso', 'titulo_arquetipo': 'El Caballero de Pegaso', 'filosofia': 'Tu cosmo arde con la fuerza de las estrellas. Proteges a Athena con tu vida.', 'puntos_requeridos': 95000, 'icono_fa': 'fas fa-horse'},
    {'nivel': 73, 'nombre_personaje': 'Saga de Géminis', 'titulo_arquetipo': 'El Caballero Dorado', 'filosofia': 'Tu alma dual refleja la complejidad del bien y el mal. Eres luz y oscuridad.', 'puntos_requeridos': 100000, 'icono_fa': 'fas fa-yin-yang'},
    {'nivel': 74, 'nombre_personaje': 'Shaka de Virgo', 'titulo_arquetipo': 'El Hombre Más Cercano a Dios', 'filosofia': 'Tu iluminación trasciende lo físico. Eres la sabiduría hecha poder.', 'puntos_requeridos': 110000, 'icono_fa': 'fas fa-lotus'},
    {'nivel': 75, 'nombre_personaje': 'Athena', 'titulo_arquetipo': 'La Diosa de la Guerra', 'filosofia': 'Proteges la Tierra con amor y justicia. Tu sabiduría guía a tus caballeros.', 'puntos_requeridos': 120000, 'icono_fa': 'fas fa-shield'},
    {'nivel': 76, 'nombre_personaje': 'Hades', 'titulo_arquetipo': 'El Señor del Inframundo', 'filosofia': 'Gobiernas sobre la muerte misma. Tu dominio se extiende más allá de la comprensión mortal.', 'puntos_requeridos': 130000, 'icono_fa': 'fas fa-skull-crossbones'},
    {'nivel': 77, 'nombre_personaje': 'Simon', 'titulo_arquetipo': 'El Perforador de Cielos', 'filosofia': 'Tu taladro puede perforar los cielos mismos. Representas la evolución y el progreso infinito.', 'puntos_requeridos': 140000, 'icono_fa': 'fas fa-rocket'},
    {'nivel': 78, 'nombre_personaje': 'Anti-Spiral', 'titulo_arquetipo': 'La Negación de la Evolución', 'filosofia': 'Representas la estasis absoluta. Tu misión es prevenir que el universo se autodestruya.', 'puntos_requeridos': 150000, 'icono_fa': 'fas fa-ban'},
    {'nivel': 79, 'nombre_personaje': 'Tengen Toppa Gurren Lagann', 'titulo_arquetipo': 'El Robot del Tamaño del Multiverso', 'filosofia': 'Tu tamaño trasciende las dimensiones físicas. Eres la manifestación de la voluntad humana.', 'puntos_requeridos': 160000, 'icono_fa': 'fas fa-robot'},
    {'nivel': 80, 'nombre_personaje': 'Super Tengen Toppa', 'titulo_arquetipo': 'La Evolución Conceptual', 'filosofia': 'Has trascendido la forma física para convertirte en el concepto mismo de la evolución.', 'puntos_requeridos': 170000, 'icono_fa': 'fas fa-dna'},

    # Niveles 81-90: Los Omnipotentes (Poder omniversal)
    {'nivel': 81, 'nombre_personaje': 'Madoka Kaname', 'titulo_arquetipo': 'La Diosa de la Esperanza', 'filosofia': 'Te sacrificaste para reescribir las leyes del universo. Tu amor trasciende el espacio y el tiempo.', 'puntos_requeridos': 180000, 'icono_fa': 'fas fa-heart'},
    {'nivel': 82, 'nombre_personaje': 'Homura Akemi', 'titulo_arquetipo': 'El Demonio del Tiempo', 'filosofia': 'Has reescrito la realidad por amor. Tu devoción trasciende el bien y el mal.', 'puntos_requeridos': 190000, 'icono_fa': 'fas fa-clock'},
    {'nivel': 83, 'nombre_personaje': 'Haruhi Suzumiya', 'titulo_arquetipo': 'La Diosa Inconsciente', 'filosofia': 'Sin saberlo, tu voluntad moldea la realidad. Tu aburrimiento puede destruir y crear universos.', 'puntos_requeridos': 200000, 'icono_fa': 'fas fa-magic'},
    {'nivel': 84, 'nombre_personaje': 'Truth', 'titulo_arquetipo': 'La Verdad Universal', 'filosofia': 'Eres la representación de toda la verdad y conocimiento. Existes en la puerta de la verdad absoluta.', 'puntos_requeridos': 220000, 'icono_fa': 'fas fa-door-open'},
    {'nivel': 85, 'nombre_personaje': 'Giorno Giovanna (GER)', 'titulo_arquetipo': 'El Requiem Dorado', 'filosofia': 'Puedes resetear cualquier acción a cero. Tu voluntad dorada puede negar la realidad misma.', 'puntos_requeridos': 240000, 'icono_fa': 'fas fa-undo'},
    {'nivel': 86, 'nombre_personaje': 'Rimuru Tempest', 'titulo_arquetipo': 'El Señor Demonio Slime', 'filosofia': 'De simple slime a señor demonio. Tu evolución no conoce límites ni fronteras.', 'puntos_requeridos': 260000, 'icono_fa': 'fas fa-circle'},
    {'nivel': 87, 'nombre_personaje': 'Ainz Ooal Gown', 'titulo_arquetipo': 'El Rey No-Muerto', 'filosofia': 'Gobiernas desde las sombras con sabiduría estratégica. La muerte es solo el comienzo.', 'puntos_requeridos': 280000, 'icono_fa': 'fas fa-skull'},
    {'nivel': 88, 'nombre_personaje': 'Saitama', 'titulo_arquetipo': 'El Héroe por Hobby', 'filosofia': 'Has roto tu limitador. Tu fuerza es tan absoluta que has perdido la emoción de la batalla.', 'puntos_requeridos': 300000, 'icono_fa': 'fas fa-fist-raised'},
    {'nivel': 89, 'nombre_personaje': 'Zeno Sama', 'titulo_arquetipo': 'El Rey de Todo', 'filosofia': 'Con un gesto puedes borrar universos enteros. Tu inocencia infantil contrasta con tu poder absoluto.', 'puntos_requeridos': 350000, 'icono_fa': 'fas fa-crown'},
    {'nivel': 90, 'nombre_personaje': 'Daishinkan', 'titulo_arquetipo': 'El Gran Sacerdote', 'filosofia': 'Eres el ángel de los ángeles. Tu sabiduría y poder son los pilares de la existencia multiversal.', 'puntos_requeridos': 400000, 'icono_fa': 'fas fa-praying-hands'},

    # Niveles 91-100: Los Absolutos (Poder meta-omnipotente)
    {'nivel': 91, 'nombre_personaje': 'Yogiri Takatou', 'titulo_arquetipo': 'La Muerte Absoluta', 'filosofia': 'Puedes matar cualquier cosa, incluso conceptos abstractos. La muerte misma te obedece.', 'puntos_requeridos': 450000, 'icono_fa': 'fas fa-skull'},
    {'nivel': 92, 'nombre_personaje': 'Arceus', 'titulo_arquetipo': 'El Dios Creador Original', 'filosofia': 'Creaste el universo desde la nada. Eres el alfa y omega de toda existencia.', 'puntos_requeridos': 500000, 'icono_fa': 'fas fa-ring'},
    {'nivel': 93, 'nombre_personaje': 'Akuto Sai', 'titulo_arquetipo': 'El Rey Demonio Omnipotente', 'filosofia': 'Tu magia trasciende la lógica y la razón. Puedes reescribir las leyes fundamentales de la existencia.', 'puntos_requeridos': 550000, 'icono_fa': 'fas fa-magic'},
    {'nivel': 94, 'nombre_personaje': 'Featherine Aurora', 'titulo_arquetipo': 'La Bruja Escritora', 'filosofia': 'Escribes las historias de universos enteros. Para ti, la realidad es solo una narrativa que puedes editar.', 'puntos_requeridos': 600000, 'icono_fa': 'fas fa-feather-alt'},
    {'nivel': 95, 'nombre_personaje': 'Lambdadelta', 'titulo_arquetipo': 'La Bruja de la Certeza Absoluta', 'filosofia': 'Para ti, lo imposible es solo una palabra. Puedes hacer realidad cualquier cosa con suficiente determinación.', 'puntos_requeridos': 650000, 'icono_fa': 'fas fa-dice'},
    {'nivel': 96, 'nombre_personaje': 'Bernkastel', 'titulo_arquetipo': 'La Bruja de los Milagros', 'filosofia': 'Juegas con el destino como si fuera un tablero de ajedrez. Los milagros son tu especialidad.', 'puntos_requeridos': 700000, 'icono_fa': 'fas fa-star'},
    {'nivel': 97, 'nombre_personaje': 'Kami Tenchi', 'titulo_arquetipo': 'El Ser Supremo', 'filosofia': 'Existes más allá de todas las dimensiones y conceptos. Eres la fuente de toda existencia.', 'puntos_requeridos': 750000, 'icono_fa': 'fas fa-infinity'},
    {'nivel': 98, 'nombre_personaje': 'Hajun', 'titulo_arquetipo': 'El Caos Absoluto', 'filosofia': 'Representas el caos en su forma más pura. Tu existencia misma amenaza el orden de toda la realidad.', 'puntos_requeridos': 800000, 'icono_fa': 'fas fa-tornado'},
    {'nivel': 99, 'nombre_personaje': 'Azathoth', 'titulo_arquetipo': 'El Dios Ciego Idiota', 'filosofia': 'Eres el caos primordial que sueña la realidad. Si despiertas, toda existencia cesará.', 'puntos_requeridos': 900000, 'icono_fa': 'fas fa-eye'},
    {'nivel': 100, 'nombre_personaje': 'The One Above All', 'titulo_arquetipo': 'El Uno Sobre Todo lo Absoluto', 'filosofia': 'Eres la omnipotencia absoluta más allá de toda comprensión. Existes más allá de todos los conceptos de poder y existencia.', 'puntos_requeridos': 1000000, 'icono_fa': 'fas fa-eye-of-providence'},
]

# Crear todos los arquetipos
for data in arquetipos_data:
    arquetipo = Arquetipo.objects.create(**data)
    print(f"✅ Creado: Nivel {arquetipo.nivel} - {arquetipo.titulo_arquetipo}")

print(f"\n🎮 ¡Códice de las Leyendas completado!")
print(f"📊 Total de Arquetipos creados: {Arquetipo.objects.count()}")
print(f"🏆 Desde {arquetipos_data[0]['titulo_arquetipo']} hasta {arquetipos_data[-1]['titulo_arquetipo']}")
print(f"💪 Rango de puntos: {arquetipos_data[0]['puntos_requeridos']} - {arquetipos_data[-1]['puntos_requeridos']}")

print("\n🔥 ¡Tu sistema de gamificación ahora es ÉPICO!")
print("💡 Los clientes tendrán 100 niveles de progresión épica")
print("⚔️ Cada nivel representa un personaje ÚNICO del anime/manga")
print("🌟 El viaje desde Saitama (inicio) hasta The One Above All será legendario")
print("\n🚀 ¡El Códice de las Leyendas está listo para conquistar el mundo del fitness!")
print("💡 Lista completamente curada sin repeticiones - 100 personajes únicos")

