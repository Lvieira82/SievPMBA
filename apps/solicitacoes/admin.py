from django.contrib import admin
from .models import MatriculaAutorizada
from django.utils import timezone
from .models import Municipio
from .models import Solicitacao, LogSistema

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


@admin.register(LogSistema)
class LogSistemaAdmin(admin.ModelAdmin):
    """Consulta somente leitura dos registros de auditoria do SIEVPM."""

    list_display = (
        "criado_em",
        "usuario",
        "acao",
        "solicitacao",
        "ip",
    )
    list_filter = (
        "acao",
        "criado_em",
    )
    search_fields = (
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
        "acao",
        "detalhes",
        "ip",
        "solicitacao__protocolo",
    )
    readonly_fields = (
        "usuario",
        "solicitacao",
        "acao",
        "detalhes",
        "ip",
        "criado_em",
    )
    ordering = ("-criado_em",)
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
