from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("entrenos", "0055_detalleejerciciorealizado_distancia_metros"),
        ("estiramientos", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sesionprogramada",
            name="estado",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente"),
                    ("completada", "Completada"),
                    ("parcial", "Parcial"),
                    ("saltada_usuario", "Saltada por usuario"),
                    ("omitida_usuario", "Omitida por ausencia planificada"),
                    ("omitida_sistema", "Omitida por sistema"),
                    ("cancelada_lesion", "Cancelada por lesión"),
                    ("sustituida_recuperacion", "Sustituida por recuperación"),
                ],
                db_index=True,
                default="pendiente",
                max_length=24,
            ),
        ),
        migrations.CreateModel(
            name="SesionMovilidadAdaptativa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("resolucion", models.CharField(choices=[("anadir", "Añadir movilidad"), ("posponer", "Posponer entrenamiento"), ("sustituir", "Sustituir por recuperación")], max_length=16)),
                ("fecha", models.DateField(db_index=True)),
                ("fecha_destino", models.DateField(blank=True, null=True)),
                ("duracion_minutos", models.PositiveIntegerField()),
                ("rpe", models.FloatField()),
                ("idempotency_key", models.CharField(max_length=120)),
                ("creada_en", models.DateTimeField(auto_now_add=True)),
                ("actividad", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="sesion_movilidad_adaptativa", to="entrenos.actividadrealizada")),
                ("cliente", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sesiones_movilidad_adaptativas", to="clientes.cliente")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sesiones_completadas", to="estiramientos.estiramientoplan")),
                ("sesion_programada", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sesiones_movilidad", to="entrenos.sesionprogramada")),
            ],
            options={"ordering": ["-fecha", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="sesionmovilidadadaptativa",
            constraint=models.UniqueConstraint(fields=("cliente", "idempotency_key"), name="unique_movilidad_cliente_idempotencia"),
        ),
    ]
