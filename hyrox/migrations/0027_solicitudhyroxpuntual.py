import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('entrenos', '0048_evaluacionbloquegym'),
        ('hyrox', '0026_contratocampanahyrox'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SolicitudHyroxPuntual',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('fecha', models.DateField(db_index=True)),
                ('modo', models.CharField(choices=[('extra', 'Extra'), ('sustituye_gym', 'Sustituye Gym')], default='extra', max_length=20)),
                ('resolucion_gym', models.CharField(choices=[('ninguna', 'Ninguna'), ('reubicada', 'Reubicada'), ('omitida', 'Omitida')], default='ninguna', max_length=12)),
                ('fecha_reubicacion', models.DateField(blank=True, null=True)),
                ('estado', models.CharField(choices=[('autorizada', 'Autorizada'), ('en_registro', 'En registro'), ('completada', 'Completada'), ('cancelada', 'Cancelada'), ('fallida', 'Fallida')], default='autorizada', max_length=16)),
                ('idempotency_key', models.CharField(max_length=128)),
                ('authority_snapshot', models.JSONField(default=dict)),
                ('safety_snapshot', models.JSONField(default=dict)),
                ('gym_contract_snapshot', models.JSONField(default=dict)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='solicitudes_hyrox_puntuales_autorizadas', to=settings.AUTH_USER_MODEL)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='solicitudes_hyrox_puntuales', to='clientes.cliente')),
                ('hyrox_session', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='solicitudes_puntuales', to='hyrox.hyroxsession')),
                ('sesion_gym_programada', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='solicitudes_hyrox_puntuales', to='entrenos.sesionprogramada')),
            ],
            options={'ordering': ['-creado_en']},
        ),
        migrations.AddConstraint(
            model_name='solicitudhyroxpuntual',
            constraint=models.UniqueConstraint(fields=('cliente', 'idempotency_key'), name='uniq_solicitud_hyrox_cliente_key'),
        ),
    ]
