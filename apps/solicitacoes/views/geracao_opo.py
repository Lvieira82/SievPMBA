import base64
from io import BytesIO
from django.contrib import messages
from django.core.files.storage import default_storage
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.staticfiles import finders
from qrcode import make as make_qr
from weasyprint import HTML
from apps.solicitacoes.models import AnexoOPO, HistoricoSolicitacao, Solicitacao
from apps.solicitacoes.permissoes import pode_gerar_opo


def _logo_pmba_base64():
    caminho = finders.find("logos/logo_pmba.png")
    if not caminho:
        return ""
    try:
        with open(caminho, "rb") as arquivo:
            return "data:image/png;base64," + base64.b64encode(arquivo.read()).decode("utf-8")
    except OSError:
        return ""


def _unidade_executor(request, solicitacao):
    acesso = getattr(request.user, "acesso_institucional", None)
    unidade = getattr(acesso, "unidade", None)
    return unidade or solicitacao.unidade


def _gerar_pdf_opo(request, solicitacao, evento_extra=False, unidade_executor=None, observacoes_adicionais=""):
    data_geracao = timezone.localtime()

    url_verificacao = request.build_absolute_uri(
        f"/verificar/{solicitacao.protocolo}/"
    )

    qr_img = make_qr(url_verificacao)
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_base64 = "data:image/png;base64," + base64.b64encode(
        qr_buffer.getvalue()
    ).decode("utf-8")

    if solicitacao.origem == "MANUAL" and solicitacao.tipo_opo == "INSTITUCIONAL":
        # OPO Institucional usa exclusivamente o efetivo informado por matrícula
        # no Lançamento Interno. Nunca aplica o efetivo padrão/festivo.
        efetivo = (solicitacao.efetivo_institucional or "").strip()
    else:
        efetivo = (
            "Efetivo extraordinário escalado."
            if evento_extra
            else "01 (uma) Guarnição a critério do Coordenador de Área."
        )

    html = render_to_string(
        "solicitacoes/opo_pdf.html",
        {
            "solicitacao": solicitacao,
            "data_geracao": data_geracao,
            "qr_base64": qr_base64,
            "url_verificacao": url_verificacao,
            "efetivo_opo": efetivo,
            "gerado_por_nome": request.user.get_full_name() or request.user.username,
            "unidade_executor": unidade_executor,
            "logo_pmba_base64": _logo_pmba_base64(),
            "observacoes_adicionais": observacoes_adicionais,
        },
        request=request,
    )

    return HTML(
        string=html,
        base_url=request.build_absolute_uri("/"),
    ).write_pdf()


def _evento_extra_do_anexo(anexo):
    """Recupera a classificação registrada na descrição do anexo."""
    if not anexo:
        return False
    return "Evento extra: SIM" in (anexo.descricao or "")


def _salvar_ou_atualizar_anexo_opo(request, solicitacao, conteudo, evento_extra, unidade_executor):
    """
    Mantém um único anexo principal de OPO por solicitação.
    Se já existir, substitui o PDF; não cria outro registro.
    """
    nome = f"OPO_{solicitacao.protocolo}.pdf"
    descricao = (
        "OPO gerada pelo SiEv — Evento extra: "
        f"{'SIM' if evento_extra else 'NÃO'}"
    )
    arquivo_antigo = None

    with transaction.atomic():
        # Serializa duas tentativas simultâneas para a mesma solicitação.
        solicitacao_bloqueada = Solicitacao.objects.select_for_update().get(pk=solicitacao.pk)
        anexo = (
            AnexoOPO.objects.select_for_update()
            .filter(solicitacao=solicitacao_bloqueada)
            .order_by("-criado_em", "-pk")
            .first()
        )

        if anexo is None:
            anexo = AnexoOPO(solicitacao=solicitacao_bloqueada)

        if anexo.arquivo and anexo.arquivo.name:
            arquivo_antigo = anexo.arquivo.name

        anexo.descricao = descricao
        anexo.arquivo.save(nome, ContentFile(conteudo), save=False)
        anexo.save()

        HistoricoSolicitacao.objects.create(
            solicitacao=solicitacao_bloqueada,
            usuario=request.user,
            acao="OPO ATUALIZADA" if arquivo_antigo else "OPO GERADA",
            observacao=(
                f"Arquivo {anexo.arquivo.name} "
                f"{'atualizado' if arquivo_antigo else 'gerado'} pela unidade "
                f"{unidade_executor.nome if unidade_executor else 'não definida'}. "
                f"Evento extra: {'SIM' if evento_extra else 'NÃO'}."
            ),
        )

    # Só remove a versão física anterior depois que o novo arquivo foi salvo.
    if arquivo_antigo and arquivo_antigo != anexo.arquivo.name:
        try:
            default_storage.delete(arquivo_antigo)
        except Exception:
            # A falha de limpeza do arquivo antigo não invalida a OPO nova.
            pass

    return anexo


