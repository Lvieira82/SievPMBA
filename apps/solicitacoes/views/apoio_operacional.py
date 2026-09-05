from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db import transaction

from apps.solicitacoes.models import AnexoOPO, HistoricoSolicitacao, Solicitacao, Unidade
from apps.solicitacoes.models_acesso import AcessoInstitucional
from apps.solicitacoes.models_apoio import ApoioEvento
from apps.solicitacoes.permissoes import eh_desenvolvedor, eh_gestor, pode_ver_solicitacao
from .geracao_opo import _pdf_opo


def _acesso(request):
    return getattr(request.user, "acesso_institucional", None)


def _eh_gestor_unidade_do(request, unidade):
    if eh_desenvolvedor(request.user):
        return True
    a = _acesso(request)
    return bool(a and a.ativo and request.user.is_active and a.funcao == "GESTOR" and a.perfil == "UNIDADE" and a.unidade_id == unidade.id)


def _unidades_aptas_para_apoio(solicitacao):
    # Unidades especializadas (ex.: Cavalaria e Motociclistas) podem receber
    # o pacote de apoio para produzir sua própria OPO fora da área territorial.
    return Unidade.objects.filter(ativo=True, tipo="ESPECIALIZADA").exclude(pk=solicitacao.unidade_id).order_by("sigla", "nome")


