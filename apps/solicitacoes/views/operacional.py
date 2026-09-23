"""Camada de compatibilidade das views operacionais antigas.

As rotas novas usam views segmentadas/seguras. Este módulo mantém os nomes
históricos importados por compat.py sem duplicar a implementação.
"""

from django import forms


class MunicipioPorUnidadeSelect(forms.Select):
    """Select que expõe a unidade responsável de cada município para o filtro dinâmico."""
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-unidade-id"] = str(instance.unidade_responsavel_id or "")
        return option


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect
from django.utils import timezone

from apps.solicitacoes.forms import SolicitacaoManualForm
from apps.solicitacoes.models import Bairro, HistoricoSolicitacao, MatriculaAutorizada, Municipio, Solicitacao, TipoEvento, Unidade


class GestaoManualForm(SolicitacaoManualForm):
    """Formulário de lançamento manual com escopo territorial da unidade."""

    oficio_origem = forms.FileField(
        label="Ofício de origem (PDF)",
        required=False,
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".pdf,application/pdf",
        }),
    )

    def __init__(self, *args, perfil=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perfil_gestor = perfil

        # No lançamento manual, o Ofício ao Comandante não é utilizado.
        # O documento anexado neste fluxo é o Ofício de origem.
        self.fields.pop("oficio_comandante", None)

        self.fields["municipio"] = forms.ModelChoiceField(
            queryset=Municipio.objects.filter(ativo=True).order_by("nome"),
            required=True,
            label="Município",
            widget=MunicipioPorUnidadeSelect(attrs={"class": "form-select", "data-filtro-unidade": "1"}),
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

        # O efetivo institucional é montado a partir das matrículas cadastradas
        # e vinculadas à unidade responsável.
        self.fields["efetivo_institucional"] = forms.CharField(
            required=False,
            max_length=250,
            widget=forms.HiddenInput(),
        )

        tipo_opo_inicial = (
            (self.data.get("tipo_opo") if self.is_bound else None)
            or (self.instance.tipo_opo if getattr(self.instance, "pk", None) else None)
            or "FESTIVO"
        )

        self.fields["tipo_opo"] = forms.ChoiceField(
            required=False,
            initial="FESTIVO",
            label="Tipo de OPO",
            choices=Solicitacao.TIPO_OPO_CHOICES,
            widget=forms.Select(attrs={"class": "tipo-opo-toggle"}),
            help_text="Selecione Institucional somente para o lançamento interno de operações institucionais.",
        )

        if tipo_opo_inicial == "INSTITUCIONAL":
            for campo in ("cpf", "email", "telefone"):
                if campo in self.fields:
                    self.fields[campo].required = False
                    self.fields[campo].initial = ""

        self.fields["opo_permanente"] = forms.BooleanField(
            required=False,
            initial=False,
            label="OPO permanente",
            help_text="Use para operações especiais que permanecem válidas por mais de um dia sem gerar novos protocolos.",
            widget=forms.CheckboxInput(attrs={"class": "opo-permanente-toggle"}),
        )
        self.fields["opo_permanente_data_fim"] = forms.DateField(
            required=False,
            label="Data de fim da OPO permanente",
            widget=forms.DateInput(attrs={"type": "date", "class": "opo-permanente-data-fim"}),
        )
        self.fields["opo_permanente_indeterminado"] = forms.BooleanField(
            required=False,
            initial=False,
            label="Indeterminado",
            help_text="Marque quando não houver previsão de encerramento.",
            widget=forms.CheckboxInput(attrs={"class": "opo-permanente-indeterminado"}),
        )

        if perfil and perfil.unidade_id:
            unidades = Unidade.objects.filter(pk=perfil.unidade_id, ativo=True)
        elif perfil and perfil.cpr_id:
            unidades = Unidade.objects.filter(cpr_id=perfil.cpr_id, ativo=True).order_by("nome")
        else:
            unidades = Unidade.objects.filter(ativo=True).order_by("nome")

        unidade_para_matriculas = None
        if self.is_bound:
            unidade_para_matriculas = self.data.get(self.add_prefix("unidade"))
        elif perfil and perfil.unidade_id:
            unidade_para_matriculas = perfil.unidade_id
        elif self.instance and self.instance.pk:
            unidade_para_matriculas = self.instance.unidade_id

        opcoes_matriculas = []
        if unidade_para_matriculas:
            try:
                unidade_id_matriculas = int(unidade_para_matriculas)
            except (TypeError, ValueError):
                unidade_id_matriculas = None
            if unidade_id_matriculas:
                opcoes_matriculas = [
                    (str(m.matricula), f"{m.matricula} — {m.posto} {m.nome}".strip())
                    for m in MatriculaAutorizada.objects.filter(
                        unidade_id=unidade_id_matriculas,
                        ativo=True,
                    ).order_by("nome")
                ]

        self.fields["matriculas_institucionais"] = forms.MultipleChoiceField(
            required=False,
            label="Efetivo",
            choices=opcoes_matriculas,
            widget=forms.SelectMultiple(attrs={"class": "matriculas-institucionais", "size": "1"}),
            help_text="Selecione um policial e use + Adicionar outro policial para incluir quantos forem necessários.",
        )

        self.fields["unidade"] = forms.ModelChoiceField(
            queryset=unidades,
            required=True,
            label="Unidade responsável",
            widget=forms.Select(attrs={"class": "form-select"}),
        )

        # O município deve pertencer à unidade responsável selecionada.
        unidade_selecionada = None
        if self.is_bound:
            unidade_selecionada = self.data.get(self.add_prefix("unidade"))
        elif perfil and perfil.unidade_id:
            unidade_selecionada = perfil.unidade_id
        elif self.instance and self.instance.pk:
            unidade_selecionada = self.instance.unidade_id

        if unidade_selecionada:
            try:
                unidade_id = int(unidade_selecionada)
            except (TypeError, ValueError):
                unidade_id = None
            if unidade_id:
                unidade_obj = Unidade.objects.filter(pk=unidade_id, ativo=True).first()
                sede_nome = ""
                if unidade_obj:
                    texto_unidade = (unidade_obj.nome or unidade_obj.sigla or "").strip()
                    if "/" in texto_unidade:
                        sede_nome = texto_unidade.rsplit("/", 1)[-1].strip()

                filtro = Q(unidade_responsavel_id=unidade_id)
                if sede_nome:
                    filtro |= Q(nome__iexact=sede_nome)

                self.fields["municipio"].queryset = Municipio.objects.filter(
                    Q(ativo=True) & filtro,
                ).order_by("nome")

        if self.instance and self.instance.pk:
            self.fields["municipio"].initial = self.instance.municipio_id
            self.fields["bairro"].initial = self.instance.bairro_id
            self.fields["tipo_evento"].initial = self.instance.tipo_evento_id
            self.fields["unidade"].initial = self.instance.unidade_id
            self.fields["tipo_opo"].initial = self.instance.tipo_opo
            matriculas_atuais = [item.strip() for item in (self.instance.efetivo_institucional or "").split("\n") if item.strip()]
            self.fields["matriculas_institucionais"].initial = [
                item.split(" — ", 1)[0].strip() for item in matriculas_atuais
            ]
            self.fields["efetivo_institucional"].initial = self.instance.efetivo_institucional
            self.fields["opo_permanente"].initial = self.instance.opo_permanente
            self.fields["opo_permanente_data_fim"].initial = self.instance.opo_permanente_data_fim
            self.fields["opo_permanente_indeterminado"].initial = self.instance.opo_permanente_indeterminado

    def clean_municipio(self):
        municipio = self.cleaned_data.get("municipio")
        unidade = self.cleaned_data.get("unidade")
        if municipio and unidade:
            pertence_unidade = municipio.unidade_responsavel_id == unidade.id
            sede_nome = ""
            texto_unidade = (unidade.nome or unidade.sigla or "").strip()
            if "/" in texto_unidade:
                sede_nome = texto_unidade.rsplit("/", 1)[-1].strip()
            eh_sede = bool(sede_nome and municipio.nome.strip().casefold() == sede_nome.casefold())
            if not pertence_unidade and not eh_sede:
                raise forms.ValidationError("O município selecionado não pertence à unidade responsável nem corresponde à cidade sede da unidade.")
        return municipio

    def clean_bairro(self):
        bairro = self.cleaned_data.get("bairro")
        municipio = self.cleaned_data.get("municipio")
        if bairro and municipio and bairro.municipio_id != municipio.id:
            raise forms.ValidationError("O bairro selecionado não pertence ao município.")
        return bairro

    def clean(self):
        cleaned_data = super().clean()
        permanente = cleaned_data.get("opo_permanente", False)
        tipo_opo = cleaned_data.get("tipo_opo", "FESTIVO")
        efetivo_institucional = (cleaned_data.get("efetivo_institucional") or "").strip()
        data_inicio = cleaned_data.get("data_evento")
        data_fim = cleaned_data.get("opo_permanente_data_fim")
        indeterminado = cleaned_data.get("opo_permanente_indeterminado", False)

        matriculas = cleaned_data.get("matriculas_institucionais") or []
        if tipo_opo == "INSTITUCIONAL":
            if not matriculas:
                self.add_error("matriculas_institucionais", "Selecione pelo menos um policial para o efetivo.")
            else:
                matriculas_qs = MatriculaAutorizada.objects.filter(
                    matricula__in=matriculas,
                    ativo=True,
                    unidade=cleaned_data.get("unidade"),
                )
                encontrados = {str(item.matricula): item for item in matriculas_qs}
                if len(encontrados) != len(set(matriculas)):
                    self.add_error("matriculas_institucionais", "Uma ou mais matrículas não pertencem à unidade responsável.")
                else:
                    linhas = [
                        f"{encontrados[m].matricula} — {encontrados[m].posto} {encontrados[m].nome}".strip()
                        for m in matriculas
                    ]
                    cleaned_data["efetivo_institucional"] = "\n".join(linhas)
                    efetivo_institucional = cleaned_data["efetivo_institucional"]

        if permanente:
            if not data_inicio:
                self.add_error("data_evento", "Informe a data de início da OPO permanente.")
            if indeterminado:
                cleaned_data["opo_permanente_data_fim"] = None
            elif not data_fim:
                self.add_error(
                    "opo_permanente_data_fim",
                    'Informe a data de fim ou marque "Indeterminado".',
                )
            elif data_inicio and data_fim < data_inicio:
                self.add_error(
                    "opo_permanente_data_fim",
                    "A data de fim não pode ser anterior à data de início.",
                )
        else:
            cleaned_data["opo_permanente_data_fim"] = None
            cleaned_data["opo_permanente_indeterminado"] = False

        return cleaned_data


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


@login_required
def alterar_status(request, id, status, *args, **kwargs):
    """Compatibilidade com a rota histórica de alteração de status."""
    solicitacao = Solicitacao.objects.filter(pk=id).first()
    permitidos = {"PENDENTE", "EM_ANALISE", "CORRECAO", "APROVADA", "REJEITADA", "CONCLUIDA"}
    if not solicitacao:
        messages.error(request, "Solicitação não encontrada.")
        return redirect("painel_gestao")
    if status not in permitidos:
        messages.error(request, "Status inválido.")
        return redirect("painel_gestao")

    solicitacao.status = status
    if status in {"APROVADA", "REJEITADA", "CONCLUIDA"}:
        solicitacao.data_aprovacao = timezone.now()
    solicitacao.save(update_fields=["status", "data_aprovacao", "atualizado_em"])

    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao=f"STATUS: {status}",
        observacao="Alteração realizada pela rota de compatibilidade.",
    )
    messages.success(request, "Status atualizado.")
    return redirect("painel_gestao")


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
    "alterar_status",
]
