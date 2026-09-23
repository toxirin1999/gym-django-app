from django.db import migrations, models


def identificar_planes_historicos(apps, schema_editor):
    Plan = apps.get_model("estiramientos", "EstiramientoPlan")
    codigos = {
        "SUPERIOR": "stretch-upper-body",
        "INFERIOR": "stretch-lower-body",
        "COMPLETO": "stretch-full-body",
    }
    usados = set()
    for plan in Plan.objects.order_by("pk"):
        base = codigos.get(plan.fase, f"stretch-plan-{plan.pk}")
        codigo = base
        contador = 2
        while codigo in usados:
            codigo = f"{base}-{contador}"
            contador += 1
        usados.add(codigo)
        plan.codigo = codigo
        plan.modalidad = "estiramientos"
        plan.save(update_fields=["codigo", "modalidad"])


class Migration(migrations.Migration):
    dependencies = [("estiramientos", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="estiramientoplan",
            name="codigo",
            field=models.SlugField(default="", max_length=80),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="estiramientoplan",
            name="descripcion",
            field=models.CharField(blank=True, default="", max_length=220),
        ),
        migrations.AddField(
            model_name="estiramientoplan",
            name="modalidad",
            field=models.CharField(
                choices=[("estiramientos", "Estiramientos"), ("movilidad", "Movilidad")],
                default="estiramientos",
                max_length=16,
            ),
        ),
        migrations.RunPython(identificar_planes_historicos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="estiramientoplan",
            name="codigo",
            field=models.SlugField(max_length=80, unique=True),
        ),
        migrations.AlterField(
            model_name="estiramientoplan",
            name="fase",
            field=models.CharField(
                choices=[
                    ("SUPERIOR", "Tren superior"),
                    ("INFERIOR", "Tren inferior"),
                    ("COMPLETO", "Cuerpo completo"),
                ],
                max_length=12,
            ),
        ),
    ]
