from django.contrib import admin, messages
from django.db import transaction
from django.template.response import TemplateResponse
from django.utils import timezone

from .models import (
    AnexoOPO,
    CumprimentoOPO,
    DocumentoSolicitacao,
    LogSistema,
    MatriculaAutorizada,
    Municipio,
    Solicitacao,
)
from .utils import gerar_pdf_autorizacao


@admin.register(Solicitacao)
class SolicitacaoAdmin(admin.ModelAdmin):
    list_display = (
        "protocolo",
        "nome_evento",
        "solicitante",
        "data_evento",
        "status",
    )
    search_fields = ("protocolo", "nome_evento", "solicitante")
    list_filter = ("status", "data_evento")
    actions = ["aprovar_solicitacao", "limpar_solicitacoes_selecionadas"]

    def aprovar_solicitacao(self, request, queryset):
        for solicitacao in queryset:
            solicitacao.status = "APROVADA"
            solicitacao.assinado_por = (
                request.user.get_full_name() or request.user.username
            )
            solicitacao.data_assinatura = timezone.now()
            nome_pdf = gerar_pdf_autorizacao(solicitacao)
            solicitacao.pdf_autorizacao = f"autorizacoes/{nome_pdf}"
            solicitacao.save()

    aprovar_solicitacao.short_description = "Aprovar solicitações"

    def limpar_solicitacoes_selecionadas(self, request, queryset):
        """Exclui solicitações selecionadas, preservando os logs de auditoria."""
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Somente um superusuário pode limpar solicitações.",
                level=messages.ERROR,
            )
            return None

        ids = list(queryset.values_list("pk", flat=True))
        if not ids:
            self.message_user(
                request,
                "Selecione pelo menos uma solicitação.",
                level=messages.WARNING,
            )
            return None

        if request.POST.get("confirmar_limpeza") != "sim":
            return TemplateResponse(
                request,
                "admin/solicitacoes/solicitacao/confirmar_limpeza.html",
                {
                    **self.admin_site.each_context(request),
                    "opts": self.model._meta,
                    "solicitacoes": queryset,
                    "quantidade": len(ids),
                    "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
                    "selected_ids": ids,
                    "title": "Confirmar limpeza de solicitações",
                },
            )

        arquivos = []
        documentos = DocumentoSolicitacao.objects.filter(solicitacao_id__in=ids)
        anexos_opo = AnexoOPO.objects.filter(solicitacao_id__in=ids)
        imagens_cumprimento = CumprimentoOPO.objects.filter(
            opo__solicitacao_id__in=ids
        )

        for item in documentos:
            if item.arquivo and item.arquivo.name:
                arquivos.append((item.arquivo.storage, item.arquivo.name))
        for item in anexos_opo:
            if item.arquivo and item.arquivo.name:
                arquivos.append((item.arquivo.storage, item.arquivo.name))
        for item in imagens_cumprimento:
            if item.imagem and item.imagem.name:
                arquivos.append((item.imagem.storage, item.imagem.name))

        try:
            with transaction.atomic():
                # O log é de auditoria e pode existir sem uma solicitação associada.
                # Desvinculamos os logs antes da exclusão para não apagar a auditoria.
                LogSistema.objects.filter(solicitacao_id__in=ids).update(
                    solicitacao=None
                )
                _, detalhes = Solicitacao.objects.filter(pk__in=ids).delete()
        except Exception as erro:
            self.message_user(
                request,
                f"Não foi possível limpar as solicitações: {erro}",
                level=messages.ERROR,
            )
            return None

        falhas_arquivos = 0
        for storage, nome in arquivos:
            try:
                storage.delete(nome)
            except Exception:
                falhas_arquivos += 1

        total_registros = sum(detalhes.values())
        mensagem = (
            f"Limpeza concluída: {len(ids)} solicitação(ões) removida(s) "
            f"e {total_registros} registro(s) do banco excluído(s). "
            "Os logs de auditoria foram preservados."
        )
        if falhas_arquivos:
            mensagem += (
                f" Atenção: {falhas_arquivos} arquivo(s) não puderam ser "
                "removidos do armazenamento."
            )
        self.message_user(request, mensagem, level=messages.SUCCESS)

    limpar_solicitacoes_selecionadas.short_description = (
        "Limpar solicitações selecionadas (preservar logs)"
    )


@admin.register(MatriculaAutorizada)
class MatriculaAutorizadaAdmin(admin.ModelAdmin):
    list_display = ("matricula", "nome", "posto", "unidade", "ativo", "criado_em")
    search_fields = ("matricula", "nome", "posto", "unidade")
    list_filter = ("ativo", "posto", "unidade")


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo")
    search_fields = ("nome",)
    list_filter = ("ativo",)


@admin.register(LogSistema)
class LogSistemaAdmin(admin.ModelAdmin):
    """Consulta somente leitura dos registros de auditoria do SIEVPM."""

    list_display = ("criado_em", "usuario", "acao", "solicitacao", "ip")
    list_filter = ("acao", "criado_em")
    search_fields = (
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
        "acao",
        "detalhes",
        "ip",
        "solicitacao__protocolo",
    )
    readonly_fields = ("usuario", "solicitacao", "acao", "detalhes", "ip", "criado_em")
    ordering = ("-criado_em",)
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
