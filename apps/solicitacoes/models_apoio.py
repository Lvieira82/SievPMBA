import os

from django.conf import settings
from django.db import models


def pasta_apoio(instance, filename):
    protocolo = instance.solicitacao.protocolo or "SEM_PROTOCOLO"
    sigla = (instance.unidade_destino.sigla or "UNIDADE").replace("/", "_")
    return os.path.join("protocolos", protocolo, "apoio", sigla, filename)


class ApoioEvento(models.Model):
    STATUS = [
        ("ENVIADO", "Enviado"),
        ("RECEBIDO", "Recebido"),
        ("OPO_GERADA", "OPO própria gerada"),
    ]

    solicitacao = models.ForeignKey(
        "solicitacoes.Solicitacao",
        on_delete=models.CASCADE,
        related_name="apoios",
    )
    unidade_origem = models.ForeignKey(
        "solicitacoes.Unidade",
        on_delete=models.PROTECT,
        related_name="apoios_enviados",
    )
    unidade_destino = models.ForeignKey(
        "solicitacoes.Unidade",
        on_delete=models.PROTECT,
        related_name="apoios_recebidos",
    )
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="apoios_enviados",
    )
    status = models.CharField(max_length=20, choices=STATUS, default="ENVIADO")
    observacao = models.TextField(blank=True)
    opo_arquivo = models.FileField(upload_to=pasta_apoio, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.solicitacao.protocolo} - {self.unidade_origem} → {self.unidade_destino}"
