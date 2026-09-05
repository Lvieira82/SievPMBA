from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import apps.solicitacoes.models_apoio


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0014_unificar_ramos_de_migracoes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ApoioEvento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("ENVIADO", "Enviado"), ("RECEBIDO", "Recebido"), ("OPO_GERADA", "OPO própria gerada")], default="ENVIADO", max_length=20)),
                ("observacao", models.TextField(blank=True)),
                ("opo_arquivo", models.FileField(blank=True, upload_to=apps.solicitacoes.models_apoio.pasta_apoio)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("enviado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="apoios_enviados", to=settings.AUTH_USER_MODEL)),
                ("solicitacao", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="apoios", to="solicitacoes.solicitacao")),
                ("unidade_destino", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="apoios_recebidos", to="solicitacoes.unidade")),
                ("unidade_origem", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="apoios_enviados", to="solicitacoes.unidade")),
            ],
            options={"ordering": ["-criado_em"]},
        ),
    ]
