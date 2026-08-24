from django.contrib import admin
from .models import MatriculaAutorizada
from django.utils import timezone
from django.contrib import admin
from .models import Municipio
from .models import Solicitacao

from .utils import gerar_pdf_autorizacao


@admin.register(Solicitacao)
class SolicitacaoAdmin(admin.ModelAdmin):

    list_display = (
        'protocolo',
        'nome_evento',
        'solicitante',
        'data_evento',
        'status',
    )

    search_fields = (
        'protocolo',
        'nome_evento',
        'solicitante',
    )

    list_filter = (
        'status',
        'data_evento',
    )

    actions = ['aprovar_solicitacao']

    def aprovar_solicitacao(
        self,
        request,
        queryset
    ):

        for solicitacao in queryset:

            solicitacao.status = 'APROVADA'

            solicitacao.assinado_por = (
                request.user.get_full_name()
                or request.user.username
            )

            solicitacao.data_assinatura = timezone.now()

            nome_pdf = gerar_pdf_autorizacao(
                solicitacao
            )

            solicitacao.pdf_autorizacao = (
                f'autorizacoes/{nome_pdf}'
            )

            solicitacao.save()

    aprovar_solicitacao.short_description = (
        'Aprovar solicitações'
    )
@admin.register(MatriculaAutorizada)
class MatriculaAutorizadaAdmin(admin.ModelAdmin):
    list_display = (
        "matricula",
        "nome",
        "posto",
        "unidade",
        "ativo",
        "criado_em",
    )

    search_fields = (
        "matricula",
        "nome",
        "posto",
        "unidade",
    )

    list_filter = (
        "ativo",
        "posto",
        "unidade",
    )
    



@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):

    list_display = (
        "nome",
        "ativo",
    )

    search_fields = (
        "nome",
    )

    list_filter = (
        "ativo",
    )
