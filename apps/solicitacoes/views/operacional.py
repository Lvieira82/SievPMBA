import csv
import io
from datetime import timedelta

import openpyxl
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django import forms

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from apps.solicitacoes.forms import SolicitacaoManualForm
from apps.solicitacoes.models import (
    AnexoOPO,
    Bairro,
    DocumentoSolicitacao,
    HistoricoSolicitacao,
    MatriculaAutorizada,
    Municipio,
    PerfilUsuario,
    Solicitacao,
    TipoDocumento,
    TipoEvento,
    Unidade,
)
from apps.solicitacoes.pdf_security import validar_pdf_upload


class GestaoManualForm(SolicitacaoManualForm):
    """Formulário manual com os dados territoriais definidos pelo usuário da unidade."""

    def __init__(self, *args, perfil=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perfil_gestor = perfil

        self.fields["municipio"] = forms.ModelChoiceField(
            queryset=Municipio.objects.filter(ativo=True).order_by("nome"),
            required=True,
            label="Município",
            widget=forms.Select(attrs={"class": "form-select"}),
        )
        self.fields["bairro"] = forms.ModelChoiceField(
            queryset=Bairro.objects.none(),
            required=False,
            label="Bairro / Distrito",
            widget=forms.Select(attrs={"class": "form-select"}),
        )
        self.fields["tipo_evento"] = forms.ModelChoiceField(
            queryset=TipoEvento.objects.filter(
                nome__in=["ORDINÁRIO", "EXTRAORDINÁRIO"],
                ativo=True,
            ).order_by("nome"),
            required=True,
            label="Tipo de evento",
            empty_label="Selecione o tipo de evento",
            widget=forms.Select(attrs={"class": "form-select"}),
        )

        if perfil and perfil.unidade_id:
            unidades = Unidade.objects.filter(pk=perfil.unidade_id, ativo=True)
        elif perfil and perfil.cpr_id:
            unidades = Unidade.objects.filter(cpr_id=perfil.cpr_id, ativo=True).order_by("nome")
        else:
            unidades = Unidade.objects.filter(ativo=True).order_by("nome")

        self.fields["unidade"] = forms.ModelChoiceField(
            queryset=unidades,
            required=True,
            label="Unidade responsável",
            widget=forms.Select(attrs={"class": "form-select"}),
        )

        if self.instance and self.instance.pk:
            self.fields["municipio"].initial = self.instance.municipio_id
            self.fields["bairro"].initial = self.instance.bairro_id
            self.fields["tipo_evento"].initial = self.instance.tipo_evento_id
            self.fields["unidade"].initial = self.instance.unidade_id

    def clean_bairro(self):
        bairro = self.cleaned_data.get("bairro")
        municipio = self.cleaned_data.get("municipio")
        if bairro and municipio and bairro.municipio_id != municipio.id:
            raise forms.ValidationError("O bairro selecionado não pertence ao município.")
        return bairro


@login_required
def lancamento_manual(request):
    perfil = getattr(request.user, "perfil_siev", None)
    protocolo = request.GET.get("protocolo_origem", "").strip().upper()
    original = Solicitacao.objects.filter(protocolo=protocolo).first() if protocolo else None

    if protocolo and not original:
        messages.error(request, "Protocolo não encontrado.")

    if request.method == "POST":
        protocolo = request.POST.get("protocolo_origem", "").strip().upper()
        original = Solicitacao.objects.filter(protocolo=protocolo).first() if protocolo else None
        form = GestaoManualForm(request.POST, request.FILES, instance=original, perfil=perfil)

        if form.is_valid():
            obj = form.save(commit=False)
            obj.usuario = request.user
            obj.municipio = form.cleaned_data["municipio"]
            obj.bairro = form.cleaned_data.get("bairro")
            obj.tipo_evento = form.cleaned_data["tipo_evento"]
            obj.unidade = form.cleaned_data["unidade"]
            obj.origem = "MANUAL"
            obj.status = "PENDENTE"
            obj.save()

            HistoricoSolicitacao.objects.create(
                solicitacao=obj,
                usuario=request.user,
                acao="LANÇAMENTO MANUAL",
                detalhes="Solicitação criada/atualizada pelo módulo de lançamento manual.",
            )

            messages.success(request, f"Informação salva com o protocolo {obj.protocolo}.")
            return redirect("documentos_solicitacao", id=obj.id)
    else:
        form = GestaoManualForm(instance=original, perfil=perfil)

    return render(
        request,
        "gestao/lancamento_manual.html",
        {
            "form": form,
            "solicitacao_original": original,
            "protocolo_origem": protocolo,
        },
    )


@login_required
def documentos_solicitacao(request, id):
    solicitacao = get_object_or_404(
        Solicitacao.objects.select_related("municipio", "bairro", "unidade"),
        pk=id,
    )
    documentos = DocumentoSolicitacao.objects.filter(solicitacao=solicitacao).select_related("tipo_documento")
    tipos = TipoDocumento.objects.filter(ativo=True).order_by("nome")

    if request.method == "POST":
        arquivo = request.FILES.get("arquivo")
        tipo_id = request.POST.get("tipo_documento")
        descricao = request.POST.get("descricao", "").strip()

        if not arquivo or not tipo_id:
            messages.error(request, "Informe o PDF e o tipo do documento.")
        else:
            try:
                validar_pdf_upload(arquivo)
                tipo = get_object_or_404(TipoDocumento, pk=tipo_id, ativo=True)
                DocumentoSolicitacao.objects.create(
                    solicitacao=solicitacao,
                    tipo_documento=tipo,
                    descricao=descricao,
                    arquivo=arquivo,
                )
                messages.success(request, "Documento anexado com sucesso.")
                return redirect("documentos_solicitacao", id=id)
            except Exception as exc:
                messages.error(request, f"Documento rejeitado: {exc}")

    return render(
        request,
        "gestao/documentos_solicitacao.html",
        {"solicitacao": solicitacao, "documentos": documentos, "tipos_documento": tipos},
    )
