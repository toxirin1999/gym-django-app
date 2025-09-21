# Django Management Command: verificar_datos_estoicos.py
# Ubicación: estoico/management/commands/verificar_datos_estoicos.py

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count


class Command(BaseCommand):
    """
    Comando para verificar la integridad de los datos estoicos.
    Uso: python manage.py verificar_datos_estoicos
    """

    help = 'Verifica la integridad de los datos estoicos'

    def handle(self, *args, **options):
        self.stdout.write('🔍 Verificando integridad de datos...')

        self._verificar_contenido_diario()
        self._verificar_logros()
        self._verificar_usuarios()

        self.stdout.write(
            self.style.SUCCESS('✅ Verificación completada')
        )

    def _verificar_contenido_diario(self):
        """Verifica que el contenido diario esté completo."""
        from estoico.models import ContenidoDiario

        total_contenidos = ContenidoDiario.objects.count()
        self.stdout.write(f'📚 Contenidos diarios: {total_contenidos}/366')

        if total_contenidos < 366:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Faltan {366 - total_contenidos} contenidos')
            )

        # Verificar días faltantes usando el campo correcto 'dia'
        dias_existentes = set(
            ContenidoDiario.objects.values_list('dia', flat=True)
        )
        dias_faltantes = set(range(1, 367)) - dias_existentes

        if dias_faltantes:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Días faltantes: {sorted(list(dias_faltantes))}')
            )

        # Verificar campos obligatorios
        contenidos_incompletos = ContenidoDiario.objects.filter(
            cita__isnull=True
        ).count()

        if contenidos_incompletos > 0:
            self.stdout.write(
                self.style.ERROR(f'❌ {contenidos_incompletos} contenidos sin cita')
            )

        # Verificar contenidos sin autor
        contenidos_sin_autor = ContenidoDiario.objects.filter(
            autor__isnull=True
        ).count()

        if contenidos_sin_autor > 0:
            self.stdout.write(
                self.style.WARNING(f'⚠️ {contenidos_sin_autor} contenidos sin autor')
            )

        # Verificar distribución por autor
        try:
            autores = ContenidoDiario.objects.values('autor').annotate(
                count=Count('id')
            ).order_by('-count')

            self.stdout.write('📊 Distribución por autor:')
            for autor in autores:
                self.stdout.write(f'  - {autor["autor"]}: {autor["count"]} citas')
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️ No se pudo obtener distribución por autor: {e}')
            )

        # Verificar distribución por mes
        try:
            meses = ContenidoDiario.objects.values('mes').annotate(
                count=Count('id')
            ).order_by('mes')

            self.stdout.write('📊 Distribución por mes:')
            for mes in meses:
                self.stdout.write(f'  - {mes["mes"]}: {mes["count"]} días')
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️ No se pudo obtener distribución por mes: {e}')
            )

    def _verificar_logros(self):
        """Verifica que los logros estén configurados correctamente."""
        try:
            from estoico.models import Logro

            total_logros = Logro.objects.count()
            self.stdout.write(f'🏆 Logros configurados: {total_logros}')

            if total_logros == 0:
                self.stdout.write(
                    self.style.WARNING(
                        '⚠️ No hay logros configurados. Ejecuta: python manage.py cargar_datos_estoicos --crear-logros')
                )
                return

            # Verificar logros por categoría si el campo existe
            try:
                categorias = Logro.objects.values('categoria').annotate(
                    count=Count('id')
                ).order_by('categoria')

                self.stdout.write('📊 Logros por categoría:')
                for categoria in categorias:
                    self.stdout.write(f'  - {categoria["categoria"]}: {categoria["count"]} logros')
            except Exception:
                # El campo categoria no existe, mostrar logros básicos
                logros = Logro.objects.values('nombre', 'descripcion')[:5]
                self.stdout.write('📊 Primeros 5 logros:')
                for logro in logros:
                    self.stdout.write(f'  - {logro["nombre"]}: {logro["descripcion"]}')

            # Verificar logros sin criterios si el campo existe
            try:
                logros_sin_criterio = Logro.objects.filter(
                    criterio_tipo__isnull=True
                ).count()

                if logros_sin_criterio > 0:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️ {logros_sin_criterio} logros sin criterio')
                    )
            except Exception:
                pass  # El campo criterio_tipo no existe

            # Verificar logros inactivos si el campo existe
            try:
                logros_inactivos = Logro.objects.filter(activo=False).count()
                if logros_inactivos > 0:
                    self.stdout.write(f'ℹ️ {logros_inactivos} logros inactivos')
            except Exception:
                pass  # El campo activo no existe

        except ImportError:
            self.stdout.write(
                self.style.WARNING('⚠️ Modelo Logro no encontrado')
            )

    def _verificar_usuarios(self):
        """Verifica el estado de los usuarios."""
        from django.contrib.auth.models import User

        total_usuarios = User.objects.count()
        self.stdout.write(f'👥 Usuarios totales: {total_usuarios}')

        # Verificar perfiles estoicos si el modelo existe
        try:
            from estoico.models import PerfilEstoico
            usuarios_con_perfil = PerfilEstoico.objects.count()
            self.stdout.write(f'👤 Usuarios con perfil estoico: {usuarios_con_perfil}')

            if usuarios_con_perfil < total_usuarios:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️ {total_usuarios - usuarios_con_perfil} usuarios sin perfil estoico'
                    )
                )
        except ImportError:
            self.stdout.write('ℹ️ Modelo PerfilEstoico no encontrado')

        # Verificar reflexiones si el modelo existe
        try:
            from estoico.models import ReflexionDiaria

            usuarios_activos = ReflexionDiaria.objects.values('usuario').distinct().count()
            self.stdout.write(f'✍️ Usuarios con reflexiones: {usuarios_activos}')

            # Estadísticas de reflexiones
            total_reflexiones = ReflexionDiaria.objects.count()
            self.stdout.write(f'📝 Total reflexiones: {total_reflexiones}')

            try:
                reflexiones_completadas = ReflexionDiaria.objects.filter(completada=True).count()
                self.stdout.write(f'✅ Reflexiones completadas: {reflexiones_completadas}')
            except Exception:
                pass  # El campo completada no existe

            try:
                promedio_calificacion = ReflexionDiaria.objects.filter(
                    calificacion_dia__isnull=False
                ).aggregate(promedio=Avg('calificacion_dia'))['promedio']

                if promedio_calificacion:
                    self.stdout.write(f'⭐ Promedio calificación: {promedio_calificacion:.2f}/5')
            except Exception:
                pass  # El campo calificacion_dia no existe

        except ImportError:
            self.stdout.write('ℹ️ Modelo ReflexionDiaria no encontrado')

        # Verificar logros de usuarios si el modelo existe
        try:
            from estoico.models import LogroUsuario

            usuarios_con_logros = LogroUsuario.objects.values('usuario').distinct().count()
            self.stdout.write(f'🏆 Usuarios con logros: {usuarios_con_logros}')

            # Logros otorgados
            total_logros_otorgados = LogroUsuario.objects.count()
            self.stdout.write(f'🎖️ Total logros otorgados: {total_logros_otorgados}')

            try:
                logros_no_vistos = LogroUsuario.objects.filter(visto=False).count()
                if logros_no_vistos > 0:
                    self.stdout.write(f'🔔 Logros no vistos: {logros_no_vistos}')
            except Exception:
                pass  # El campo visto no existe

        except ImportError:
            self.stdout.write('ℹ️ Modelo LogroUsuario no encontrado')

        # Mostrar usuario demo si existe
        try:
            usuario_demo = User.objects.get(username='demo_estoico')
            self.stdout.write(f'🎭 Usuario demo encontrado: {usuario_demo.username}')
        except User.DoesNotExist:
            self.stdout.write(
                'ℹ️ Usuario demo no encontrado. Ejecuta: python manage.py cargar_datos_estoicos --crear-usuario-demo')
        except Exception as e:
            pass
