from django.core.management.base import BaseCommand

from rehab.models import EjercicioRehab, FaseProtocolo, PrescripcionEjercicio, ProtocoloRehab

PROTOCOLO_SLUG = 'tendinopatia-rotuliana'


class Command(BaseCommand):
    help = "Siembra el protocolo Tendinopatía rotuliana (Cook & Purdam) con sus fases y ejercicios."

    def handle(self, *args, **options):
        if ProtocoloRehab.objects.filter(slug=PROTOCOLO_SLUG, activo=True).exists():
            protocolo = ProtocoloRehab.objects.get(slug=PROTOCOLO_SLUG, activo=True)
        else:
            protocolo = ProtocoloRehab.objects.create(
                slug=PROTOCOLO_SLUG,
                version=1,
                nombre='Tendinopatía rotuliana',
                zona='rodilla',
                descripcion=(
                    'Progresión en 3 fases basada en el modelo de continuum de Cook & Purdam: '
                    'isométrica -> isotónica lenta y pesada -> almacenamiento de energía/pliometría.'
                ),
                fuente_referencia=(
                    'Cook JL, Purdam CR. "The challenge of managing tendinopathy in competing '
                    'athletes." Br J Sports Med. 2014;48(7):506-509. '
                    'Malliaras P, et al. "Patellar tendinopathy: clinical diagnosis, load management, '
                    'and advice for challenging case presentations." JOSPT. 2015;45(11):887-898.'
                ),
                criterios_alta={
                    'dolor_maximo_actividad_deportiva': 2,
                    'sesiones_sin_dolor_post_24h_consecutivas': 4,
                    'simetria_minima_porcentaje': 90,
                },
                advertencias=(
                    'Detener la sesión si el dolor supera 5/10 durante el ejercicio. '
                    'El dolor post-actividad debe resolverse en menos de 24h; si no, retroceder de fase.'
                ),
            )

        fases_seed = [
            {
                'orden': 1,
                'slug': 'fase-1-isometrica',
                'nombre': 'Fase 1 · Isométrica',
                'objetivo': 'Reducir dolor mediante contracciones isométricas de alta carga sin agravar el tendón.',
                'duracion_minima_dias': 7,
                'duracion_tipica_dias': 14,
                'reglas_avance': {
                    'min_sesiones': 6,
                    'umbral_dolor': 3,
                    'min_adherencia': 0.8,
                },
                'reglas_retroceso': {
                    'dolor_post_24h_umbral': 5,
                    'sesiones_consecutivas_con_dolor': 2,
                },
                'descripcion': (
                    'Contracciones isométricas mantenidas para analgesia y mantenimiento de capacidad '
                    'de carga del tendón sin componente excéntrico/concéntrico.'
                ),
                'ejercicios': [
                    {
                        'nombre': 'Sentadilla isométrica en pared (~60°)',
                        'slug': 'sentadilla-isometrica-pared-60',
                        'tipo_contraccion': 'isometrico',
                        'descripcion_ejecucion': (
                            'Apoyo en pared con flexión de rodilla a ~60 grados, mantener posición '
                            'estática con carga tolerable de dolor.'
                        ),
                        'equipo': 'Pared / balón suizo opcional',
                        'nombre_equivalente_gym': 'Sentadilla isométrica en pared',
                        'series': 5,
                        'frecuencia_semanal': 5,
                        'parametros': {
                            'duracion_segundos': 45,
                            'descanso_segundos': 60,
                            'intensidad_referencia': 'RPE 6-7, dolor <= 3/10',
                        },
                        'notas': 'Progresar a carga externa (chaleco/barra) cuando la tolerancia mejore.',
                    },
                    {
                        'nombre': 'Extensión de rodilla isométrica en máquina',
                        'slug': 'extension-rodilla-isometrica-maquina',
                        'tipo_contraccion': 'isometrico',
                        'descripcion_ejecucion': (
                            'Extensión de rodilla en máquina bloqueada a ~30-60 grados de flexión, '
                            'mantener contracción estática.'
                        ),
                        'equipo': 'Máquina de extensión de rodilla',
                        'nombre_equivalente_gym': 'Extensión de cuádriceps en máquina',
                        'series': 4,
                        'frecuencia_semanal': 4,
                        'parametros': {
                            'duracion_segundos': 45,
                            'descanso_segundos': 90,
                            'intensidad_referencia': '70% de 1RM percibido, dolor <= 3/10',
                        },
                        'notas': '',
                    },
                ],
            },
            {
                'orden': 2,
                'slug': 'fase-2-isotonica-lenta-pesada',
                'nombre': 'Fase 2 · Isotónica lenta y pesada',
                'objetivo': 'Restaurar capacidad de carga del tendón mediante trabajo excéntrico-concéntrico lento y pesado.',
                'duracion_minima_dias': 14,
                'duracion_tipica_dias': 42,
                'reglas_avance': {
                    'min_sesiones': 12,
                    'umbral_dolor': 3,
                    'min_adherencia': 0.8,
                },
                'reglas_retroceso': {
                    'dolor_post_24h_umbral': 5,
                    'sesiones_consecutivas_con_dolor': 2,
                },
                'descripcion': (
                    'Trabajo isotónico con tempo controlado (fase excéntrica lenta) y cargas progresivas '
                    'para estimular remodelación del tendón.'
                ),
                'ejercicios': [
                    {
                        'nombre': 'Sentadilla con tempo excéntrico lento',
                        'slug': 'sentadilla-tempo-excentrico-lento',
                        'tipo_contraccion': 'isotonico_lento',
                        'descripcion_ejecucion': (
                            'Sentadilla con barra o mancuernas, fase excéntrica de 3-4 segundos, '
                            'pausa breve, ascenso controlado.'
                        ),
                        'equipo': 'Barra / rack',
                        'nombre_equivalente_gym': 'Sentadilla con barra',
                        'series': 4,
                        'frecuencia_semanal': 3,
                        'parametros': {
                            'repeticiones': 8,
                            'tempo': '4-1-2-0',
                            'descanso_segundos': 120,
                            'intensidad_referencia': 'dolor <= 3/10 durante la serie',
                        },
                        'notas': 'Progresar carga semanalmente si dolor post-24h se resuelve.',
                    },
                    {
                        'nombre': 'Prensa de piernas con tempo excéntrico lento',
                        'slug': 'prensa-piernas-tempo-excentrico-lento',
                        'tipo_contraccion': 'isotonico_lento',
                        'descripcion_ejecucion': (
                            'Prensa de piernas unilateral o bilateral, fase excéntrica de 3-4 segundos '
                            'con rango controlado hasta ~90 grados de flexión de rodilla.'
                        ),
                        'equipo': 'Prensa de piernas',
                        'nombre_equivalente_gym': 'Prensa de piernas',
                        'series': 4,
                        'frecuencia_semanal': 3,
                        'parametros': {
                            'repeticiones': 8,
                            'tempo': '4-1-2-0',
                            'descanso_segundos': 120,
                            'intensidad_referencia': 'dolor <= 3/10 durante la serie',
                        },
                        'notas': '',
                    },
                ],
            },
            {
                'orden': 3,
                'slug': 'fase-3-almacenamiento-energia-pliometria',
                'nombre': 'Fase 3 · Almacenamiento de energía y pliometría',
                'objetivo': 'Reintroducir demandas elásticas y de alta velocidad para retorno al deporte.',
                'duracion_minima_dias': 14,
                'duracion_tipica_dias': 28,
                'reglas_avance': {
                    'min_sesiones': 8,
                    'umbral_dolor': 2,
                    'min_adherencia': 0.85,
                },
                'reglas_retroceso': {
                    'dolor_post_24h_umbral': 4,
                    'sesiones_consecutivas_con_dolor': 2,
                },
                'descripcion': (
                    'Ejercicios pliométricos de baja/media intensidad que reintroducen ciclo '
                    'estiramiento-acortamiento antes del retorno al deporte.'
                ),
                'ejercicios': [
                    {
                        'nombre': 'Salto a caja (bajo volumen)',
                        'slug': 'salto-caja-bajo-volumen',
                        'tipo_contraccion': 'pliometrico',
                        'descripcion_ejecucion': (
                            'Salto vertical con despegue y aterrizaje controlado sobre caja baja, '
                            'énfasis en aterrizaje suave.'
                        ),
                        'equipo': 'Caja pliométrica baja',
                        'nombre_equivalente_gym': None,
                        'series': 3,
                        'frecuencia_semanal': 2,
                        'parametros': {
                            'repeticiones': 6,
                            'descanso_segundos': 90,
                            'intensidad_referencia': 'dolor <= 2/10, sin dolor post-24h',
                        },
                        'notas': 'Progresar a saltos unilaterales y cambios de dirección según tolerancia.',
                    },
                    {
                        'nombre': 'Skipping / rebote de tobillo',
                        'slug': 'skipping-rebote-tobillo',
                        'tipo_contraccion': 'pliometrico',
                        'descripcion_ejecucion': (
                            'Rebotes de baja amplitud enfatizando contacto rápido con el suelo, '
                            'preparación para carrera y cambios de dirección.'
                        ),
                        'equipo': 'Ninguno',
                        'nombre_equivalente_gym': None,
                        'series': 3,
                        'frecuencia_semanal': 2,
                        'parametros': {
                            'duracion_segundos': 20,
                            'descanso_segundos': 60,
                            'intensidad_referencia': 'dolor <= 2/10',
                        },
                        'notas': '',
                    },
                ],
            },
        ]

        for fase_data in fases_seed:
            ejercicios = fase_data.pop('ejercicios')
            fase, _ = FaseProtocolo.objects.update_or_create(
                protocolo=protocolo,
                slug=fase_data['slug'],
                defaults={k: v for k, v in fase_data.items() if k != 'slug'},
            )

            for orden, ejercicio_data in enumerate(ejercicios, start=1):
                series = ejercicio_data.pop('series')
                frecuencia_semanal = ejercicio_data.pop('frecuencia_semanal')
                parametros = ejercicio_data.pop('parametros')
                notas = ejercicio_data.pop('notas')

                ejercicio, _ = EjercicioRehab.objects.update_or_create(
                    slug=ejercicio_data['slug'],
                    defaults={k: v for k, v in ejercicio_data.items() if k != 'slug'},
                )

                PrescripcionEjercicio.objects.update_or_create(
                    fase=fase,
                    ejercicio=ejercicio,
                    defaults={
                        'orden': orden,
                        'series': series,
                        'frecuencia_semanal': frecuencia_semanal,
                        'parametros': parametros,
                        'notas': notas,
                    },
                )

        self.stdout.write(self.style.SUCCESS(
            f"Protocolo '{protocolo.nombre}' v{protocolo.version} sembrado con "
            f"{protocolo.fases.count()} fases."
        ))
