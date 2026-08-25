from django.http import HttpResponse
from django.shortcuts import redirect


def minhas_solicitacoes(request):
    return redirect("consultar")


def _nao_implementada(nome):
    return HttpResponse(
        f"A funcionalidade '{nome}' ainda não está disponível nesta versão.",
        status=501,
        content_type="text/plain; charset=utf-8",
    )


def verificar_autenticidade(request, *args, **kwargs):
    return _nao_implementada("verificar autenticidade")


def alterar_status(request, *args, **kwargs):
    return _nao_implementada("alterar status")


def documentos_solicitacao(request, *args, **kwargs):
    return _nao_implementada("documentos da solicitação")


def abrir_documento_solicitacao(request, *args, **kwargs):
    return _nao_implementada("abertura de documento")


def lancamento_manual(request, *args, **kwargs):
    return _nao_implementada("lançamento manual")


def opos_geradas(request, *args, **kwargs):
    return _nao_implementada("OPOs geradas")


def detalhe_opo(request, *args, **kwargs):
    return _nao_implementada("detalhes da OPO")


def gerar_opo(request, *args, **kwargs):
    return _nao_implementada("geração da OPO")


def validar_matricula_opo_publica(request, *args, **kwargs):
    return _nao_implementada("validação de matrícula da OPO")


def detalhe_opo_publica(request, *args, **kwargs):
    return _nao_implementada("detalhes públicos da OPO")


def importar_matriculas_painel(request, *args, **kwargs):
    return _nao_implementada("importação de matrículas")


def mapa_eventos(request, *args, **kwargs):
    return _nao_implementada("mapa de eventos")


def gerar_mapa_eventos_pdf(request, *args, **kwargs):
    return _nao_implementada("PDF do mapa de eventos")


def importar_municipios(request, *args, **kwargs):
    return _nao_implementada("importação de municípios")
