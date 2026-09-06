from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("solicitacoes", "0015_apoioevento"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transferenciasolicitacao",
            name="usuario",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="transferencias_realizadas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="apoioevento",
            name="enviado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="apoios_enviados",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
