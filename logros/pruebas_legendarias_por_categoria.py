# Script para crear Pruebas Legendarias específicas por categorías de poder
# Ejecutar DESPUÉS del script principal de arquetipos
# python manage.py shell < pruebas_legendarias_por_categoria.py

from logros.models import Arquetipo, PruebaLegendaria

print("⚔️ Creando Pruebas Legendarias específicas por categorías...")

# =============================================================================
# CATEGORÍA 1: LOS ASPIRANTES (Niveles 1-10) - Pruebas de Fundamentos
# =============================================================================

print("\n🥊 Creando pruebas para LOS ASPIRANTES (Niveles 1-10)...")

# Nivel 1: Saitama (inicio)
saitama = Arquetipo.objects.get(nivel=1)
pruebas_saitama = [
    {'nombre': 'El Primer Puñetazo', 'descripcion': 'Completa tu primer entrenamiento. Todo héroe comienza aquí.', 'clave_calculo': 'primer_entrenamiento', 'meta_valor': 1, 'puntos_recompensa': 50, 'es_secreta': False},
    {'nombre': '100 Flexiones', 'descripcion': 'Realiza 100 flexiones acumuladas en total.', 'clave_calculo': 'flexiones_totales', 'meta_valor': 100, 'puntos_recompensa': 100, 'es_secreta': False},
    {'nombre': 'La Rutina Diaria', 'descripcion': 'Entrena 3 días consecutivos.', 'clave_calculo': 'racha_7_dias', 'meta_valor': 3, 'puntos_recompensa': 150, 'es_secreta': False},
]

# Nivel 2: Rock Lee
lee = Arquetipo.objects.get(nivel=2)
pruebas_lee = [
    {'nombre': 'Las Puertas del Esfuerzo', 'descripcion': 'Mantén una racha de 7 días entrenando.', 'clave_calculo': 'racha_7_dias', 'meta_valor': 7, 'puntos_recompensa': 200, 'es_secreta': False},
    {'nombre': 'La Llama de la Juventud', 'descripcion': 'Completa 15 entrenamientos.', 'clave_calculo': 'cien_entrenos', 'meta_valor': 15, 'puntos_recompensa': 250, 'es_secreta': False},
    {'nombre': 'Entrenamiento de Pesas', 'descripcion': 'Levanta un total de 5,000 kg acumulados.', 'clave_calculo': 'volumen_total_kg', 'meta_valor': 5000, 'puntos_recompensa': 300, 'es_secreta': False},
]

# Nivel 3: Roronoa Zoro
zoro = Arquetipo.objects.get(nivel=3)
pruebas_zoro = [
    {'nombre': 'Las Tres Espadas', 'descripcion': 'Domina 3 ejercicios diferentes (completa al menos 5 series de cada).', 'clave_calculo': 'ejercicios_dominados', 'meta_valor': 3, 'puntos_recompensa': 300, 'es_secreta': False},
    {'nombre': 'El Camino del Espadachín', 'descripcion': 'Levanta un total de 10,000 kg.', 'clave_calculo': 'volumen_total_kg', 'meta_valor': 10000, 'puntos_recompensa': 350, 'es_secreta': False},
    {'nombre': 'Perdido pero Determinado', 'descripcion': 'Completa 20 entrenamientos.', 'clave_calculo': 'cien_entrenos', 'meta_valor': 20, 'puntos_recompensa': 400, 'es_secreta': False},
]

# Nivel 4: Kenshiro
kenshiro = Arquetipo.objects.get(nivel=4)
pruebas_kenshiro = [
    {'nombre': 'Hokuto Shinken', 'descripcion': 'Alcanza 50kg en Press de Banca.', 'clave_calculo': 'rm_50kg_banca', 'meta_valor': 50, 'puntos_recompensa': 400, 'es_secreta': False},
    {'nombre': 'Ya Estás Muerto', 'descripcion': 'Completa 25 entrenamientos.', 'clave_calculo': 'cien_entrenos', 'meta_valor': 25, 'puntos_recompensa': 450, 'es_secreta': False},
    {'nombre': 'Los Puntos Vitales', 'descripcion': 'Mantén una racha de 10 días.', 'clave_calculo': 'racha_7_dias', 'meta_valor': 10, 'puntos_recompensa': 500, 'es_secreta': False},
]

