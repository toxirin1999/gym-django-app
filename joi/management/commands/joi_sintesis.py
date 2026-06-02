import datetime

from django.core.management.base import BaseCommand

from clientes.models import Cliente
from joi.models import MensajeJOI, NarrativaActiva
from joi.services import (
    generar_sintesis_joi,
    revisar_manual_david,
    registrar_sintesis_log,
    _hay_contexto_para_revision,
    _revision_antigua,
    _actualizar_narrativa_activa,
    construir_contexto,
)


def _capas_snapshot(cliente_user) -> dict:
    try:
        n = NarrativaActiva.objects.get(user=cliente_user)
        return {
            'capa_corta': n.capa_corta or '',
            'capa_media': n.capa_media or '',
            'capa_larga': n.capa_larga or '',
            'estado': n.estado,
            'confianza': n.confianza,
        }
    except NarrativaActiva.DoesNotExist:
        return {}


class Command(BaseCommand):
    help = 'Ciclo completo JOI: revisión ManualDavid, NarrativaActiva, síntesis — con trazabilidad.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', type=str,
                            help='Ejecutar solo para un usuario concreto (username)')
        parser.add_argument('--solo-narrativa', action='store_true',
                            help='Solo revisar ManualDavid y NarrativaActiva, sin generar mensaje.')
        parser.add_argument('--forzar-capas', action='store_true',
                            help='Regenera capa_media y capa_larga saltando el bloqueo de 14/28 días. '
                                 'Uso puntual de migración, no operación normal.')

    def handle(self, *args, **options):
        from entrenos.models import ActividadRealizada

        ahora = datetime.datetime.now()
        generados = 0
        silenciados = 0
        saltados = 0
        revisiones = 0

        if options.get('usuario'):
            clientes = Cliente.objects.filter(
                user__username=options['usuario']
            ).select_related('user')
        else:
            clientes = Cliente.objects.select_related('user').all()

        for cliente in clientes:
            try:
                # ── MODO REVISIÓN ─────────────────────────────────────────────
                ultima_revision = None
                narrativa_existia = NarrativaActiva.objects.filter(
                    user=cliente.user
                ).exists()
                try:
                    narrativa_obj = NarrativaActiva.objects.get(user=cliente.user)
                    ultima_revision = narrativa_obj.ultima_revision_manual
                except NarrativaActiva.DoesNotExist:
                    pass

                debe_revisar = (
                    _revision_antigua(ultima_revision, dias=7)
                    or _hay_contexto_para_revision(cliente, ultima_revision)
                )

                if debe_revisar:
                    capas_antes = _capas_snapshot(cliente.user)

                    resultado_revision = revisar_manual_david(cliente)
                    revisiones += 1

                    narrativa_existe_ahora = NarrativaActiva.objects.filter(
                        user=cliente.user
                    ).exists()

                    _forzar = options.get('forzar_capas', False)
                    if resultado_revision.get('cambio_significativo') or not narrativa_existe_ahora or _forzar:
                        try:
                            ctx = construir_contexto(cliente)
                            _actualizar_narrativa_activa(cliente, ctx, cambio_significativo=True, forzar=_forzar)
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'  {cliente.user.username}: NarrativaActiva falló — {e}'
                                )
                            )

                    capas_despues = _capas_snapshot(cliente.user)

                    try:
                        registrar_sintesis_log(
                            cliente=cliente,
                            tipo='manual',
                            resultado_revision=resultado_revision,
                            narrativa_existia=narrativa_existia,
                            capas_antes=capas_antes,
                            capas_despues=capas_despues,
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'  log falló (no crítico): {e}')
                        )

                    self._imprimir_resumen(cliente, resultado_revision, capas_antes, capas_despues)

                if options.get('solo_narrativa'):
                    continue

                # ── MODO GENERACIÓN ───────────────────────────────────────────
                ultimo_msg = (
                    MensajeJOI.objects
                    .filter(user=cliente.user)
                    .order_by('-creado_en')
                    .first()
                )

                if ultimo_msg and not ultimo_msg.leido and ultimo_msg.trigger == 'sintesis_joi':
                    saltados += 1
                    continue

                ultimo_ts = ultimo_msg.creado_en if ultimo_msg else None
                trigger_activo = False

                if not ultimo_ts:
                    trigger_activo = True
                else:
                    ts_naive = ultimo_ts.replace(tzinfo=None)
                    if (ahora - ts_naive).total_seconds() > 48 * 3600:
                        trigger_activo = True

                if not trigger_activo and ultimo_ts:
                    if ActividadRealizada.objects.filter(
                        cliente=cliente,
                        tipo__in=['gym', 'hyrox', 'carrera'],
                        fecha__gte=ultimo_ts.date(),
                    ).exists():
                        trigger_activo = True

                if not trigger_activo and ultimo_ts:
                    try:
                        from diario.models import ProsocheDiario, ReflexionLibre
                        if (
                            ProsocheDiario.objects.filter(
                                prosoche_mes__usuario=cliente.user,
                                fecha__gte=ultimo_ts.date(),
                            ).exists()
                            or
                            ReflexionLibre.objects.filter(
                                usuario=cliente.user, fecha__gte=ultimo_ts,
                            ).exists()
                        ):
                            trigger_activo = True
                    except Exception:
                        pass

                if not trigger_activo:
                    saltados += 1
                    continue

                resultado = generar_sintesis_joi(cliente)
                if resultado:
                    generados += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  {cliente.user.username}: "{resultado.mensaje[:100]}..."'
                        )
                    )
                else:
                    silenciados += 1
                    self.stdout.write(f'  {cliente.user.username}: [SILENCE]')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  {cliente.user.username}: ERROR — {e}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nResultado: {revisiones} revisiones | {generados} mensajes '
                f'| {silenciados} silencios | {saltados} saltados'
            )
        )

    def _imprimir_resumen(self, cliente, resultado, capas_antes, capas_despues):
        nombre = cliente.user.username
        sig = resultado.get('cambio_significativo')
        delta = resultado.get('delta_confianza_medio', 0)
        self.stdout.write(
            f'  {nombre}: revisión (Δ={delta:.2f}, significativo={sig})'
        )

        for cambio in resultado.get('cambios_detalle', []):
            self.stdout.write(
                f'    ManualDavid: [{cambio["antes_estado"]}→{cambio["despues_estado"]}] '
                f'{cambio["antes_confianza"]:.2f}→{cambio["despues_confianza"]:.2f} '
                f'| {cambio["hipotesis"][:60]}'
            )
            if cambio.get('motivo'):
                self.stdout.write(f'      motivo: {cambio["motivo"]}')

        capas_mod = [
            c for c in ('capa_corta', 'capa_media', 'capa_larga')
            if capas_antes.get(c) != capas_despues.get(c) and capas_despues.get(c)
        ]
        if capas_mod:
            accion = 'creada' if not capas_antes else 'actualizada'
            self.stdout.write(
                self.style.SUCCESS(
                    f'  {nombre}: NarrativaActiva {accion} — capas: {", ".join(capas_mod)}'
                )
            )
            for capa in capas_mod:
                nuevo = capas_despues.get(capa, '')
                if nuevo:
                    self.stdout.write(f'    {capa}: {nuevo[:100]}')
        else:
            self.stdout.write(f'  {nombre}: NarrativaActiva sin cambio')

        evidencia = resultado.get('evidencia_usada', [])
        if evidencia:
            self.stdout.write(f'  {nombre}: evidencia usada: {", ".join(evidencia[:4])}')
