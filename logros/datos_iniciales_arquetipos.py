# Script para poblar los datos iniciales del Códice de las Leyendas
# Ejecutar con: python manage.py shell < datos_iniciales_arquetipos.py

from logros.models import Arquetipo, PruebaLegendaria

# Limpiar datos existentes (opcional)
print("Limpiando datos existentes...")
PruebaLegendaria.objects.all().delete()
Arquetipo.objects.all().delete()

# Crear los Arquetipos (Niveles)
print("Creando Arquetipos...")

arquetipos_data = [
    {
        'nivel': 1,
        'nombre_personaje': 'Ippo Makunouchi',
        'titulo_arquetipo': 'El Aspirante Diligente',
        'filosofia': 'Todo poder empieza con el primer paso. Eres pura voluntad y potencial, aprendiendo los fundamentos con cada gota de sudor.',
        'puntos_requeridos': 0,
        'icono_fa': 'fas fa-fist-raised'
    },
    {
        'nivel': 2,
        'nombre_personaje': 'Eren Jaeger',
        'titulo_arquetipo': 'El Guerrero Tenaz',
        'filosofia': 'Has sobrevivido a tus primeras batallas. La disciplina es tu arma y la constancia tu armadura. Aún no eres el más fuerte, pero sí el que nunca se rinde.',
        'puntos_requeridos': 2500,
        'icono_fa': 'fas fa-sword'
    },
    {
        'nivel': 3,
        'nombre_personaje': 'Rock Lee',
        'titulo_arquetipo': 'El Prodigio Desatado',
        'filosofia': 'Tu poder no viene de un don, sino del trabajo duro. Estás empezando a romper tus propios límites, demostrando que el esfuerzo puede superar al talento natural.',
        'puntos_requeridos': 7500,
        'icono_fa': 'fas fa-running'
    },
    {
        'nivel': 4,
        'nombre_personaje': 'Genos',
        'titulo_arquetipo': 'El Héroe de la Clase-A',
        'filosofia': 'Ya no eres un novato. Tu poder es reconocido y tu impacto es medible. Eres una fuerza a tener en cuenta, preciso y destructivo.',
        'puntos_requeridos': 15000,
        'icono_fa': 'fas fa-robot'
    },
    {
        'nivel': 5,
        'nombre_personaje': 'Kyojuro Rengoku',
        'titulo_arquetipo': 'El Pilar de la Determinación',
        'filosofia': 'Tu espíritu arde con una llama que inspira a otros. Has alcanzado un dominio técnico y una fortaleza que te convierten en un pilar para los demás.',
        'puntos_requeridos': 30000,
        'icono_fa': 'fas fa-fire'
    },
    {
        'nivel': 6,
        'nombre_personaje': 'Goku',
        'titulo_arquetipo': 'El Super Saiyan',
        'filosofia': 'Has roto una barrera legendaria. Un evento cataclísmico ha desatado un nuevo nivel de poder. Tu transformación es visible para todos.',
        'puntos_requeridos': 50000,
        'icono_fa': 'fas fa-bolt'
    },
    {
        'nivel': 7,
        'nombre_personaje': 'Edward Elric',
        'titulo_arquetipo': 'El Alquimista de Acero',
        'filosofia': 'Entiendes el principio del intercambio equivalente: para construir un físico de élite, has tenido que sacrificarlo todo. Tu conocimiento y tu físico son uno.',
        'puntos_requeridos': 80000,
        'icono_fa': 'fas fa-atom'
    },
    {
        'nivel': 8,
        'nombre_personaje': 'All Might',
        'titulo_arquetipo': 'El Símbolo de la Paz',
        'filosofia': 'Tu presencia en el gimnasio es una inspiración. Has alcanzado la cima del potencial humano a través de la dedicación absoluta. Eres el estándar de oro.',
        'puntos_requeridos': 120000,
        'icono_fa': 'fas fa-crown'
    },
    {
        'nivel': 9,
        'nombre_personaje': 'Saitama',
        'titulo_arquetipo': 'El Héroe por Diversión',
        'filosofia': 'Has trascendido la necesidad de competir. Entrenas por la pura disciplina y el amor al proceso. Tu poder es tan abrumador que parece sencillo.',
        'puntos_requeridos': 200000,
        'icono_fa': 'fas fa-infinity'
    },
    {
        'nivel': 10,
        'nombre_personaje': 'Gilgamesh',
        'titulo_arquetipo': 'El Rey de los Héroes',
        'filosofia': 'Has acumulado un tesoro de logros y récords que son inalcanzables para la mayoría. No sigues el camino, eres el camino. Tu legado es indiscutible.',
        'puntos_requeridos': 350000,
        'icono_fa': 'fas fa-chess-king'
    }
]

