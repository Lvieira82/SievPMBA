from pathlib import Path
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.solicitacoes.models import AnexoOPO, CumprimentoOPO, Solicitacao
from apps.solicitacoes.permissoes import eh_operador

_EXTENSOES_IMAGEM = {"jpg", "jpeg", "png", "webp"}
_MAX_IMAGEM = 5 * 1024 * 1024


def _operador_autorizado(request, solicitacao):
    acesso = getattr(request.user, "acesso_institucional", None)
    return bool(
        eh_operador(request.user)
        and acesso
        and acesso.unidade_id
        and solicitacao.unidade_id == acesso.unidade_id
        and solicitacao.status == "APROVADA"
        and solicitacao.data_evento == timezone.localdate()
    )


def _opo_principal(solicitacao):
    return (
        AnexoOPO.objects.filter(solicitacao=solicitacao)
        .exclude(arquivo="")
        .order_by("-criado_em")
        .first()
    )


def _pasta_protocolo(protocolo):
    return Path("protocolos") / protocolo


def _salvar_comprovacao_no_protocolo(solicitacao, imagem):
    """Salva a foto diretamente na mesma pasta dos documentos do protocolo."""
    protocolo = solicitacao.protocolo or "SEM_PROTOCOLO"
    extensao = Path(imagem.name).suffix.lower() or ".jpg"
    nome = f"comprovacao_opo_{timezone.localtime():%Y%m%d_%H%M%S_%f}{extensao}"
    caminho = str(_pasta_protocolo(protocolo) / nome)
    return default_storage.save(caminho, imagem)


def _salvar_justificativa_txt_no_protocolo(solicitacao, operador, justificativa):
    """Cria um TXT da justificativa na mesma pasta dos documentos do protocolo."""
    protocolo = solicitacao.protocolo or "SEM_PROTOCOLO"
    identificador = getattr(operador, "username", "operador") or "operador"
    seguro = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in identificador)
    nome = f"justificativa_opo_{seguro}_{timezone.localtime():%Y%m%d_%H%M%S_%f}.txt"
    caminho = str(_pasta_protocolo(protocolo) / nome)
    conteudo = (
        f"PROTOCOLO: {protocolo}\n"
        f"OPERADOR: {identificador}\n"
        f"DATA/HORA: {timezone.localtime():%d/%m/%Y %H:%M:%S}\n\n"
        f"JUSTIFICATIVA:\n{justificativa}\n"
    )
    return default_storage.save(caminho, __import__("django.core.files.base", fromlist=["ContentFile"]).ContentFile(conteudo.encode("utf-8")))


@login_required
@require_http_methods(["GET", "POST"])
def cumprimento_opo(request, solicitacao_id):
    solicitacao = get_object_or_404(
        Solicitacao.objects.select_related("municipio", "bairro", "unidade"),
        pk=solicitacao_id,
    )
    if not _operador_autorizado(request, solicitacao):
        messages.error(request, "Esta OPO não está liberada para o seu acesso de operador.")
        return redirect("eventos_dia")

    opo = _opo_principal(solicitacao)
    if not opo:
        messages.error(request, "A OPO deste evento ainda não possui arquivo disponível.")
        return redirect("eventos_dia")

    registro, _ = CumprimentoOPO.objects.get_or_create(opo=opo, operador=request.user)

    if request.method == "POST":
        resposta = request.POST.get("cumprida")
        imagem = request.FILES.get("imagem")
        justificativa = (request.POST.get("justificativa") or "").strip()

        if resposta not in {"SIM", "NAO"}:
            messages.error(request, "Informe se a OPO foi cumprida.")
        elif resposta == "SIM":
            if not imagem:
                messages.error(request, "Anexe uma imagem para confirmar o cumprimento da OPO.")
            else:
                extensao = Path(imagem.name).suffix.lower().lstrip(".")
                if extensao not in _EXTENSOES_IMAGEM:
                    messages.error(request, "A imagem deve estar em JPG, JPEG, PNG ou WEBP.")
                elif imagem.size > _MAX_IMAGEM:
                    messages.error(request, "A imagem deve ter no máximo 5 MB.")
                else:
                    if registro.imagem:
                        try:
                            registro.imagem.delete(save=False)
                        except Exception:
                            pass
                    caminho_imagem = _salvar_comprovacao_no_protocolo(solicitacao, imagem)
                    registro.cumprida = True
                    registro.imagem.name = caminho_imagem
                    registro.justificativa = ""
                    registro.respondido_em = timezone.now()
                    registro.save()
                    messages.success(request, "Cumprimento registrado como SIM.")
                    return redirect("cumprimento_opo", solicitacao_id=solicitacao_id)
        else:
            if not justificativa:
                messages.error(request, "Informe a justificativa quando a OPO não for cumprida.")
            else:
                if registro.imagem:
                    try:
                        registro.imagem.delete(save=False)
                    except Exception:
                        pass
                _salvar_justificativa_txt_no_protocolo(solicitacao, request.user, justificativa)
                registro.cumprida = False
                registro.imagem = None
                registro.justificativa = justificativa
                registro.respondido_em = timezone.now()
                registro.save()
                messages.success(request, "Registro de não cumprimento salvo com justificativa.")
                return redirect("cumprimento_opo", solicitacao_id=solicitacao_id)

    return render(request, "solicitacoes/cumprimento_opo.html", {
        "solicitacao": solicitacao,
        "opo": opo,
        "registro": registro,
    })


@login_required
def abrir_opo_operador(request, anexo_id):
    opo = get_object_or_404(
        AnexoOPO.objects.select_related("solicitacao", "solicitacao__unidade"),
        pk=anexo_id,
    )
    if not _operador_autorizado(request, opo.solicitacao):
        messages.error(request, "Esta OPO não está liberada para o seu acesso de operador.")
        return redirect("eventos_dia")
    if not opo.arquivo:
        messages.error(request, "O arquivo da OPO não está disponível.")
        return redirect("cumprimento_opo", solicitacao_id=opo.solicitacao_id)

    nome = getattr(opo.arquivo, "name", "") or ""
    if not nome:
        raise Http404("O arquivo da OPO não possui nome.")
    try:
        if default_storage.exists(nome):
            arquivo = default_storage.open(nome, "rb")
        else:
            caminho = Path(settings.MEDIA_ROOT) / nome
            if not caminho.is_file():
                raise Http404("O arquivo da OPO não foi encontrado no armazenamento.")
            arquivo = caminho.open("rb")
    except (OSError, ValueError):
        raise Http404("O arquivo da OPO não foi encontrado no armazenamento.")

    resposta = FileResponse(arquivo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{Path(nome).name}"'
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta
