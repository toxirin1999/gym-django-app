# Archivo: entrenos/api.py - API REST PARA INTEGRACIÓN CON iOS

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from django.contrib.auth.models import User
import json
import uuid
from datetime import datetime

from .models import EntrenoRealizado, DatosLiftinDetallados, DetalleEjercicioRealizado
from clientes.models import Cliente
from rutinas.models import Rutina, EjercicioBase


class LiftinAPIView(View):
    """
    API base para integración con Liftin
    """

    def dispatch(self, request, *args, **kwargs):
        # Verificar autenticación básica (en producción usar tokens JWT)
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({
                'error': 'Token de autorización requerido',
                'code': 'AUTH_REQUIRED'
            }, status=401)

        # En producción, validar el token aquí
        # token = auth_header.split(' ')[1]
        # if not validate_token(token):
        #     return JsonResponse({'error': 'Token inválido'}, status=401)

        return super().dispatch(request, *args, **kwargs)


@method_decorator(csrf_exempt, name='dispatch')
class ImportarEntrenamientoAPI(LiftinAPIView):
    """
    API endpoint para importar entrenamientos desde iOS/Liftin

    POST /api/liftin/entrenamientos/
    """

    def post(self, request):
        try:
            data = json.loads(request.body)

            # Validar datos requeridos
            required_fields = ['cliente_id', 'rutina_nombre', 'fecha', 'duracion_minutos']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'error': f'Campo requerido: {field}',
                        'code': 'MISSING_FIELD'
                    }, status=400)

            # Obtener o crear cliente
            try:
                cliente = Cliente.objects.get(id=data['cliente_id'])
            except Cliente.DoesNotExist:
                return JsonResponse({
                    'error': 'Cliente no encontrado',
                    'code': 'CLIENT_NOT_FOUND'
                }, status=404)

            # Obtener o crear rutina
            rutina, created = Rutina.objects.get_or_create(
                nombre=data['rutina_nombre'],
                defaults={'nombre': data['rutina_nombre']}
            )

            # Crear entrenamiento
            entreno = EntrenoRealizado.objects.create(
                cliente=cliente,
                rutina=rutina,
                fecha=datetime.fromisoformat(data['fecha'].replace('Z', '+00:00')).date(),
                fuente_datos='liftin',
                duracion_minutos=data['duracion_minutos'],
                calorias_quemadas=data.get('calorias_quemadas'),
                frecuencia_cardiaca_promedio=data.get('frecuencia_cardiaca_promedio'),
                frecuencia_cardiaca_maxima=data.get('frecuencia_cardiaca_maxima'),
                notas_liftin=data.get('notas'),
                liftin_workout_id=data.get('liftin_workout_id', f"api_{uuid.uuid4().hex[:8]}"),
                fecha_importacion=timezone.now()
            )

            # Crear datos detallados de Liftin si se proporcionan
            if any(key in data for key in ['datos_frecuencia_cardiaca', 'version_liftin', 'dispositivo_origen']):
                DatosLiftinDetallados.objects.create(
                    entreno=entreno,
                    datos_frecuencia_cardiaca=data.get('datos_frecuencia_cardiaca'),
                    version_liftin=data.get('version_liftin'),
                    dispositivo_origen=data.get('dispositivo_origen'),
                    sincronizado_health=data.get('sincronizado_health', False),
                    health_workout_uuid=data.get('health_workout_uuid'),
                    metadatos_adicionales=data.get('metadatos_adicionales')
                )

            # Procesar ejercicios si se proporcionan
            if 'ejercicios' in data:
                for ejercicio_data in data['ejercicios']:
                    # Obtener o crear ejercicio
                    ejercicio, created = Ejercicio.objects.get_or_create(
                        nombre=ejercicio_data['nombre'],
                        defaults={
                            'nombre': ejercicio_data['nombre'],
                            'grupo_muscular': ejercicio_data.get('grupo_muscular', 'General')
                        }
                    )

                    # Crear detalle del ejercicio
                    DetalleEjercicioRealizado.objects.create(
                        entreno=entreno,
                        ejercicio=ejercicio,
                        series=ejercicio_data.get('series', 1),
                        repeticiones=ejercicio_data.get('repeticiones', 0),
                        peso_kg=ejercicio_data.get('peso_kg', 0),
                        completado=ejercicio_data.get('completado', True)
                    )

            return JsonResponse({
                'success': True,
                'entrenamiento_id': entreno.id,
                'message': 'Entrenamiento importado exitosamente',
                'data': {
                    'id': entreno.id,
                    'cliente': entreno.cliente.nombre,
                    'rutina': entreno.rutina.nombre,
                    'fecha': entreno.fecha.isoformat(),
                    'duracion_formateada': entreno.duracion_formateada
                }
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'JSON inválido',
                'code': 'INVALID_JSON'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'error': f'Error interno: {str(e)}',
                'code': 'INTERNAL_ERROR'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class ListarEntrenamientosAPI(LiftinAPIView):
    """
    API endpoint para listar entrenamientos

    GET /api/liftin/entrenamientos/
    """

    def get(self, request):
        try:
            # Parámetros de filtrado
            cliente_id = request.GET.get('cliente_id')
            fuente = request.GET.get('fuente', 'liftin')  # Por defecto solo Liftin
            limite = int(request.GET.get('limite', 50))

            # Construir queryset
            entrenamientos = EntrenoRealizado.objects.select_related('cliente', 'rutina')

            if cliente_id:
                entrenamientos = entrenamientos.filter(cliente_id=cliente_id)

            if fuente:
                entrenamientos = entrenamientos.filter(fuente_datos=fuente)

            entrenamientos = entrenamientos.order_by('-fecha')[:limite]

            # Serializar datos
            data = []
            for entreno in entrenamientos:
                data.append({
                    'id': entreno.id,
                    'cliente': {
                        'id': entreno.cliente.id,
                        'nombre': entreno.cliente.nombre
                    },
                    'rutina': {
                        'nombre': entreno.rutina.nombre
                    },
                    'fecha': entreno.fecha.isoformat(),
                    'fuente_datos': entreno.fuente_datos,
                    'duracion_minutos': entreno.duracion_minutos,
                    'calorias_quemadas': entreno.calorias_quemadas,
                    'frecuencia_cardiaca_promedio': entreno.frecuencia_cardiaca_promedio,
                    'frecuencia_cardiaca_maxima': entreno.frecuencia_cardiaca_maxima,
                    'liftin_workout_id': entreno.liftin_workout_id,
                    'fecha_importacion': entreno.fecha_importacion.isoformat() if entreno.fecha_importacion else None
                })

            return JsonResponse({
                'success': True,
                'count': len(data),
                'entrenamientos': data
            })

        except Exception as e:
            return JsonResponse({
                'error': f'Error interno: {str(e)}',
                'code': 'INTERNAL_ERROR'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class EstadisticasAPI(LiftinAPIView):
    """
    API endpoint para obtener estadísticas

    GET /api/liftin/estadisticas/
    """

    def get(self, request):
        try:
            cliente_id = request.GET.get('cliente_id')

            # Construir queryset base
            entrenamientos = EntrenoRealizado.objects.filter(fuente_datos='liftin')

            if cliente_id:
                entrenamientos = entrenamientos.filter(cliente_id=cliente_id)

            # Calcular estadísticas
            total_entrenamientos = entrenamientos.count()

            if total_entrenamientos > 0:
                from django.db.models import Sum, Avg, Max, Min

                stats = entrenamientos.aggregate(
                    total_duracion=Sum('duracion_minutos'),
                    duracion_promedio=Avg('duracion_minutos'),
                    total_calorias=Sum('calorias_quemadas'),
                    calorias_promedio=Avg('calorias_quemadas'),
                    fc_promedio=Avg('frecuencia_cardiaca_promedio'),
                    fc_maxima_absoluta=Max('frecuencia_cardiaca_maxima')
                )

                # Entrenamiento más reciente
                ultimo_entreno = entrenamientos.order_by('-fecha').first()

                data = {
                    'total_entrenamientos': total_entrenamientos,
                    'total_duracion_minutos': stats['total_duracion'] or 0,
                    'duracion_promedio_minutos': round(stats['duracion_promedio'] or 0, 1),
                    'total_calorias': stats['total_calorias'] or 0,
                    'calorias_promedio': round(stats['calorias_promedio'] or 0, 1),
                    'frecuencia_cardiaca_promedio': round(stats['fc_promedio'] or 0, 1),
                    'frecuencia_cardiaca_maxima_absoluta': stats['fc_maxima_absoluta'] or 0,
                    'ultimo_entrenamiento': {
                        'fecha': ultimo_entreno.fecha.isoformat(),
                        'rutina': ultimo_entreno.rutina.nombre,
                        'duracion_minutos': ultimo_entreno.duracion_minutos
                    } if ultimo_entreno else None
                }
            else:
                data = {
                    'total_entrenamientos': 0,
                    'total_duracion_minutos': 0,
                    'duracion_promedio_minutos': 0,
                    'total_calorias': 0,
                    'calorias_promedio': 0,
                    'frecuencia_cardiaca_promedio': 0,
                    'frecuencia_cardiaca_maxima_absoluta': 0,
                    'ultimo_entrenamiento': None
                }

            return JsonResponse({
                'success': True,
                'estadisticas': data
            })

        except Exception as e:
            return JsonResponse({
                'error': f'Error interno: {str(e)}',
                'code': 'INTERNAL_ERROR'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class ClientesAPI(LiftinAPIView):
    """
    API endpoint para listar clientes

    GET /api/liftin/clientes/
    """

    def get(self, request):
        try:
            clientes = Cliente.objects.all().order_by('nombre')

            data = []
            for cliente in clientes:
                # Contar entrenamientos de Liftin para este cliente
                entrenamientos_liftin = EntrenoRealizado.objects.filter(
                    cliente=cliente,
                    fuente_datos='liftin'
                ).count()

                data.append({
                    'id': cliente.id,
                    'nombre': cliente.nombre,
                    'email': getattr(cliente, 'email', ''),
                    'entrenamientos_liftin': entrenamientos_liftin
                })

            return JsonResponse({
                'success': True,
                'count': len(data),
                'clientes': data
            })

        except Exception as e:
            return JsonResponse({
                'error': f'Error interno: {str(e)}',
                'code': 'INTERNAL_ERROR'
            }, status=500)


# Funciones auxiliares para autenticación (para implementar en el futuro)
def generate_api_token(user):
    """Genera un token JWT para el usuario"""
    # Implementar JWT aquí
    pass


def validate_token(token):
    """Valida un token JWT"""
    # Implementar validación JWT aquí
    return True  # Por ahora siempre válido


# Vistas de función para compatibilidad
@csrf_exempt
@require_http_methods(["POST"])
def webhook_liftin(request):
    """
    Webhook para recibir datos automáticamente desde Liftin
    (Para implementación futura con integración real)
    """
    try:
        data = json.loads(request.body)

        # Procesar webhook de Liftin
        # Esta función se activaría cuando Liftin envíe datos automáticamente

        return JsonResponse({
            'success': True,
            'message': 'Webhook procesado exitosamente'
        })

    except Exception as e:
        return JsonResponse({
            'error': f'Error procesando webhook: {str(e)}',
            'code': 'WEBHOOK_ERROR'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    Endpoint de salud para verificar que la API funciona
    """
    return JsonResponse({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0'
    })
