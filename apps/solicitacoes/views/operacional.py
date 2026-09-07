"""Camada de compatibilidade das views operacionais antigas.

As rotas novas usam views segmentadas/seguras. Este módulo mantém os nomes
históricos importados por compat.py sem duplicar a implementação.
"""

from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from apps.solicitacoes.forms import SolicitacaoManualForm
from apps.solicitacoes.models import Bairro, Municipio, TipoEvento, Unidade


class GestaoManualForm(SolicitacaoManualForm):
    """Formulário de lançamento manual com escopo territorial da unidade."""

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


def _delegar(nome, modulo, request, *args, **kwargs):
    func = getattr(__import__(modulo, fromlist=[nome]), nome)
    return func(request, *args, **kwargs)


def lancamento_manual(request, *args, **kwargs):
    from .manual import lancamento_manual as view
    return view(request, *args, **kwargs)


def documentos_solicitacao(request, id, *args, **kwargs):
    from .escopo_gestao import documentos_solicitacao_seguro
    return documentos_solicitacao_seguro(request, id, *args, **kwargs)


def abrir_documento_solicitacao(request, id, tipo="arquivo", *args, **kwargs):
    from .escopo_gestao import abrir_documento_solicitacao_seguro
    return abrir_documento_solicitacao_seguro(request, id, tipo=tipo, *args, **kwargs)


def opos_geradas(request, *args, **kwargs):
    from .escopo_gestao import opos_geradas_seguro
    return opos_geradas_seguro(request, *args, **kwargs)


def detalhe_opo(request, id, *args, **kwargs):
    from .escopo_gestao import detalhe_opo_seguro
    return detalhe_opo_seguro(request, id, *args, **kwargs)


def gerar_opo(request, id, *args, **kwargs):
    from .escopo_gestao import gerar_opo_seguro
    return gerar_opo_seguro(request, id, *args, **kwargs)


def mapa_eventos(request, *args, **kwargs):
    from .escopo_gestao import mapa_eventos_seguro
    return mapa_eventos_seguro(request, *args, **kwargs)


def gerar_mapa_eventos_pdf(request, *args, **kwargs):
    from .mapa_eventos_pdf import gerar_mapa_eventos_pdf_seguro
    return gerar_mapa_eventos_pdf_seguro(request, *args, **kwargs)


def validar_matricula_opo_publica(request, id, *args, **kwargs):
    from .public_opo import validar_matricula_opo_publica as view
    return view(request, id, *args, **kwargs)


def detalhe_opo_publica(request, id, *args, **kwargs):
    from .public_opo import detalhe_opo_publica as view
    return view(request, id, *args, **kwargs)


def importar_matriculas_painel(request, *args, **kwargs):
    """Compatibilidade: a administração atual não usa mais esta rota antiga."""
    return redirect("painel_gestao")


@login_required
def importar_municipios(request, *args, **kwargs):
    """Compatibilidade: cadastro de municípios foi retirado do painel."""
    return redirect("painel_gestao")


@login_required
def verificar_autenticidade(request, protocolo, *args, **kwargs):
    """Compatibilidade para QR/links antigos; encaminha para a consulta pública."""
    return redirect(f"/consultar/?protocolo={protocolo}")


__all__ = [
    "GestaoManualForm",
    "lancamento_manual",
    "documentos_solicitacao",
    "abrir_documento_solicitacao",
    "opos_geradas",
    "detalhe_opo",
    "gerar_opo",
    "mapa_eventos",
    "gerar_mapa_eventos_pdf",
    "validar_matricula_opo_publica",
    "detalhe_opo_publica",
    "importar_matriculas_painel",
    "importar_municipios",
    "verificar_autenticidade",
]