# Nivel 5: All Might
allmight = Arquetipo.objects.get(nivel=5)
pruebas_allmight = [
    {'nombre': 'One For All', 'descripcion': 'Alcanza 75kg en Press de Banca.', 'clave_calculo': 'rm_75kg_banca', 'meta_valor': 75, 'puntos_recompensa': 500, 'es_secreta': False},
    {'nombre': 'Plus Ultra!', 'descripcion': 'Supera tu récord personal en cualquier ejercicio.', 'clave_calculo': 'record_personal', 'meta_valor': 1, 'puntos_recompensa': 600, 'es_secreta': False},
    {'nombre': 'El Símbolo de la Paz', 'descripcion': 'Completa 30 entrenamientos.', 'clave_calculo': 'cien_entrenos', 'meta_valor': 30, 'puntos_recompensa': 550, 'es_secreta': False},
]

# =============================================================================
# CATEGORÍA 2: LOS GUERREROS (Niveles 11-30) - Pruebas de Poder
# =============================================================================

print("\n⚔️ Creando pruebas para LOS GUERREROS (Niveles 11-30)...")

# Nivel 21: Goku (Namek) - El Super Saiyan Legendario
goku_namek = Arquetipo.objects.get(nivel=21)
pruebas_goku_namek = [
    {'nombre': 'La Transformación Dorada', 'descripcion': 'Alcanza 100kg en Press de Banca.', 'clave_calculo': 'rm_100kg_banca', 'meta_valor': 100, 'puntos_recompensa': 1000, 'es_secreta': False},
    {'nombre': 'El Grito del Super Saiyan', 'descripcion': 'Rompe 2 récords personales en una semana.', 'clave_calculo': 'records_semanales', 'meta_valor': 2, 'puntos_recompensa': 1200, 'es_secreta': False},
    {'nombre': 'El Poder Legendario', 'descripcion': 'Levanta 50,000kg de volumen total.', 'clave_calculo': 'volumen_total_kg', 'meta_valor': 50000, 'puntos_recompensa': 1500, 'es_secreta': False},
    {'nombre': 'La Ira del Saiyan', 'descripcion': 'Completa un entrenamiento de más de 20,000kg en una sesión.', 'clave_calculo': 'volumen_sesion', 'meta_valor': 20000, 'puntos_recompensa': 2000, 'es_secreta': True},
]

# Nivel 25: Majin Buu (Gordo)
buu = Arquetipo.objects.get(nivel=25)
pruebas_buu = [
    {'nombre': 'Absorción de Poder', 'descripcion': 'Alcanza 150kg en Sentadilla.', 'clave_calculo': 'rm_150kg_sentadilla', 'meta_valor': 150, 'puntos_recompensa': 1500, 'es_secreta': False},
    {'nombre': 'Regeneración Infinita', 'descripcion': 'Mantén una racha de 21 días.', 'clave_calculo': 'racha_21_dias', 'meta_valor': 21, 'puntos_recompensa': 1800, 'es_secreta': False},
    {'nombre': 'Destrucción Inocente', 'descripcion': 'Levanta 100,000kg de volumen total.', 'clave_calculo': 'volumen_total_kg', 'meta_valor': 100000, 'puntos_recompensa': 2000, 'es_secreta': False},
]

# =============================================================================
# CATEGORÍA 3: LOS DIVINOS (Niveles 41-50) - Pruebas Divinas
# =============================================================================

print("\n🌟 Creando pruebas para LOS DIVINOS (Niveles 41-50)...")

# Nivel 41: Goku (SSJ God)
goku_god = Arquetipo.objects.get(nivel=41)
pruebas_goku_god = [
    {'nombre': 'El Ki Divino', 'descripcion': 'Alcanza 200kg en Press de Banca.', 'clave_calculo': 'rm_200kg_banca', 'meta_valor': 200, 'puntos_recompensa': 3000, 'es_secreta': False},
    {'nombre': 'Ritual de los Dioses', 'descripcion': 'Completa 100 entrenamientos.', 'clave_calculo': 'cien_entrenos', 'meta_valor': 100, 'puntos_recompensa': 3500, 'es_secreta': False},
    {'nombre': 'Trascendencia Mortal', 'descripcion': 'Levanta 250,000kg de volumen total.', 'clave_calculo': 'volumen_total_kg', 'meta_valor': 250000, 'puntos_recompensa': 4000, 'es_secreta': False},
    {'nombre': 'El Poder de los Dioses', 'descripcion': 'Rompe 5 récords personales en un mes.', 'clave_calculo': 'records_mensuales', 'meta_valor': 5, 'puntos_recompensa': 5000, 'es_secreta': True},
]