def _garantir_opo_padrao(request, solicitacao):
    """
    Garante que toda solicitação aprovada tenha um PDF acessível.
    Se já existir um PDF válido, não o recria nem altera.
    """
    anexos = (
        AnexoOPO.objects.filter(solicitacao=solicitacao)
        .order_by("-criado_em", "-pk")
    )
    anexo = anexos.first()

    if anexo and anexo.arquivo and anexo.arquivo.name:
        try:
            if default_storage.exists(anexo.arquivo.name):
                return anexo
        except Exception:
            pass

    # Ausência de escolha equivale sempre a evento ORDINÁRIO.
    evento_extra = _evento_extra_do_anexo(anexo)
    unidade_executor = _unidade_executor(request, solicitacao)
    conteudo = _gerar_pdf_opo(
        request,
        solicitacao,
        evento_extra=evento_extra,
        unidade_executor=unidade_executor,
        observacoes_adicionais="",
    )
    return _salvar_ou_atualizar_anexo_opo(
        request,
        solicitacao,
        conteudo,
        evento_extra,
        unidade_executor,
    )


@login_required
def gerar_opo_com_evento_extra(request, id):
    solicitacao = get_object_or_404(
        Solicitacao.objects.select_related(
            "unidade", "municipio", "bairro", "tipo_evento"
        ),
        pk=id,
    )

    if not pode_gerar_opo(request.user, solicitacao):
        messages.error(request, "Você não possui permissão para gerar esta OPO.")
        return redirect("painel_gestao")

    if solicitacao.status not in {"APROVADA", "CONCLUIDA"}:
        messages.error(
            request,
            "A OPO somente pode ser gerada após a aprovação da solicitação.",
        )
        return redirect("aprovacoes")

    # A abertura desta tela já garante um PDF padrão ORDINÁRIO.
    # Assim, sair sem responder à pergunta não deixa a solicitação sem OPO.
    anexo = _garantir_opo_padrao(request, solicitacao)
    evento_extra_atual = _evento_extra_do_anexo(anexo)

    if request.method == "GET":
        return render(
            request,
            "gestao/gerar_opo.html",
            {
                "solicitacao": solicitacao,
                "evento_extra_atual": evento_extra_atual,
                "opo_ja_gerada": bool(anexo and anexo.arquivo),
            },
        )

    # Campo ausente ou sem seleção significa ORDINÁRIO (False).
    evento_extra = request.POST.get("evento_extra") == "SIM"
    observacoes_adicionais = (request.POST.get("observacoes_adicionais") or "").strip()
    unidade_executor = _unidade_executor(request, solicitacao)
    conteudo = _gerar_pdf_opo(
        request,
        solicitacao,
        evento_extra=evento_extra,
        unidade_executor=unidade_executor,
        observacoes_adicionais=observacoes_adicionais,
    )

    _salvar_ou_atualizar_anexo_opo(
        request,
        solicitacao,
        conteudo,
        evento_extra,
        unidade_executor,
    )

    messages.success(
        request,
        f"OPO {solicitacao.protocolo} atualizada com sucesso. "
        "O PDF já está disponível em OPOs Geradas.",
    )
    return redirect("detalhe_opo", id=id)