for data in arquetipos_data:
    arquetipo = Arquetipo.objects.create(**data)
    print(f"Creado: {arquetipo}")

print("\nCreando Pruebas Legendarias...")

# Pruebas para el Nivel 1 - Ippo Makunouchi (El Aspirante Diligente)
ippo = Arquetipo.objects.get(nivel=1)
pruebas_ippo = [
    {
        'nombre': 'El Primer Paso',
        'descripcion': 'Completa tu primer entrenamiento. Todo viaje épico comienza con un solo paso.',
        'clave_calculo': 'primer_entrenamiento',
        'meta_valor': 1,
        'puntos_recompensa': 100,
        'es_secreta': False
    },
    {
        'nombre': 'La Sombra del Boxeador',
        'descripcion': 'Mantén una racha de 3 días entrenando consecutivamente.',
        'clave_calculo': 'racha_7_dias',
        'meta_valor': 3,
        'puntos_recompensa': 200,
        'es_secreta': False
    },
    {
        'nombre': 'El Eco del Esfuerzo',
        'descripcion': 'Completa 10 entrenamientos. La constancia es la base de toda grandeza.',
        'clave_calculo': 'cien_entrenos',
        'meta_valor': 10,
        'puntos_recompensa': 300,
        'es_secreta': False
    }
]

for prueba_data in pruebas_ippo:
    prueba = PruebaLegendaria.objects.create(arquetipo=ippo, **prueba_data)
    print(f"Creada: {prueba}")

# Pruebas para el Nivel 2 - Eren Jaeger (El Guerrero Tenaz)
eren = Arquetipo.objects.get(nivel=2)
pruebas_eren = [
    {
        'nombre': 'La Determinación del Titán',
        'descripcion': 'Mantén una racha de 7 días entrenando sin fallar.',
        'clave_calculo': 'racha_7_dias',
        'meta_valor': 7,
        'puntos_recompensa': 400,
        'es_secreta': False
    },
    {
        'nombre': 'El Peso de la Libertad',
        'descripcion': 'Levanta un total acumulado de 42,195 kg (el peso de un maratón).',
        'clave_calculo': 'volumen_maraton',
        'meta_valor': 42195,
        'puntos_recompensa': 500,
        'es_secreta': False
    },
    {
        'nombre': 'Más Allá de las Murallas',
        'descripcion': 'Completa 25 entrenamientos. Has demostrado que puedes ir más allá de tus límites iniciales.',
        'clave_calculo': 'cien_entrenos',
        'meta_valor': 25,
        'puntos_recompensa': 350,
        'es_secreta': False
    }
]

for prueba_data in pruebas_eren:
    prueba = PruebaLegendaria.objects.create(arquetipo=eren, **prueba_data)
    print(f"Creada: {prueba}")

# Pruebas para el Nivel 3 - Rock Lee (El Prodigio Desatado)
lee = Arquetipo.objects.get(nivel=3)
pruebas_lee = [
    {
        'nombre': 'Las Puertas del Poder',
        'descripcion': 'Alcanza un 1RM de 100 kg en Press de Banca.',
        'clave_calculo': 'rm_100kg_banca',
        'meta_valor': 100,
        'puntos_recompensa': 600,
        'es_secreta': False
    },
    {
        'nombre': 'El Huracán de Hojas',
        'descripcion': 'Completa 50 entrenamientos. Tu dedicación es inquebrantable.',
        'clave_calculo': 'cien_entrenos',
        'meta_valor': 50,
        'puntos_recompensa': 500,
        'es_secreta': False
    },
    {
        'nombre': 'La Llama de la Juventud',
        'descripcion': 'Mantén una racha de 14 días consecutivos entrenando.',
        'clave_calculo': 'racha_7_dias',
        'meta_valor': 14,
        'puntos_recompensa': 700,
        'es_secreta': False
    }
]

for prueba_data in pruebas_lee:
    prueba = PruebaLegendaria.objects.create(arquetipo=lee, **prueba_data)
    print(f"Creada: {prueba}")

# Pruebas para el Nivel 4 - Genos (El Héroe de la Clase-A)
genos = Arquetipo.objects.get(nivel=4)
pruebas_genos = [
    {
        'nombre': 'Incineración Completa',
        'descripcion': 'Alcanza un 1RM de 140 kg en Sentadilla.',
        'clave_calculo': 'rm_140kg_sentadilla',
        'meta_valor': 140,
        'puntos_recompensa': 800,
        'es_secreta': False
    },
    {
        'nombre': 'Precisión Mecánica',
        'descripcion': 'Completa 10 entrenamientos perfectos (todas las series completadas).',
        'clave_calculo': 'entrenos_perfectos',
        'meta_valor': 10,
        'puntos_recompensa': 600,
        'es_secreta': False
    },
    {
        'nombre': 'El Arsenal del Cyborg',
        'descripcion': 'Completa 75 entrenamientos. Tu eficiencia es sobrehumana.',
        'clave_calculo': 'cien_entrenos',
        'meta_valor': 75,
        'puntos_recompensa': 700,
        'es_secreta': False
    }
]

