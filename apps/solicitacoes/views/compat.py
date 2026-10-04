"""Compatibilidade das rotas antigas com as views atuais segmentadas."""

import csv
import io

import openpyxl
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.solicitacoes.models import HistoricoSolicitacao, MatriculaAutorizada, Municipio, Solicitacao

from .manual import lancamento_manual
from .minhas import minhas_solicitacoes
from .public_opo import detalhe_opo_publica, validar_matricula_opo_publica


@login_required
def verificar_autenticidade(request, protocolo):
    solicitacao = get_object_or_404(Solicitacao, protocolo=protocolo)
    return render(request, "gestao/verificar_autenticidade.html", {"solicitacao": solicitacao})


@login_required
def alterar_status(request, id, status):
    solicitacao = get_object_or_404(Solicitacao, pk=id)
    permitidos = {"PENDENTE", "EM_ANALISE", "CORRECAO", "APROVADA", "REJEITADA", "CONCLUIDA"}
    if status not in permitidos:
        messages.error(request, "Status inválido.")
        return redirect("painel_gestao")
    solicitacao.status = status
    if status in {"APROVADA", "REJEITADA", "CONCLUIDA"}:
        solicitacao.data_aprovacao = timezone.now()
    solicitacao.save()
    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao=f"STATUS: {status}",
        detalhes="Alteração realizada pelo painel institucional.",
    )
    messages.success(request, "Status atualizado.")
    return redirect("painel_gestao")


@login_required
def importar_matriculas_painel(request):
    if request.method == "POST":
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            messages.error(request, "Selecione uma planilha Excel.")
            return redirect("importar_matriculas_painel")
        if arquivo.size > 5 * 1024 * 1024:
            messages.error(request, "A planilha deve ter no máximo 5 MB.")
            return redirect("importar_matriculas_painel")
        try:
            workbook = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
            sheet = workbook.active
            linhas = list(sheet.iter_rows(values_only=True))
            if not linhas:
                raise ValueError("A planilha está vazia.")
            def normalizar(valor):
                return "".join(ch for ch in str(valor or "").strip().lower() if ch.isalnum())
            cabecalho = {normalizar(v): i for i, v in enumerate(linhas[0])}
            indices = {}
            for campo, alternativas in {
                "matricula": ["matricula", "matrícula"],
                "nome": ["nome"],
                "posto": ["posto", "postograduacao", "posto/graduação"],
                "unidade": ["unidade", "sigla"],
            }.items():
                for alternativa in alternativas:
                    chave = normalizar(alternativa)
                    if chave in cabecalho:
                        indices[campo] = cabecalho[chave]
                        break
            if "matricula" not in indices or "nome" not in indices:
                raise ValueError("A planilha precisa conter as colunas Matrícula e Nome.")
            inseridos = atualizados = 0
            for linha in linhas[1:]:
                matricula = str(linha[indices["matricula"]] or "").strip()
                nome = str(linha[indices["nome"]] or "").strip()
                if not matricula or not nome:
                    continue
                posto = str(linha[indices["posto"]] or "").strip() if "posto" in indices else ""
                unidade = str(linha[indices["unidade"]] or "").strip() if "unidade" in indices else ""
                _, criado = MatriculaAutorizada.objects.update_or_create(
                    matricula=matricula,
                    defaults={"nome": nome, "posto": posto, "unidade": unidade, "ativo": True},
                )
                if criado:
                    inseridos += 1
                else:
                    atualizados += 1
            workbook.close()
            messages.success(request, f"Importação concluída: {inseridos} novas e {atualizados} atualizadas.")
        except Exception as exc:
            messages.error(request, f"Não foi possível importar a planilha: {exc}")
        return redirect("importar_matriculas_painel")
    total = MatriculaAutorizada.objects.filter(ativo=True).count()
    return render(request, "gestao/importar_matriculas.html", {"total_matriculas": total})


@login_required
def importar_municipios(request):
    if request.method != "POST":
        return render(request, "gestao/importar_municipios.html")
    arquivo = request.FILES.get("arquivo")
    if not arquivo or arquivo.size > 5 * 1024 * 1024:
        messages.error(request, "Selecione um CSV de até 5 MB.")
        return redirect("importar_municipios")
    try:
        texto = arquivo.read().decode("utf-8-sig")
        leitor = csv.DictReader(io.StringIO(texto))
        total = 0
        for linha in leitor:
            nome = (linha.get("municipio") or linha.get("Município") or linha.get("nome") or "").strip()
            if nome:
                Municipio.objects.get_or_create(nome=nome, defaults={"ativo": True})
                total += 1
        messages.success(request, f"{total} municípios processados.")
    except Exception as exc:
        messages.error(request, f"Importação não realizada: {exc}")
    return redirect("importar_municipios")
