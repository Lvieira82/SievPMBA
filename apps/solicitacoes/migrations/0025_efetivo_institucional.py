from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("solicitacoes", "0024_tipo_opo"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitacao",
            name="efetivo_institucional",
            field=models.CharField(blank=True, max_length=250),
        ),
    ]
