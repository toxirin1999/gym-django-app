from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nutricion_app_django', '0001_initial'),
        ('clientes', '0005_add_altura_cliente'),
    ]

    operations = [
        migrations.CreateModel(
            name='PerfilNutricional',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('altura_cm', models.FloatField(help_text='Altura en cm')),
                ('grasa_corporal_pct', models.FloatField(editable=False)),
                ('masa_magra_kg', models.FloatField(editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cliente', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='perfil_nutricional',
                    to='clientes.cliente',
                )),
            ],
            options={
                'verbose_name': 'Perfil Nutricional',
                'verbose_name_plural': 'Perfiles Nutricionales',
            },
        ),
        migrations.CreateModel(
            name='TargetNutricionalDiario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('tipo_dia', models.CharField(choices=[('carga', 'Día de Carga'), ('moderado', 'Día Moderado'), ('descarga', 'Día de Descarga')], max_length=10)),
                ('porciones_proteina', models.IntegerField(help_text='Número de palmas (1 palma ≈ 25g proteína)')),
                ('porciones_carbos', models.IntegerField(help_text='Número de puños (1 puño ≈ 30g carbos)')),
                ('porciones_grasas', models.IntegerField(help_text='Número de pulgares (1 pulgar ≈ 10g grasa)')),
                ('porciones_verduras', models.IntegerField(default=3, help_text='Número de puños de verduras')),
                ('proteina_g_min', models.IntegerField()),
                ('proteina_g_max', models.IntegerField()),
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='targets_nutricionales',
                    to='clientes.cliente',
                )),
            ],
            options={
                'verbose_name': 'Target Nutricional Diario',
                'verbose_name_plural': 'Targets Nutricionales Diarios',
                'unique_together': {('cliente', 'fecha')},
            },
        ),
        migrations.CreateModel(
            name='CheckNutricionalDiario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('proteina_cumplida', models.BooleanField(blank=True, null=True)),
                ('carbos_pre_entreno', models.BooleanField(blank=True, null=True)),
                ('verduras_cumplidas', models.BooleanField(blank=True, null=True)),
                ('hidratacion_ok', models.BooleanField(blank=True, null=True)),
                ('hambre_excesiva', models.BooleanField(blank=True, help_text='¿Tuviste hambre excesiva durante el día?', null=True)),
                ('energia_post_entreno', models.IntegerField(
                    blank=True,
                    null=True,
                    help_text='Energía tras el entrenamiento (1=muy baja, 5=excelente)',
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(5),
                    ],
                )),
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='checks_nutricionales',
                    to='clientes.cliente',
                )),
            ],
            options={
                'verbose_name': 'Check Nutricional Diario',
                'verbose_name_plural': 'Checks Nutricionales Diarios',
                'unique_together': {('cliente', 'fecha')},
            },
        ),
        migrations.CreateModel(
            name='AjusteNutricional',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(auto_now_add=True)),
                ('motivo', models.CharField(choices=[('sin_progreso', 'Sin progreso en 2 semanas'), ('progreso_rapido', 'Progreso demasiado rápido'), ('fatiga_alta', 'Fatiga elevada detectada'), ('inicio', 'Configuración inicial')], max_length=20)),
                ('proteina_anterior', models.IntegerField()),
                ('proteina_nuevo', models.IntegerField()),
                ('carbos_anterior', models.IntegerField()),
                ('carbos_nuevo', models.IntegerField()),
                ('mensaje_usuario', models.TextField()),
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ajustes_nutricionales',
                    to='clientes.cliente',
                )),
            ],
            options={
                'verbose_name': 'Ajuste Nutricional',
                'verbose_name_plural': 'Ajustes Nutricionales',
                'ordering': ['-fecha'],
            },
        ),
    ]
