"""Camada de compatibilidade das views operacionais antigas.

As rotas novas usam views segmentadas/seguras. Este módulo mantém os nomes
históricos importados por compat.py sem duplicar a implementação.
"""

from django import forms
from django.http import JsonResponse


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
from apps.solicitacoes.models import Bairro, HistoricoSolicitacao, Municipio, Solicitacao, TipoEvento, Unidade
from apps.solicitacoes.permissoes import escopo_unidades
from apps.solicitacoes.models_acesso import AcessoInstitucional


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
            initial=tipo_opo_inicial,
            label="Tipo de OPO",
            choices=Solicitacao.TIPO_OPO_CHOICES,
            widget=forms.Select(attrs={
                "class": "tipo-opo-toggle",
                "onchange": "setTimeout(function(){['id_cpf','id_email','id_telefone'].forEach(function(id){var e=document.getElementById(id);if(e&&e.parentElement)e.parentElement.style.display='';});},0);",
            }),
            help_text="Selecione Institucional somente para o lançamento interno de operações institucionais.",
        )

        # No lançamento interno Festivo, os dados de contato continuam disponíveis.
        # No Institucional, não são obrigatórios e podem permanecer vazios, conforme
        # a regra específica desse tipo de OPO.
        self.fields["cpf"] = forms.CharField(
            required=False,
            label="CPF",
            max_length=14,
            widget=forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "000.000.000-00",
                "maxlength": "14",
                "inputmode": "numeric",
                "autocomplete": "off",
                "oninput": "this.value=this.value.replace(/\\D/g,'').slice(0,11).replace(/(\\d{3})(\\d)/,'$1.$2').replace(/(\\d{3})(\\d)/,'$1.$2').replace(/(\\d{3})(\\d{1,2})$/,'$1-$2');",
            }),
        )
        self.fields["telefone"] = forms.CharField(
            required=False,
            label="Telefone",
            max_length=15,
            widget=forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "(99) 99999-9999",
                "maxlength": "15",
                "inputmode": "tel",
                "autocomplete": "off",
                "oninput": "this.value=this.value.replace(/\\D/g,'').slice(0,11).replace(/(\\d{2})(\\d)/,'($1) $2').replace(/(\\d{5})(\\d)/,'$1-$2');",
            }),
        )
        self.fields["email"] = forms.CharField(
            required=False,
            label="E-mail",
            max_length=254,
            widget=forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "seuemail@exemplo.com",
                "autocomplete": "off",
            }),
        )

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
                    (str(a.matricula), f"{a.matricula} — {a.usuario.get_full_name() or a.usuario.username}".strip())
                    for a in AcessoInstitucional.objects.select_related("usuario").filter(
                        unidade_id=unidade_id_matriculas,
                        ativo=True,
                        usuario__is_active=True,
                    ).order_by("usuario__first_name", "matricula")
                ]

        self.fields["matriculas_institucionais"] = forms.MultipleChoiceField(
            required=False,
            label="Efetivo",
            choices=opcoes_matriculas,
            widget=forms.SelectMultiple(attrs={"class": "matriculas-institucionais", "style": "display:none;"}),
            help_text="Matrícula é opcional. Informe uma ou várias somente quando desejar identificar o efetivo institucional.",
        )

        self.fields["unidade"] = forms.ModelChoiceField(
            queryset=unidades,
            required=True,
            label="Unidade responsável",
            widget=forms.Select(attrs={"class": "form-select"}),
        )

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
        data_inicio = cleaned_data.get("data_evento")
        data_fim = cleaned_data.get("opo_permanente_data_fim")
        indeterminado = cleaned_data.get("opo_permanente_indeterminado", False)

        # Festivo pode utilizar os dados de contato para o recebimento da confirmação.
        # Institucional não exige CPF, e-mail ou telefone.
        if tipo_opo == "FESTIVO":
            for campo, mensagem in (
                ("cpf", "Informe o CPF."),
                ("email", "Informe o e-mail."),
                ("telefone", "Informe o telefone."),
            ):
                valor = (cleaned_data.get(campo) or "").strip()
                if not valor:
                    self.add_error(campo, mensagem)
                else:
                    cleaned_data[campo] = valor
        else:
            cleaned_data["cpf"] = ""
            cleaned_data["email"] = ""
            cleaned_data["telefone"] = ""

        matriculas = cleaned_data.get("matriculas_institucionais") or []
        if tipo_opo == "INSTITUCIONAL":
            if matriculas:
                matriculas_qs = AcessoInstitucional.objects.select_related("usuario").filter(
                    matricula__in=matriculas,
                    ativo=True,
                    unidade=cleaned_data.get("unidade"),
                    usuario__is_active=True,
                )
                encontrados = {str(item.matricula): item for item in matriculas_qs}
                if len(encontrados) != len(set(matriculas)):
                    self.add_error("matriculas_institucionais", "Uma ou mais matrículas não pertencem à unidade responsável.")
                else:
                    linhas = [
                        f"{encontrados[m].matricula} — {encontrados[m].usuario.get_full_name() or encontrados[m].usuario.username}".strip()
                        for m in matriculas
                    ]
                    cleaned_data["efetivo_institucional"] = "\n".join(linhas)
            else:
                cleaned_data["efetivo_institucional"] = ""

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


@login_required
def buscar_matricula_institucional(request, unidade_id):
    """Consulta a matrícula diretamente no cadastro ativo da unidade selecionada."""
    if request.method != "GET":
        return JsonResponse({"ok": False, "erro": "Método não permitido."}, status=405)

    if unidade_id not in set(escopo_unidades(request.user).values_list("id", flat=True)):
        return JsonResponse({"ok": False, "erro": "Unidade fora do seu escopo."}, status=403)

    termo = (request.GET.get("termo") or "").strip()
    if len(termo) < 2:
        return JsonResponse({"ok": True, "resultados": []})

    acessos = AcessoInstitucional.objects.select_related("usuario").filter(
        unidade_id=unidade_id,
        ativo=True,
        usuario__is_active=True,
    ).filter(
        Q(matricula__icontains=termo)
        | Q(usuario__first_name__icontains=termo)
        | Q(usuario__last_name__icontains=termo)
        | Q(usuario__username__icontains=termo)
    ).order_by("usuario__first_name", "matricula")[:20]

    return JsonResponse({
        "ok": True,
        "resultados": [
            {
                "matricula": str(item.matricula),
                "nome": item.usuario.get_full_name() or item.usuario.username,
                "posto": "",
                "label": f"{item.matricula} — {item.usuario.get_full_name() or item.usuario.username}",
            }
            for item in acessos
        ],
    })