for prueba_data in pruebas_genos:
    prueba = PruebaLegendaria.objects.create(arquetipo=genos, **prueba_data)
    print(f"Creada: {prueba}")

# Pruebas para el Nivel 5 - Kyojuro Rengoku (El Pilar de la Determinación)
rengoku = Arquetipo.objects.get(nivel=5)
pruebas_rengoku = [
    {
        'nombre': 'La Llama Eterna',
        'descripcion': 'Mantén una racha de 30 días consecutivos entrenando.',
        'clave_calculo': 'racha_30_dias',
        'meta_valor': 30,
        'puntos_recompensa': 1000,
        'es_secreta': False
    },
    {
        'nombre': 'El Corazón Ardiente',
        'descripcion': 'Alcanza un 1RM de 180 kg en Peso Muerto.',
        'clave_calculo': 'rm_180kg_peso_muerto',
        'meta_valor': 180,
        'puntos_recompensa': 900,
        'es_secreta': False
    },
    {
        'nombre': 'El Pilar Inquebrantable',
        'descripcion': 'Completa 100 entrenamientos. Has demostrado ser un verdadero pilar.',
        'clave_calculo': 'cien_entrenos',
        'meta_valor': 100,
        'puntos_recompensa': 800,
        'es_secreta': False
    }
]

for prueba_data in pruebas_rengoku:
    prueba = PruebaLegendaria.objects.create(arquetipo=rengoku, **prueba_data)
    print(f"Creada: {prueba}")

# Pruebas para el Nivel 6 - Goku (El Super Saiyan)
goku = Arquetipo.objects.get(nivel=6)
pruebas_goku = [
    {
        'nombre': 'El Grito del Saiyan',
        'descripcion': 'Rompe 3 récords personales en una sola semana.',
        'clave_calculo': 'grito_del_saiyan',
        'meta_valor': 3,
        'puntos_recompensa': 1500,
        'es_secreta': False
    },
    {
        'nombre': 'La Transformación Legendaria',
        'descripcion': 'Acumula 100,000 kg de volumen total levantado.',
        'clave_calculo': 'volumen_total_kg',
        'meta_valor': 100000,
        'puntos_recompensa': 1200,
        'es_secreta': False
    },
    {
        'nombre': 'El Poder Sobre 9000',
        'descripcion': 'Alcanza 25,000 kg de volumen en una sola semana.',
        'clave_calculo': 'volumen_semanal_alto',
        'meta_valor': 25000,
        'puntos_recompensa': 1000,
        'es_secreta': False
    }
]

for prueba_data in pruebas_goku:
    prueba = PruebaLegendaria.objects.create(arquetipo=goku, **prueba_data)
    print(f"Creada: {prueba}")

# Pruebas Secretas Épicas para niveles altos
pruebas_secretas = [
    {
        'arquetipo': goku,
        'nombre': 'El Rompedor de Límites',
        'descripcion': 'Falla una serie y en la siguiente sesión supera ese peso.',
        'clave_calculo': 'rompedor_limites',
        'meta_valor': 1,
        'puntos_recompensa': 2000,
        'es_secreta': True
    },
    {
        'arquetipo': rengoku,
        'nombre': 'El Maestro de la Llama Interior',
        'descripcion': 'Completa 20 entrenamientos registrando RPE en la bitácora.',
        'clave_calculo': 'maestro_conexion',
        'meta_valor': 20,
        'puntos_recompensa': 1500,
        'es_secreta': True
    }
]

for prueba_data in pruebas_secretas:
    arquetipo = prueba_data.pop('arquetipo')
    prueba = PruebaLegendaria.objects.create(arquetipo=arquetipo, **prueba_data)
    print(f"Creada (SECRETA): {prueba}")

print(f"\n✅ Datos iniciales creados exitosamente!")
print(f"📊 Arquetipos creados: {Arquetipo.objects.count()}")
print(f"⚔️ Pruebas Legendarias creadas: {PruebaLegendaria.objects.count()}")
print(f"🔮 Pruebas Secretas: {PruebaLegendaria.objects.filter(es_secreta=True).count()}")

print("\n🎮 El Códice de las Leyendas está listo para ser usado!")
print("💡 Recuerda ejecutar las migraciones antes de usar este script:")
print("   python manage.py makemigrations logros")
print("   python manage.py migrate")

