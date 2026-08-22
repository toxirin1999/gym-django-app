from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('rehab', '0003_contratoriesgogymfaserehab')]
    operations = [migrations.AddField(
        model_name='contratoriesgogymfaserehab', name='execution_enabled',
        field=models.BooleanField(default=False),
    )]