# Nivel 43: Beerus
beerus = Arquetipo.objects.get(nivel=43)
pruebas_beerus = [
    {'nombre': 'Hakai', 'descripcion': 'Alcanza 250kg en Peso Muerto.', 'clave_calculo': 'rm_250kg_peso_muerto', 'meta_valor': 250, 'puntos_recompensa': 4000, 'es_secreta': False},
    {'nombre': 'El Despertar del Destructor', 'descripcion': 'Mantén una racha de 30 días.', 'clave_calculo': 'racha_30_dias', 'meta_valor': 30, 'puntos_recompensa': 4500, 'es_secreta': False},
    {'nombre': 'Equilibrio Universal', 'descripcion': 'Levanta 500,000kg de volumen total.', 'clave_calculo': 'volumen_total_kg', 'meta_valor': 500000, 'puntos_recompensa': 5000, 'es_secreta': False},
]

# =============================================================================
# CATEGORÍA 4: LOS OMNIPOTENTES (Niveles 51-70) - Pruebas Cósmicas
# =============================================================================

print("\n🌌 Creando pruebas para LOS OMNIPOTENTES (Niveles 51-70)...")

# Nivel 51: Zeno Sama
zeno = Arquetipo.objects.get(nivel=51)
pruebas_zeno = [
    {'nombre': 'Borrado Universal', 'descripcion': 'Alcanza 300kg en cualquier ejercicio compuesto.', 'clave_calculo': 'rm_300kg_cualquiera', 'meta_valor': 300, 'puntos_recompensa': 6000, 'es_secreta': False},
    {'nombre': 'El Botón del Fin', 'descripcion': 'Completa 200 entrenamientos.', 'clave_calculo': 'doscientos_entrenos', 'meta_valor': 200, 'puntos_recompensa': 7000, 'es_secreta': False},
    {'nombre': 'Rey de Todo', 'descripcion': 'Levanta 1,000,000kg de volumen total.', 'clave_calculo': 'volumen_millon', 'meta_valor': 1000000, 'puntos_recompensa': 8000, 'es_secreta': False},
    {'nombre': 'Capricho Infantil', 'descripcion': 'Rompe 10 récords personales en total.', 'clave_calculo': 'records_totales', 'meta_valor': 10, 'puntos_recompensa': 10000, 'es_secreta': True},
]

# Nivel 55: Madoka Kaname (Diosa)
madoka = Arquetipo.objects.get(nivel=55)
pruebas_madoka = [
    {'nombre': 'El Sacrificio Supremo', 'descripcion': 'Mantén una racha de 50 días.', 'clave_calculo': 'racha_50_dias', 'meta_valor': 50, 'puntos_recompensa': 8000, 'es_secreta': False},
    {'nombre': 'Reescribir las Leyes', 'descripcion': 'Alcanza el top 3 en el ranking de puntos.', 'clave_calculo': 'ranking_top3', 'meta_valor': 3, 'puntos_recompensa': 10000, 'es_secreta': False},
    {'nombre': 'La Diosa de la Esperanza', 'descripcion': 'Levanta 2,000,000kg de volumen total.', 'clave_calculo': 'volumen_dos_millones', 'meta_valor': 2000000, 'puntos_recompensa': 12000, 'es_secreta': False},
]

# =============================================================================
# CATEGORÍA 5: LOS ABSOLUTOS (Niveles 91-100) - Pruebas Imposibles
# =============================================================================

print("\n♾️ Creando pruebas para LOS ABSOLUTOS (Niveles 91-100)...")

