from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0009_add_hrv_ms_to_bitacora'),
        ('entrenos', '0032_gymdecisionlog_origen_normalizado'),
    ]

    operations = [
        migrations.CreateModel(
            name='GymDecisionVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(db_index=True)),
                ('version', models.PositiveIntegerField()),
                ('decision_id', models.CharField(db_index=True, max_length=100)),
                ('schema_version', models.PositiveSmallIntegerField(default=1)),
                ('origen', models.CharField(choices=[('motor', 'Motor'), ('correccion_manual', 'Corrección manual'), ('reversion_manual', 'Reversión manual')], max_length=24)),
                ('vigente', models.BooleanField(db_index=True, default=True)),
                ('fingerprint', models.CharField(db_index=True, max_length=64)),
                ('base_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('postura', models.CharField(max_length=20)),
                ('causa_principal', models.CharField(blank=True, max_length=80)),
                ('snapshot', models.JSONField(default=dict)),
                ('ajustes', models.JSONField(blank=True, default=dict)),
                ('motivo_correccion', models.TextField(blank=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versiones_decision_gym', to='clientes.cliente')),
                ('reemplaza', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reemplazos', to='entrenos.gymdecisionversion')),
            ],
            options={
                'ordering': ['fecha', 'version'],
            },
        ),
        migrations.AddConstraint(
            model_name='gymdecisionversion',
            constraint=models.UniqueConstraint(fields=('cliente', 'fecha', 'version'), name='uniq_gym_decision_version_cliente_fecha'),
        ),
        migrations.AddIndex(
            model_name='gymdecisionversion',
            index=models.Index(fields=['cliente', 'fecha', 'vigente'], name='entrenos_gy_cliente_debbfc_idx'),
        ),
    ]
