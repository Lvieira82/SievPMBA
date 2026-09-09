import re
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.solicitacoes.models import HistoricoSolicitacao, Unidade
from apps.solicitacoes.permissoes import perfil_gestor


MARCADOR_ENVIO = "PESQUISA DE SATISFAÇÃO ENVIADA"
MARCADOR_RESPOSTA = "PESQUISA RESPONDIDA"


def _extrair_resposta(observacao):
    texto = observacao or ""
    nota = None
    comentario = ""
    match = re.search(r"Nota:\s*(\d+)\s*/\s*5", texto, re.I)
    if match:
        valor = int(match.group(1))
        if 1 <= valor <= 5:
            nota = valor
    match = re.search(r"Comentário:\s*(.*)$", texto, re.I | re.S)
    if match:
        comentario = match.group(1).strip()
        if comentario.lower() == "sem comentário.":
            comentario = ""
    return nota, comentario


@login_required
def painel_pesquisas(request):
    if not perfil_gestor(request.user, "COPPM"):
        messages.error(request, "Somente o Gestor COPPM pode acessar o painel de pesquisas.")
        return redirect("painel_gestao")

    inicio = request.GET.get("inicio", "")
    fim = request.GET.get("fim", "")
    unidade_id = request.GET.get("unidade", "")

    base = HistoricoSolicitacao.objects.filter(
        acao__in=[MARCADOR_ENVIO, MARCADOR_RESPOSTA]
    ).select_related("solicitacao", "solicitacao__unidade")

    if inicio:
        try:
            base = base.filter(solicitacao__data_evento__gte=datetime.strptime(inicio, "%Y-%m-%d").date())
        except ValueError:
            inicio = ""
    if fim:
        try:
            base = base.filter(solicitacao__data_evento__lte=datetime.strptime(fim, "%Y-%m-%d").date())
        except ValueError:
            fim = ""
    if unidade_id:
        try:
            base = base.filter(solicitacao__unidade_id=int(unidade_id))
        except (TypeError, ValueError):
            unidade_id = ""

    envios = list(base.filter(acao=MARCADOR_ENVIO).order_by("-criado_em"))
    respostas = list(base.filter(acao=MARCADOR_RESPOSTA).order_by("-criado_em"))

    resposta_por_solicitacao = {}
    for item in respostas:
        resposta_por_solicitacao.setdefault(item.solicitacao_id, item)

    registros = []
    notas = []
    distribuicao = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    comentarios = []

    for envio in envios:
        resposta = resposta_por_solicitacao.get(envio.solicitacao_id)
        nota = comentario = None
        respondida_em = None
        if resposta:
            nota, comentario = _extrair_resposta(resposta.observacao)
            respondida_em = resposta.criado_em
            if nota:
                notas.append(nota)
                distribuicao[nota] += 1
            if comentario:
                comentarios.append({
                    "nome": resposta.solicitacao.solicitante,
                    "evento": resposta.solicitacao.nome_evento,
                    "comentario": comentario,
                    "data": resposta.criado_em,
                    "nota": nota,
                })
        registros.append({
            "solicitacao": envio.solicitacao,
            "enviado_em": envio.criado_em,
            "respondida": bool(resposta),
            "nota": nota,
            "respondida_em": respondida_em,
        })

    total_enviadas = len(envios)
    total_respondidas = sum(1 for envio in envios if envio.solicitacao_id in resposta_por_solicitacao)
    total_pendentes = max(0, total_enviadas - total_respondidas)
    total_avaliacoes = len(notas)
    participacao = (total_respondidas / total_enviadas * 100) if total_enviadas else 0
    media = (sum(notas) / total_avaliacoes) if total_avaliacoes else 0
    satisfacao = (media / 5 * 100) if media else 0

    return render(request, "gestao/pesquisas.html", {
        "total_enviadas": total_enviadas,
        "total_respondidas": total_respondidas,
        "total_pendentes": total_pendentes,
        "total_avaliacoes": total_avaliacoes,
        "participacao": round(participacao, 1),
        "media": round(media, 2),
        "satisfacao": round(satisfacao, 1),
        "distribuicao": distribuicao,
        "comentarios": comentarios[:30],
        "registros": registros,
        "unidades": Unidade.objects.filter(ativo=True).order_by("sigla"),
        "inicio": inicio,
        "fim": fim,
        "unidade_id": unidade_id,
        "ultima_atualizacao": timezone.localtime(),
    })
