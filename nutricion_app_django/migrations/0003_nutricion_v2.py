from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nutricion_app_django', '0002_modulos_nutricionales'),
        ('clientes', '0005_add_altura_cliente'),
    ]

    operations = [
        # ── Eliminar modelos v1 (sin datos que preservar) ────────────────
        migrations.DeleteModel(name='AjusteNutricional'),
        migrations.DeleteModel(name='CheckNutricionalDiario'),
        migrations.DeleteModel(name='TargetNutricionalDiario'),
        migrations.DeleteModel(name='PerfilNutricional'),

        # ── PerfilNutricional v2 ─────────────────────────────────────────
        migrations.CreateModel(
            name='PerfilNutricional',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('altura_cm', models.FloatField(help_text='Altura en cm')),
                ('fase', models.CharField(
                    max_length=15, default='mantenimiento',
                    choices=[('definicion','Definición'),('volumen','Volumen'),
                             ('peak_week','Peak Week'),('mantenimiento','Mantenimiento')]
                )),
                ('grasa_corporal_pct', models.FloatField(editable=False)),
                ('masa_magra_kg', models.FloatField(editable=False)),
                ('safety_proteina_min_g_kg', models.FloatField(default=1.8)),
                ('safety_grasa_min_g_kg', models.FloatField(default=1.2)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cliente', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='perfil_nutricional',
                    to='clientes.cliente',
                )),
            ],
            options={'verbose_name': 'Perfil Nutricional',
                     'verbose_name_plural': 'Perfiles Nutricionales'},
        ),

        # ── TargetNutricionalDiario v2 ───────────────────────────────────
        migrations.CreateModel(
            name='TargetNutricionalDiario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('tipo_sesion', models.CharField(
                    max_length=10, default='descanso',
                    choices=[('gym','Sesión de Gym'),('hyrox','Sesión de Hyrox'),
                             ('descanso','Día de Descanso')]
                )),
                ('bloques_proteina', models.IntegerField(help_text='1 bloque = 7g proteína')),
                ('bloques_carbos',   models.IntegerField(help_text='1 bloque = 9g carbos netos')),
                ('bloques_grasas',   models.IntegerField(help_text='1 bloque = 3g grasa')),
                ('bloques_verduras', models.IntegerField(default=3)),
                ('proteina_g_ref',   models.IntegerField(default=0)),
                ('carbos_g_ref',     models.IntegerField(default=0)),
                ('grasas_g_ref',     models.IntegerField(default=0)),
                ('distribucion_comidas', models.JSONField(null=True, blank=True)),
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='targets_nutricionales',
                    to='clientes.cliente',
                )),
            ],
            options={'verbose_name': 'Target Nutricional Diario',
                     'verbose_name_plural': 'Targets Nutricionales Diarios'},
        ),
        migrations.AddConstraint(
            model_name='targetnutricionaldiario',
            constraint=models.UniqueConstraint(
                fields=['cliente', 'fecha'], name='unique_target_cliente_fecha'
            ),
        ),

        # ── CheckNutricionalDiario v2 ────────────────────────────────────
        migrations.CreateModel(
            name='CheckNutricionalDiario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('bloques_proteina_cumplidos', models.BooleanField(null=True, blank=True)),
                ('bloques_carbos_cumplidos',   models.BooleanField(null=True, blank=True)),
                ('bloques_grasas_cumplidos',   models.BooleanField(null=True, blank=True)),
                ('verduras_cumplidas',         models.BooleanField(null=True, blank=True)),
                ('hidratacion_ok',             models.BooleanField(null=True, blank=True)),
                ('fatiga_percibida', models.IntegerField(
                    null=True, blank=True,
                    validators=[django.core.validators.MinValueValidator(1),
                                django.core.validators.MaxValueValidator(10)]
                )),
                ('calidad_sueno', models.IntegerField(
                    null=True, blank=True,
                    validators=[django.core.validators.MinValueValidator(1),
                                django.core.validators.MaxValueValidator(10)]
                )),
                ('energia_entreno', models.IntegerField(
                    null=True, blank=True,
                    validators=[django.core.validators.MinValueValidator(1),
                                django.core.validators.MaxValueValidator(5)]
                )),
                ('hambre_excesiva',  models.BooleanField(null=True, blank=True)),
                ('cumplimiento_pct', models.FloatField(default=0.0)),
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='checks_nutricionales',
                    to='clientes.cliente',
                )),
            ],
            options={'verbose_name': 'Check Nutricional Diario',
                     'verbose_name_plural': 'Checks Nutricionales Diarios'},
        ),
        migrations.AddConstraint(
            model_name='checknutricionaldiario',
            constraint=models.UniqueConstraint(
                fields=['cliente', 'fecha'], name='unique_check_cliente_fecha'
            ),
        ),

        # ── RegistroBloques (nuevo) ──────────────────────────────────────
        migrations.CreateModel(
            name='RegistroBloques',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('fecha',  models.DateField()),
                ('comida', models.CharField(
                    max_length=10,
                    choices=[('desayuno','Desayuno'),('almuerzo','Almuerzo'),
                             ('cena','Cena'),('snack','Snack'),
                             ('pre','Pre-entreno'),('post','Post-entreno')]
                )),
                ('bloques_proteina', models.FloatField(default=0)),
                ('bloques_carbos',   models.FloatField(default=0)),
                ('bloques_grasas',   models.FloatField(default=0)),
                ('es_comodin',       models.BooleanField(default=False)),
                ('nota_comodin',     models.CharField(max_length=200, blank=True)),
                ('alimentos_json',   models.JSONField(null=True, blank=True)),
                ('creado_en',        models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='registros_bloques',
                    to='clientes.cliente',
                )),
            ],
            options={'ordering': ['fecha', 'comida'],
                     'verbose_name': 'Registro de Bloques',
                     'verbose_name_plural': 'Registros de Bloques'},
        ),

        # ── InformeOptimizacion (nuevo) ──────────────────────────────────
        migrations.CreateModel(
            name='InformeOptimizacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('semana', models.DateField(help_text='Lunes de la semana analizada')),
                ('media_peso_anterior',  models.FloatField(null=True, blank=True)),
                ('media_peso_nueva',     models.FloatField(null=True, blank=True)),
                ('cumplimiento_semana_pct', models.FloatField(default=0.0)),
                ('fatiga_media',         models.FloatField(null=True, blank=True)),
                ('rendimiento_gym_delta_pct',   models.FloatField(null=True, blank=True)),
                ('rendimiento_hyrox_delta_pct', models.FloatField(null=True, blank=True)),
                ('escenario', models.CharField(
                    max_length=2, default='X',
                    choices=[('A','Óptimo — mantener'),('B','Estancado — ajustar bloques'),
                             ('C','Fatiga/caída — Refeed'),('D','Sobreingesta — auditoría'),
                             ('X','Datos insuficientes')]
                )),
                ('alerta_honestidad', models.BooleanField(default=False)),
                ('ajuste_bloques_proteina', models.IntegerField(default=0)),
                ('ajuste_bloques_carbos',   models.IntegerField(default=0)),
                ('ajuste_bloques_grasas',   models.IntegerField(default=0)),
                ('ajuste_aplica_a', models.CharField(max_length=20, default='todos')),
                ('justificacion', models.TextField()),
                ('safety_lock_activado', models.BooleanField(default=False)),
                ('diet_break_sugerido',  models.BooleanField(default=False)),
                ('estado', models.CharField(
                    max_length=10, default='pendiente',
                    choices=[('pendiente','Pendiente de revisión'),
                             ('aceptado','Ajuste aceptado'),
                             ('rechazado','Semana atípica — sin ajuste')]
                )),
                ('razon_rechazo', models.CharField(max_length=200, blank=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='informes_optimizacion',
                    to='clientes.cliente',
                )),
            ],
            options={'ordering': ['-semana'],
                     'verbose_name': 'Informe de Optimización',
                     'verbose_name_plural': 'Informes de Optimización'},
        ),
        migrations.AddConstraint(
            model_name='informeoptimizacion',
            constraint=models.UniqueConstraint(
                fields=['cliente', 'semana'], name='unique_informe_cliente_semana'
            ),
        ),

        # ── AjusteNutricional v2 ─────────────────────────────────────────
        migrations.CreateModel(
            name='AjusteNutricional',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('fecha',  models.DateField(auto_now_add=True)),
                ('motivo', models.CharField(
                    max_length=20,
                    choices=[('sin_progreso','Sin progreso en 2 semanas'),
                             ('progreso_rapido','Progreso demasiado rápido'),
                             ('fatiga_alta','Fatiga elevada detectada'),
                             ('refeed','Refeed técnico'),
                             ('diet_break','Diet Break obligatorio'),
                             ('inicio','Configuración inicial')]
                )),
                ('proteina_anterior', models.IntegerField()),
                ('proteina_nuevo',    models.IntegerField()),
                ('carbos_anterior',   models.IntegerField()),
                ('carbos_nuevo',      models.IntegerField()),
                ('grasas_anterior',   models.IntegerField(default=0)),
                ('grasas_nuevo',      models.IntegerField(default=0)),
                ('aplica_a',          models.CharField(max_length=20, default='todos')),
                ('mensaje_usuario',   models.TextField()),
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ajustes_nutricionales',
                    to='clientes.cliente',
                )),
            ],
            options={'ordering': ['-fecha'],
                     'verbose_name': 'Ajuste Nutricional',
                     'verbose_name_plural': 'Ajustes Nutricionales'},
        ),
    ]