@login_required
def enviar_apoio(request, id):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade", "municipio", "bairro"), pk=id)

    if not (eh_desenvolvedor(request.user) or (eh_gestor(request.user) and pode_ver_solicitacao(request.user, solicitacao))):
        messages.error(request, "Você não possui permissão para enviar apoio deste evento.")
        return redirect("opos_geradas")

    opo = solicitacao.opos.order_by("-criado_em").first()
    if not opo or not opo.arquivo:
        messages.error(request, "Gere a OPO principal antes de enviar um apoio.")
        return redirect("detalhe_opo", id=id)

    unidades = _unidades_aptas_para_apoio(solicitacao)

    if request.method == "POST":
        unidade_destino = get_object_or_404(Unidade, pk=request.POST.get("unidade_destino"), ativo=True, tipo="ESPECIALIZADA")
        if unidade_destino.pk == solicitacao.unidade_id:
            messages.error(request, "A unidade de apoio deve ser diferente da unidade responsável pelo evento.")
            return render(request, "gestao/enviar_apoio.html", {"solicitacao": solicitacao, "opo": opo, "unidades": unidades})

        apoio = ApoioEvento.objects.filter(solicitacao=solicitacao, unidade_destino=unidade_destino).first()
        if apoio and apoio.status != "OPO_GERADA":
            messages.warning(request, f"O apoio para {unidade_destino.sigla} já foi enviado.")
            return redirect("detalhe_opo", id=id)

        with transaction.atomic():
            apoio, criado = ApoioEvento.objects.update_or_create(
                solicitacao=solicitacao,
                unidade_destino=unidade_destino,
                defaults={
                    "unidade_origem": solicitacao.unidade,
                    "enviado_por": request.user,
                    "status": "ENVIADO",
                    "observacao": (request.POST.get("observacao") or "").strip(),
                },
            )
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao,
                usuario=request.user,
                acao="APOIO ENVIADO",
                status=solicitacao.status,
                observacao=f"Pacote de apoio enviado para {unidade_destino.sigla}. Documentação original e OPO principal permanecem vinculadas ao protocolo.",
            )

        # A unidade destinatária recebe uma notificação, quando houver e-mail cadastrado.
        if unidade_destino.email:
            link = request.build_absolute_uri(reverse("apoios_recebidos"))
            try:
                send_mail(
                    subject=f"Apoio operacional recebido — OPO {solicitacao.protocolo}",
                    message=(
                        f"A unidade {unidade_destino.sigla} recebeu um apoio operacional para o evento "
                        f"{solicitacao.nome_evento} ({solicitacao.data_evento:%d/%m/%Y}).\n\n"
                        f"O pacote contém acesso à documentação original e à OPO principal.\n"
                        f"Acesse o SiEv para analisar e, se necessário, gerar a OPO própria da unidade:\n{link}"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[unidade_destino.email],
                    fail_silently=False,
                )
                messages.success(request, f"Apoio enviado para {unidade_destino.sigla} e unidade notificada por e-mail.")
            except Exception:
                messages.warning(request, f"Apoio enviado para {unidade_destino.sigla}. O e-mail de notificação não pôde ser enviado.")
        else:
            messages.success(request, f"Apoio enviado para {unidade_destino.sigla}.")

        return redirect("detalhe_opo", id=id)

    return render(request, "gestao/enviar_apoio.html", {"solicitacao": solicitacao, "opo": opo, "unidades": unidades})


@login_required
def apoios_recebidos(request):
    a = _acesso(request)
    if not (eh_desenvolvedor(request.user) or (a and a.ativo and request.user.is_active and a.funcao == "GESTOR" and a.perfil == "UNIDADE" and a.unidade_id)):
        messages.error(request, "A área de apoios é exclusiva dos gestores das unidades destinatárias.")
        return redirect("painel_gestao")

    qs = ApoioEvento.objects.select_related(
        "solicitacao", "solicitacao__municipio", "solicitacao__bairro",
        "unidade_origem", "unidade_destino"
    )
    if not eh_desenvolvedor(request.user):
        qs = qs.filter(unidade_destino_id=a.unidade_id)

    return render(request, "gestao/apoios_recebidos.html", {"apoios": qs})


@login_required
def abrir_apoio(request, id):
    apoio = get_object_or_404(
        ApoioEvento.objects.select_related("solicitacao", "solicitacao__unidade", "unidade_destino", "unidade_origem"),
        pk=id,
    )
    if not (eh_desenvolvedor(request.user) or _eh_gestor_unidade_do(request, apoio.unidade_destino)):
        messages.error(request, "Você não possui acesso a este apoio.")
        return redirect("apoios_recebidos")

    if request.method == "POST" and apoio.status == "ENVIADO":
        apoio.status = "RECEBIDO"
        apoio.save(update_fields=["status", "atualizado_em"])
        HistoricoSolicitacao.objects.create(
            solicitacao=apoio.solicitacao,
            usuario=request.user,
            acao="APOIO RECEBIDO",
            status=apoio.solicitacao.status,
            observacao=f"Apoio recebido pela {apoio.unidade_destino.sigla}.",
        )
        messages.success(request, "Apoio marcado como recebido.")
        return redirect("abrir_apoio", id=id)

    docs = apoio.solicitacao.documentos.select_related("tipo_documento").all()
    opos = apoio.solicitacao.opos.order_by("-criado_em")
    return render(request, "gestao/abrir_apoio.html", {"apoio": apoio, "documentos": docs, "opos": opos})


@login_required
def gerar_opo_apoio(request, id):
    apoio = get_object_or_404(
        ApoioEvento.objects.select_related("solicitacao", "unidade_destino", "unidade_origem"),
        pk=id,
    )
    if not (eh_desenvolvedor(request.user) or _eh_gestor_unidade_do(request, apoio.unidade_destino)):
        messages.error(request, "Somente o gestor da unidade destinatária pode gerar a OPO própria de apoio.")
        return redirect("apoios_recebidos")

    if not apoio.solicitacao.documentos.exists() or not apoio.solicitacao.opos.exists():
        messages.error(request, "O apoio precisa ter a documentação original e a OPO principal disponíveis.")
        return redirect("abrir_apoio", id=id)

    if request.method == "GET":
        return render(request, "gestao/gerar_opo_apoio.html", {"apoio": apoio})

    base_opo = apoio.solicitacao.opos.order_by("-criado_em").first()
    evento_extra = bool(base_opo and "Evento extra: SIM" in (base_opo.descricao or ""))
    conteudo = _pdf_opo(apoio.solicitacao, evento_extra=evento_extra, unidade_executor=apoio.unidade_destino)
    nome = f"OPO_APOIO_{apoio.solicitacao.protocolo}_{apoio.unidade_destino.sigla}.pdf"
    apoio.opo_arquivo.save(nome, ContentFile(conteudo), save=False)
    apoio.status = "OPO_GERADA"
    apoio.save(update_fields=["opo_arquivo", "status", "atualizado_em"])

    HistoricoSolicitacao.objects.create(
        solicitacao=apoio.solicitacao,
        usuario=request.user,
        acao="OPO DE APOIO GERADA",
        status=apoio.solicitacao.status,
        observacao=f"{apoio.unidade_destino.sigla} gerou sua própria OPO para o evento.",
    )
    messages.success(request, f"OPO própria da {apoio.unidade_destino.sigla} gerada com sucesso.")
    return redirect("abrir_apoio", id=id)