# Nivel 100: The One Above All
toaa = Arquetipo.objects.get(nivel=100)
pruebas_toaa = [
    {'nombre': 'Omnipotencia Absoluta', 'descripcion': 'Alcanza 500kg en Press de Banca.', 'clave_calculo': 'rm_500kg_banca', 'meta_valor': 500, 'puntos_recompensa': 50000, 'es_secreta': False},
    {'nombre': 'Más Allá de la Comprensión', 'descripcion': 'Completa 1000 entrenamientos.', 'clave_calculo': 'mil_entrenos', 'meta_valor': 1000, 'puntos_recompensa': 75000, 'es_secreta': False},
    {'nombre': 'El Uno Sobre Todo', 'descripcion': 'Mantén el puesto #1 en el ranking durante 30 días.', 'clave_calculo': 'ranking_numero_uno', 'meta_valor': 30, 'puntos_recompensa': 100000, 'es_secreta': False},
    {'nombre': 'Trascendencia Absoluta', 'descripcion': 'Levanta 10,000,000kg de volumen total.', 'clave_calculo': 'volumen_diez_millones', 'meta_valor': 10000000, 'puntos_recompensa': 200000, 'es_secreta': True},
]

# Nivel 99: Zeno Sama (Meta)
zeno_meta = Arquetipo.objects.get(nivel=99)
pruebas_zeno_meta = [
    {'nombre': 'Meta-Borrado', 'descripcion': 'Alcanza 450kg en Peso Muerto.', 'clave_calculo': 'rm_450kg_peso_muerto', 'meta_valor': 450, 'puntos_recompensa': 40000, 'es_secreta': False},
    {'nombre': 'Rey de Todas las Realidades', 'descripcion': 'Completa 500 entrenamientos.', 'clave_calculo': 'quinientos_entrenos', 'meta_valor': 500, 'puntos_recompensa': 60000, 'es_secreta': False},
    {'nombre': 'Capricho Multiversal', 'descripcion': 'Levanta 5,000,000kg de volumen total.', 'clave_calculo': 'volumen_cinco_millones', 'meta_valor': 5000000, 'puntos_recompensa': 80000, 'es_secreta': False},
]

# =============================================================================
# CREAR TODAS LAS PRUEBAS
# =============================================================================

# Lista de todas las pruebas a crear
todas_las_pruebas = [
    (saitama, pruebas_saitama),
    (lee, pruebas_lee),
    (zoro, pruebas_zoro),
    (kenshiro, pruebas_kenshiro),
    (allmight, pruebas_allmight),
    (goku_namek, pruebas_goku_namek),
    (buu, pruebas_buu),
    (goku_god, pruebas_goku_god),
    (beerus, pruebas_beerus),
    (zeno, pruebas_zeno),
    (madoka, pruebas_madoka),
    (zeno_meta, pruebas_zeno_meta),
    (toaa, pruebas_toaa),
]

total_pruebas_creadas = 0

for arquetipo, pruebas in todas_las_pruebas:
    print(f"\n⚔️ Creando pruebas para {arquetipo.titulo_arquetipo}...")
    for prueba_data in pruebas:
        prueba = PruebaLegendaria.objects.create(arquetipo=arquetipo, **prueba_data)
        print(f"   ✅ {prueba.nombre}")
        total_pruebas_creadas += 1

print(f"\n🎉 ¡CREACIÓN COMPLETADA!")
print(f"⚔️ Total de Pruebas Legendarias creadas: {total_pruebas_creadas}")
print(f"🏆 Total de Arquetipos con pruebas: {len(todas_las_pruebas)}")
print(f"📊 Pruebas en la base de datos: {PruebaLegendaria.objects.count()}")

print(f"\n🌟 RESUMEN POR CATEGORÍAS:")
print(f"🥊 Los Aspirantes (1-10): Pruebas de fundamentos y constancia")
print(f"⚔️ Los Guerreros (11-30): Pruebas de fuerza y poder")
print(f"🌟 Los Divinos (41-50): Pruebas que requieren poder divino")
print(f"🌌 Los Omnipotentes (51-70): Pruebas cósmicas y multiversales")
print(f"♾️ Los Absolutos (91-100): Pruebas imposibles para los más dedicados")

print(f"\n🚀 ¡El Códice de las Leyendas está completo!")
print(f"💪 Los clientes ahora tienen un viaje épico de 100 niveles")
print(f"🎯 Cada nivel tiene pruebas específicas y temáticas")
print(f"🏆 Desde entrenamientos básicos hasta logros legendarios")

print(f"\n💡 PRÓXIMOS PASOS:")
print(f"1. Puedes añadir más pruebas a los niveles intermedios")
print(f"2. Personalizar las pruebas según tu gimnasio específico")
print(f"3. Crear pruebas secretas especiales para eventos")
print(f"4. ¡Disfrutar viendo a tus clientes convertirse en leyendas!")

