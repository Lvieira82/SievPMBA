from django.conf import settings
from django.db import migrations, models
import django.core.validators


def upload_cumprimento_opo(instance, filename):
    protocolo = getattr(instance.opo.solicitacao, "protocolo", None) or "SEM_PROTOCOLO"
    return f"protocolos/{protocolo}/cumprimentos/{filename}"


class Migration(migrations.Migration):
    dependencies = [
        ("solicitacoes", "0018_bloquear_multiplas_unidades_por_bairro"),
    ]

    operations = [
        migrations.CreateModel(
            name="CumprimentoOPO",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cumprida", models.BooleanField(blank=True, null=True)),
                ("imagem", models.FileField(
                    blank=True,
                    null=True,
                    upload_to=upload_cumprimento_opo,
                    validators=[django.core.validators.FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"])],
                )),
                ("justificativa", models.TextField(blank=True)),
                ("respondido_em", models.DateTimeField(blank=True, null=True)),
                ("operador", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="cumprimentos_opo", to=settings.AUTH_USER_MODEL)),
                ("opo", models.ForeignKey(on_delete=models.CASCADE, related_name="cumprimentos", to="solicitacoes.anexoopo")),
            ],
            options={"ordering": ["-respondido_em", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="cumprimentoopo",
            constraint=models.UniqueConstraint(fields=("opo", "operador"), name="uq_cumprimento_opo_operador"),
        ),
    ]
