from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.solicitacoes.forms import CorrecaoSolicitacaoForm
from apps.solicitacoes.models import HistoricoSolicitacao, Solicitacao
from apps.solicitacoes.portal_views import _salvar_documentos


CAMPOS_NAO_EDITAVEIS_CORRECAO = {
    "data_evento",
    "municipio",
    "unidade",
    "bairro",
    "tipo_evento",
    "origem",
    "publico_estimado",
}


def _preparar_form_correcao(*args, **kwargs):
    """Mantém no formulário apenas os campos que o solicitante pode corrigir."""
    form = CorrecaoSolicitacaoForm(*args, **kwargs)
    for nome in CAMPOS_NAO_EDITAVEIS_CORRECAO:
        form.fields.pop(nome, None)
    return form


def _escopo_gestor(request):
    if request.user.is_superuser or request.user.is_staff:
        return Solicitacao.objects.all()

    perfil = getattr(request.user, "perfil_siev", None)
    if not perfil or not perfil.ativo:
        return Solicitacao.objects.none()

    if perfil.perfil == "COPPM":
        return Solicitacao.objects.all()
    if perfil.perfil == "CPR" and perfil.cpr_id:
        return Solicitacao.objects.filter(unidade__cpr_id=perfil.cpr_id)
    if perfil.perfil == "UNIDADE" and perfil.unidade_id:
        return Solicitacao.objects.filter(unidade_id=perfil.unidade_id)

    return Solicitacao.objects.none()


@login_required
def solicitar_correcao_gestao(request, id):
    escopo = _escopo_gestor(request)
    solicitacao = get_object_or_404(
        escopo.select_related("unidade"),
        pk=id,
    )

    if solicitacao.status != "PENDENTE":
        messages.error(
            request,
            "Esta solicitação não está pendente de análise.",
        )
        return redirect("aprovacoes")

    if request.method == "POST":
        motivo = request.POST.get("motivo_correcao", "").strip()

        if not motivo:
            messages.error(request, "Informe o motivo da correção.")
            return render(
                request,
                "solicitacoes/solicitar_correcao.html",
                {"solicitacao": solicitacao},
            )

        solicitacao.status = "CORRECAO"
        solicitacao.save(update_fields=["status", "atualizado_em"])

        HistoricoSolicitacao.objects.create(
            solicitacao=solicitacao,
            usuario=request.user,
            status="CORRECAO",
            status_anterior="PENDENTE",
            status_novo="CORRECAO",
            acao="CORREÇÃO SOLICITADA",
            observacao=motivo,
        )

        link_correcao = request.build_absolute_uri(
            reverse(
                "corrigir_solicitacao",
                kwargs={"protocolo": solicitacao.protocolo},
            )
        )

        mensagem = f"""Olá, {solicitacao.solicitante}!

Sua solicitação de policiamento necessita de correção.

PROTOCOLO:
{solicitacao.protocolo}

EVENTO:
{solicitacao.nome_evento}

MOTIVO DA CORREÇÃO:
{motivo}

Para realizar a correção, acesse diretamente:
{link_correcao}

Depois de corrigir e reenviar, a solicitação voltará para análise da unidade responsável.

Atenciosamente,

Seção de Planejamento Operacional
SiEv - Sistema Inteligente de Eventos
"""

        try:
            send_mail(
                subject="Pendência na Solicitação de Ordem de Policiamento - SiEv",
                message=mensagem,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[solicitacao.email],
                fail_silently=False,
            )
            messages.success(
                request,
                "Solicitação devolvida para correção e e-mail enviado ao solicitante.",
            )
        except Exception as erro:
            print("ERRO AO ENVIAR EMAIL DE CORREÇÃO:", repr(erro))
            messages.warning(
                request,
                "Solicitação devolvida para correção, mas o e-mail não pôde ser enviado.",
            )

        return redirect("aprovacoes")

    return render(
        request,
        "solicitacoes/solicitar_correcao.html",
        {"solicitacao": solicitacao},
    )


def corrigir_solicitacao_publica(request, protocolo):
    solicitacao = get_object_or_404(
        Solicitacao,
        protocolo=protocolo,
    )

    if solicitacao.status != "CORRECAO":
        messages.error(
            request,
            "Esta solicitação não está disponível para correção.",
        )
        return redirect(f"{reverse('consultar')}?protocolo={solicitacao.protocolo}")

    if request.method == "POST":
        form = _preparar_form_correcao(
            request.POST,
            request.FILES,
            instance=solicitacao,
        )

        if form.is_valid():
            protocolo_original = solicitacao.protocolo
            data_original = solicitacao.data_evento
            unidade_original = solicitacao.unidade
            municipio_original = solicitacao.municipio
            bairro_original = solicitacao.bairro
            tipo_evento_original = solicitacao.tipo_evento
            usuario_original = solicitacao.usuario
            origem_original = solicitacao.origem

            obj = form.save(commit=False)
            obj.protocolo = protocolo_original
            obj.data_evento = data_original
            obj.unidade = unidade_original
            obj.municipio = municipio_original
            obj.bairro = bairro_original
            obj.tipo_evento = tipo_evento_original
            obj.usuario = usuario_original
            obj.origem = origem_original
            obj.status = "PENDENTE"
            obj.save()

            _salvar_documentos(request, obj)

            HistoricoSolicitacao.objects.create(
                solicitacao=obj,
                usuario=None,
                status="PENDENTE",
                status_anterior="CORRECAO",
                status_novo="PENDENTE",
                acao="CORREÇÃO REENVIADA",
                observacao="Solicitação corrigida e reenviada pelo solicitante.",
            )

            link_consulta = request.build_absolute_uri(
                f"{reverse('consultar')}?protocolo={obj.protocolo}"
            )

            mensagem = f"""Olá, {obj.solicitante}!

Sua solicitação foi corrigida e reenviada para análise.

PROTOCOLO:
{obj.protocolo}

EVENTO:
{obj.nome_evento}

DATA:
{obj.data_evento.strftime('%d/%m/%Y')}

STATUS:
Aguardando nova análise

Acompanhe a solicitação pelo link:
{link_consulta}

Atenciosamente,

Seção de Planejamento Operacional
SiEv - Sistema Inteligente de Eventos
"""

            try:
                send_mail(
                    subject="Solicitação corrigida e reenviada - SiEv",
                    message=mensagem,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[obj.email],
                    fail_silently=False,
                )
            except Exception as erro:
                print("ERRO AO ENVIAR EMAIL DE REENVIO:", repr(erro))

            messages.success(
                request,
                "Correções enviadas com sucesso. Sua solicitação será analisada novamente.",
            )
            return redirect(f"{reverse('consultar')}?protocolo={obj.protocolo}")
    else:
        form = _preparar_form_correcao(instance=solicitacao)

    return render(
        request,
        "solicitacoes/corrigir.html",
        {"form": form, "solicitacao": solicitacao},
    )
