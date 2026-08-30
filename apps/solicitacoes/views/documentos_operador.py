import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.solicitacoes.models import (
    ConfiguracaoUnidade,
    DocumentoSolicitacao,
    HistoricoSolicitacao,
    Solicitacao,
)
from .compat import (
    abrir_documento_solicitacao as _abrir_documento_original,
    gerar_opo as _gerar_opo_original,
)


def _perfil_e_escopo(request):
    if request.user.is_superuser or request.user.is_staff:
        return None, Solicitacao.objects.all()

    perfil = getattr(request.user, "perfil_siev", None)
    if not perfil or not perfil.ativo:
        return None, Solicitacao.objects.none()

    if perfil.perfil == "COPPM":
        return perfil, Solicitacao.objects.all()

    if perfil.perfil == "CPR":
        return perfil, Solicitacao.objects.filter(unidade__cpr=perfil.cpr)

    if perfil.perfil == "UNIDADE":
        return perfil, Solicitacao.objects.filter(unidade=perfil.unidade)

    return None, Solicitacao.objects.none()


def _documentos_legados(solicitacao):
    campos = [
        ("Ofício ao Comandante", "oficio_comandante"),
        ("Ofício do Corpo de Bombeiros", "oficio_bombeiro"),
        ("Documento Sanitário", "documento_sanitario"),
        ("Documento de Meio Ambiente", "documento_meio_ambiente"),
    ]

    encontrados = []
    caminhos = set()

    for nome, campo in campos:
        arquivo = getattr(solicitacao, campo, None)
        if arquivo:
            try:
                url = arquivo.url
            except Exception:
                url = ""
            nome_arquivo = getattr(arquivo, "name", "") or ""
            caminhos.add(nome_arquivo)
            encontrados.append({"nome": nome, "campo": campo, "arquivo": arquivo, "url": url})

    pasta = os.path.join(settings.MEDIA_ROOT, "protocolos", solicitacao.protocolo)

    if os.path.isdir(pasta):
        nomes_conhecidos = {
            "oficio_comandante.pdf": "Ofício ao Comandante",
            "oficio_bombeiro.pdf": "Ofício do Corpo de Bombeiros",
            "documento_sanitario.pdf": "Documento Sanitário",
            "documento_meio_ambiente.pdf": "Documento de Meio Ambiente",
        }
        media_url = getattr(settings, "MEDIA_URL", "/media/").rstrip("/")

        for raiz, _, arquivos in os.walk(pasta):
            for nome_arquivo in sorted(arquivos):
                if not nome_arquivo.lower().endswith(".pdf"):
                    continue

                caminho = os.path.join(raiz, nome_arquivo)
                relativo = os.path.relpath(caminho, settings.MEDIA_ROOT).replace(os.sep, "/")

                if relativo in caminhos or nome_arquivo in caminhos:
                    continue

                chave = nome_arquivo.lower()
                nome_exibicao = nomes_conhecidos.get(
                    chave,
                    nome_arquivo.replace("_", " ").rsplit(".", 1)[0].title(),
                )
                encontrados.append({
                    "nome": nome_exibicao,
                    "campo": "arquivo_fisico",
                    "arquivo": nome_arquivo,
                    "url": f"{media_url}/{relativo}",
                })
                caminhos.add(relativo)
                caminhos.add(nome_arquivo)

    return encontrados


def _normalizar(texto):
    return "".join(ch.lower() for ch in str(texto or "") if ch.isalnum())


def _legado_satisfaz_tipo(nome_tipo, documentos_legados):
    nome = _normalizar(nome_tipo)
    for item in documentos_legados:
        campo = item["campo"]
        arquivo = _normalizar(item.get("arquivo", ""))
        nome_item = _normalizar(item.get("nome", ""))

        if campo == "oficio_comandante" and ("oficio" in nome and "comandante" in nome):
            return True
        if campo == "oficio_bombeiro" and "bombeiro" in nome:
            return True
        if campo == "documento_sanitario" and ("sanitario" in nome or "sanitaria" in nome):
            return True
        if campo == "documento_meio_ambiente" and "meioambiente" in nome:
            return True
        if arquivo and _normalizar(nome_tipo) in {arquivo, nome_item}:
            return True
        if "bombeiro" in nome and "bombeiro" in arquivo:
            return True
        if "comandante" in nome and "comandante" in arquivo:
            return True
        if ("sanitario" in nome or "sanitaria" in nome) and "sanitari" in arquivo:
            return True
        if "meioambiente" in nome and "meioambiente" in arquivo:
            return True

    return False


