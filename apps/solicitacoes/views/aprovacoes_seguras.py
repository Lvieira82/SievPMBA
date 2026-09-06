from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.solicitacoes.models import HistoricoSolicitacao, Solicitacao
from apps.solicitacoes.permissoes import eh_desenvolvedor, eh_gestor, pode_aprovar_solicitacao
from .geracao_opo import gerar_opo_com_evento_extra


@login_required
def aprovacoes(request):
    if not (eh_desenvolvedor(request.user) or eh_gestor(request.user)):
        messages.error(request, "Somente gestores podem acessar as aprovações.")
        return redirect("painel_gestao")

    solicitacoes = (
        Solicitacao.objects.filter(status="PENDENTE")
        .select_related("municipio", "bairro", "unidade", "tipo_evento", "usuario")
        .prefetch_related("documentos__tipo_documento", "opos")
        .order_by("data_evento", "hora_inicio")
    )

    if not eh_desenvolvedor(request.user):
        permitidas = [s.id for s in solicitacoes if pode_aprovar_solicitacao(request.user, s)]
        solicitacoes = solicitacoes.filter(id__in=permitidas)

    for s in solicitacoes:
        ids = {str(item.id) for item in s.documentos.all()}
        vistos = set(request.session.get(f"documentos_conferidos_{s.id}", []))
        s.documentos_conferidos = bool(ids) and ids.issubset(vistos)

    return render(request, "gestao/aprovacoes.html", {"solicitacoes": solicitacoes, "pode_aprovar": True})


@login_required
def aprovar_solicitacao(request, id):
    if request.method != "POST":
        return redirect("aprovacoes")
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=id)
    if not pode_aprovar_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui permissão para aprovar esta solicitação.")
        return redirect("aprovacoes")
    if solicitacao.status != "PENDENTE":
        messages.error(request, "Esta solicitação não está pendente de aprovação.")
        return redirect("aprovacoes")

    documentos = list(solicitacao.documentos.all())
    if not documentos:
        messages.error(request, "A aprovação está bloqueada: a solicitação não possui documentação anexada para conferência.")
        return redirect("aprovacoes")

    vistos = {str(item) for item in request.session.get(f"documentos_conferidos_{solicitacao.id}", [])}
    pendentes = [doc for doc in documentos if str(doc.id) not in vistos]
    if pendentes:
        messages.warning(request, "Antes de aprovar, abra e confira todos os documentos anexados desta solicitação.")
        return redirect("aprovacoes")

    solicitacao.status = "APROVADA"
    solicitacao.data_aprovacao = timezone.now()
    solicitacao.aprovado_por = request.user.get_full_name() or request.user.username
    solicitacao.save(update_fields=["status", "data_aprovacao", "aprovado_por", "atualizado_em"])
    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        status="APROVADA",
        observacao="Solicitação aprovada pelo gestor após conferência da documentação.",
    )
    messages.success(request, f"Solicitação {solicitacao.protocolo} aprovada. Escolha o tipo de efetivo para gerar a OPO.")
    return redirect("gerar_opo", id=id)


@login_required
def solicitar_correcao_gestao(request, id):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade", "municipio", "usuario"), pk=id)
    if not pode_aprovar_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui permissão para solicitar correção desta solicitação.")
        return redirect("aprovacoes")
    if request.method == "POST":
        motivo = (request.POST.get("motivo_correcao") or request.POST.get("motivo") or "").strip()
        if not motivo:
            messages.error(request, "Informe o motivo da correção.")
            return render(request, "gestao/solicitar_correcao.html", {"solicitacao": solicitacao})
        solicitacao.status = "CORRECAO"
        solicitacao.motivo_correcao = motivo
        solicitacao.save(update_fields=["status", "motivo_correcao", "atualizado_em"])
        HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, status="CORRECAO", observacao=motivo)
        link = request.build_absolute_uri(reverse("corrigir_solicitacao", kwargs={"protocolo": solicitacao.protocolo}))
        destinatario = solicitacao.email or (solicitacao.usuario.email if solicitacao.usuario else "")
        if destinatario:
            mensagem = f"""Olá, {solicitacao.solicitante}!\n\nSua solicitação de evento foi devolvida para correção.\n\nPROTOCOLO: {solicitacao.protocolo}\nEVENTO: {solicitacao.nome_evento}\n\nMOTIVO DA CORREÇÃO:\n{motivo}\n\nPara corrigir, abra o link abaixo:\n{link}\n\nDepois de enviar a correção, o protocolo retornará para análise.\n\nPMBA - Sistema de Informações de Eventos (SiEv).\n"""
            try:
                send_mail(subject=f"Correção necessária - Protocolo {solicitacao.protocolo}", message=mensagem, from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[destinatario], fail_silently=False)
                messages.success(request, "Solicitação enviada para correção e e-mail encaminhado ao solicitante.")
            except Exception:
                messages.warning(request, "A solicitação foi enviada para correção, mas o e-mail não pôde ser enviado.")
        else:
            messages.warning(request, "A solicitação foi enviada para correção, mas não possui e-mail cadastrado.")
        return redirect("aprovacoes")
    return render(request, "gestao/solicitar_correcao.html", {"solicitacao": solicitacao})


@login_required
def gerar_opo_seguro(request, id):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=id)
    if not eh_desenvolvedor(request.user) and not pode_aprovar_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui permissão para gerar esta OPO.")
        return redirect("painel_gestao")
    return gerar_opo_com_evento_extra(request, id)
