from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from apps.solicitacoes.models import HistoricoSolicitacao, Solicitacao
from apps.solicitacoes.permissoes import (
    pode_aprovar_solicitacao,
    pode_lancamento_manual,
    pode_ver_solicitacao,
    escopo_unidades,
)
from .operacional import lancamento_manual as manual_original


@login_required
def lancamento_manual_seguro(request):
    if not pode_lancamento_manual(request.user):
        messages.error(request, "Você não possui permissão para criar OPO manual.")
        return redirect("painel_gestao")
    return manual_original(request)


@login_required
def aprovacoes_seguras(request):
    from django.shortcuts import render

    solicitacoes = (
        Solicitacao.objects
        .filter(unidade__in=escopo_unidades(request.user), status="PENDENTE")
        .select_related("unidade", "municipio", "bairro", "tipo_evento", "usuario")
        .prefetch_related("documentos__tipo_documento")
        .order_by("data_evento", "hora_inicio")
    )
    return render(request, "gestao/aprovacoes.html", {"solicitacoes": solicitacoes})


@login_required
def aprovar_solicitacao_segura(request, id):
    if request.method != "POST":
        return redirect("aprovacoes")

    s = get_object_or_404(
        Solicitacao.objects.select_related("unidade"),
        pk=id,
    )

    if not pode_aprovar_solicitacao(request.user, s):
        messages.error(request, "Você não possui acesso a esta solicitação.")
        return redirect("aprovacoes")

    if not s.documentos.exists():
        messages.error(request, "A solicitação não pode ser aprovada sem documentos anexados.")
        return redirect("aprovacoes")

    s.status = "APROVADA"
    s.data_aprovacao = timezone.now()
    s.aprovado_por = request.user.get_full_name() or request.user.username
    s.save(update_fields=["status", "data_aprovacao", "aprovado_por", "atualizado_em"])
    HistoricoSolicitacao.objects.create(
        solicitacao=s,
        usuario=request.user,
        acao="APROVADA",
        detalhes="Solicitação aprovada.",
    )
    return redirect("aprovacoes")


@login_required
def solicitar_correcao_segura(request, id):
    s = get_object_or_404(
        Solicitacao.objects.select_related("unidade", "usuario"),
        pk=id,
    )

    if not pode_aprovar_solicitacao(request.user, s):
        messages.error(request, "Você não possui acesso a esta solicitação.")
        return redirect("aprovacoes")

    if request.method != "POST":
        messages.error(request, "Use o formulário de correção para informar o motivo.")
        return redirect("aprovacoes")

    motivo = (request.POST.get("motivo_correcao") or request.POST.get("motivo") or "").strip()
    if not motivo:
        messages.error(request, "Informe o motivo da correção.")
        return redirect("aprovacoes")

    s.status = "CORRECAO"
    s.motivo_correcao = motivo
    s.save(update_fields=["status", "motivo_correcao", "atualizado_em"])

    HistoricoSolicitacao.objects.create(
        solicitacao=s,
        usuario=request.user,
        acao="CORRECAO",
        detalhes=motivo,
    )

    # O link é individual e leva diretamente o solicitante para o protocolo.
    link = request.build_absolute_uri(
        reverse("corrigir_solicitacao", kwargs={"protocolo": s.protocolo})
    )

    destinatario = s.email or (s.usuario.email if s.usuario else "")
    if destinatario:
        mensagem = f"""Olá, {s.solicitante}!\n\nSua solicitação {s.protocolo} precisa de correção antes de continuar a análise.\n\nMotivo informado pela gestão:\n{motivo}\n\nAcesse o link abaixo para abrir sua solicitação e realizar as correções:\n{link}\n\nApós enviar as alterações, a solicitação retornará para análise.\n\nPMBA - Sistema de Informações de Eventos (SiEv).\n"""
        try:
            send_mail(
                subject=f"Correção necessária - Protocolo {s.protocolo}",
                message=mensagem,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[destinatario],
                fail_silently=False,
            )
            messages.success(request, "Solicitação enviada para correção e o e-mail foi encaminhado ao solicitante.")
        except Exception:
            messages.warning(request, "A solicitação foi colocada em correção, mas não foi possível enviar o e-mail ao solicitante. Verifique o serviço de e-mail.")
    else:
        messages.warning(request, "A solicitação foi colocada em correção, mas não possui e-mail cadastrado para envio.")

    return redirect("aprovacoes")


@login_required
def indeferir_seguro(request, id):
    s = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=id)
    if not pode_aprovar_solicitacao(request.user, s):
        messages.error(request, "Você não possui acesso a esta solicitação.")
        return redirect("aprovacoes")
    if request.method == "POST":
        motivo = (request.POST.get("motivo") or "").strip()
        if not motivo:
            messages.error(request, "Informe o motivo do indeferimento.")
            return redirect("aprovacoes")
        s.status = "REJEITADA"
        s.data_aprovacao = timezone.now()
        s.save(update_fields=["status", "data_aprovacao", "atualizado_em"])
        HistoricoSolicitacao.objects.create(
            solicitacao=s,
            usuario=request.user,
            acao="REJEITADA",
            detalhes=motivo,
        )
    return redirect("aprovacoes")