def _documentacao(solicitacao):
    documentos = list(
        DocumentoSolicitacao.objects
        .filter(solicitacao=solicitacao)
        .select_related("tipo_documento")
    )
    documentos_legados = _documentos_legados(solicitacao)

    obrigatorios = []
    if solicitacao.unidade_id:
        obrigatorios = list(
            ConfiguracaoUnidade.objects
            .filter(
                unidade_id=solicitacao.unidade_id,
                ativo=True,
                obrigatorio=True,
                tipo_documento__isnull=False,
            )
            .select_related("tipo_documento")
        )

    tipos_anexados = {documento.tipo_documento_id for documento in documentos}
    faltantes = [
        item.tipo_documento.nome
        for item in obrigatorios
        if item.tipo_documento_id not in tipos_anexados
        and not _legado_satisfaz_tipo(item.tipo_documento.nome, documentos_legados)
    ]

    return {
        "documentos": documentos,
        "documentos_legados": documentos_legados,
        "obrigatorios": obrigatorios,
        "faltantes": faltantes,
        "ok": bool(documentos or documentos_legados) and not faltantes,
    }


def _anexar_status_documental(solicitacao):
    """Adiciona somente atributos comuns; nunca sobrescreve o reverse manager documentos."""
    status = _documentacao(solicitacao)
    solicitacao.documentos_legados = status["documentos_legados"]
    solicitacao.documentos_obrigatorios = status["obrigatorios"]
    solicitacao.documentos_faltantes = status["faltantes"]
    solicitacao.documentacao_ok = status["ok"]
    return solicitacao


@login_required
def aprovacoes(request):
    perfil, escopo = _perfil_e_escopo(request)

    if not (request.user.is_superuser or request.user.is_staff) and perfil is None:
        messages.error(request, "Usuário sem perfil institucional ativo.")
        return redirect("login_gestao")

    solicitacoes = (
        escopo.filter(status="PENDENTE")
        .select_related("unidade", "municipio", "bairro", "tipo_evento", "usuario")
        .order_by("data_evento", "hora_inicio")
    )

    for solicitacao in solicitacoes:
        _anexar_status_documental(solicitacao)

    return render(request, "gestao/aprovacoes.html", {"solicitacoes": solicitacoes, "perfil": perfil})


@login_required
def documentos_solicitacao(request, id):
    perfil, escopo = _perfil_e_escopo(request)

    if not (request.user.is_superuser or request.user.is_staff) and perfil is None:
        messages.error(request, "Acesso não autorizado.")
        return redirect("login_gestao")

    solicitacao = get_object_or_404(
        escopo.select_related("municipio", "bairro", "unidade", "tipo_evento"),
        pk=id,
    )
    status = _documentacao(solicitacao)

    return render(
        request,
        "gestao/documentos_solicitacao.html",
        {
            "solicitacao": solicitacao,
            "documentos": status["documentos"],
            "documentos_legados": status["documentos_legados"],
            "documentos_obrigatorios": status["obrigatorios"],
            "documentos_faltantes": status["faltantes"],
            "documentacao_ok": status["ok"],
        },
    )


@login_required
def abrir_documento_solicitacao(request, id, tipo):
    _, escopo = _perfil_e_escopo(request)
    documento = get_object_or_404(
        DocumentoSolicitacao.objects.select_related("solicitacao"),
        pk=id,
        solicitacao__in=escopo,
    )
    return _abrir_documento_original(request, documento.id, tipo)


@login_required
def aprovar_solicitacao(request, id):
    if request.method != "POST":
        return redirect("aprovacoes")

    perfil, escopo = _perfil_e_escopo(request)

    if not (request.user.is_superuser or request.user.is_staff) and perfil is None:
        messages.error(request, "Acesso não autorizado.")
        return redirect("login_gestao")

    solicitacao = get_object_or_404(escopo, pk=id)

    if solicitacao.status != "PENDENTE":
        messages.error(request, "Esta solicitação não está pendente de análise.")
        return redirect("aprovacoes")

    status_documental = _documentacao(solicitacao)
    if not status_documental["ok"]:
        if status_documental["faltantes"]:
            faltantes = ", ".join(status_documental["faltantes"])
            messages.error(request, f"OPO bloqueada: falta(m) documento(s) obrigatório(s): {faltantes}.")
        else:
            messages.error(request, "OPO bloqueada: a solicitação ainda não possui documento anexado.")
        return redirect("documentos_solicitacao", id=id)

    solicitacao.status = "APROVADA"
    solicitacao.data_aprovacao = timezone.now()
    solicitacao.aprovado_por = request.user.get_full_name() or request.user.username
    solicitacao.save(update_fields=["status", "data_aprovacao", "aprovado_por", "atualizado_em"])

    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        status="APROVADA",
        observacao="Solicitação aprovada após conferência da documentação para geração da OPO.",
    )

    messages.success(request, f"Solicitação {solicitacao.protocolo} aprovada. A OPO será gerada agora.")
    return redirect("gerar_opo", id=id)


@login_required
def gerar_opo(request, id):
    _, escopo = _perfil_e_escopo(request)
    solicitacao = get_object_or_404(escopo, pk=id)
    status_documental = _documentacao(solicitacao)

    if not status_documental["ok"]:
        if status_documental["faltantes"]:
            faltantes = ", ".join(status_documental["faltantes"])
            messages.error(request, f"OPO bloqueada: falta(m) documento(s) obrigatório(s): {faltantes}.")
        else:
            messages.error(request, "OPO bloqueada: a solicitação não possui documento anexado.")
        return redirect("documentos_solicitacao", id=id)

    return _gerar_opo_original(request, id)
