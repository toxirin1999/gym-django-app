from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0004_add_performance_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='altura_cm',
            field=models.FloatField(blank=True, help_text='cm', null=True),
        ),
    ]
