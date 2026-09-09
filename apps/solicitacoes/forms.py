from django import forms
from django.core.exceptions import ValidationError
from datetime import date, timedelta
import re
from .models import Solicitacao
from .documentos_otimizados import analisar_datas_oficio_rapido
from django import forms
from django.contrib.auth.models import User
from .models import (
    Solicitacao,
    MatriculaAutorizada,
    PerfilUsuario,
)

# ==========================================================
# VALIDAÇÃO DE ARQUIVO PDF
# ==========================================================

def validar_pdf(arquivo):

    if not arquivo:
        return

    extensao = arquivo.name.split(".")[-1].lower()

    if extensao != "pdf":
        raise ValidationError(
            "Somente arquivos PDF são permitidos."
        )


# ==========================================================
# FORMULÁRIO DE SOLICITAÇÃO EXTERNA
# ==========================================================

class SolicitacaoForm(forms.ModelForm):

    oficio_comandante = forms.FileField(
        label="Ofício ao Comandante da Unidade (PDF)",
        required=True,
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".pdf,application/pdf",
        }),
    )

    class Meta:

        model = Solicitacao

        exclude = [
            "status",
            "parecer_operacional",
            "aprovado_por",
            "data_aprovacao",
            "protocolo",
            "usuario",
            "assinado_por",
            "data_assinatura",
            "criado_em",
            "opo_pdf",
            "gerado_por",
            "pesquisa_token",
            "pesquisa_enviada",
            "data_envio_pesquisa",
            "pesquisa_respondida",
            "data_resposta_pesquisa",
            "nota_satisfacao",
            "comentario_satisfacao",
            "documentos_expurgados",
            "motivo_correcao",
            "unidade",
            "municipio",
            "tipo_evento",
            "publico_estimado",
        ]

        widgets = {
            "cpf": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "000.000.000-00",
                "maxlength": "14",
            }),
            "telefone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "(99) 99999-9999",
                "maxlength": "15",
            }),
            "data_evento": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aviso_multiplas_datas = False
        self.datas_encontradas_oficio = []
        data_minima = date.today() + timedelta(days=3)
        self.fields["data_evento"].widget.attrs.update({
            "type": "date",
            "min": data_minima.strftime("%Y-%m-%d"),
        })
        for campo in ["nome_evento", "solicitante"]:
            if campo in self.fields:
                self.fields[campo].widget.attrs.update({
                    "oninput": "this.value = this.value.upper();"
                })

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf", "")
        cpf = re.sub(r"\D", "", cpf)
        if len(cpf) != 11 or cpf == cpf[0] * 11:
            raise forms.ValidationError("CPF inválido.")
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        digito1 = ((soma * 10) % 11) % 10
        if digito1 != int(cpf[9]):
            raise forms.ValidationError("CPF inválido.")
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        digito2 = ((soma * 10) % 11) % 10
        if digito2 != int(cpf[10]):
            raise forms.ValidationError("CPF inválido.")
        return cpf

    def clean_solicitante(self):
        return self.cleaned_data.get("solicitante", "").strip().upper()

    def clean_nome_evento(self):
        return self.cleaned_data.get("nome_evento", "").strip().upper()

    def clean_telefone(self):
        telefone = self.cleaned_data.get("telefone")
        padrao = r"^\(\d{2}\)\s\d{5}-\d{4}$"
        if not telefone or not re.match(padrao, telefone):
            raise forms.ValidationError(
                "Telefone inválido. Use (99) 99999-9999"
            )
        return telefone

    def clean_data_evento(self):
        data_evento = self.cleaned_data.get("data_evento")
        data_minima = date.today() + timedelta(days=3)
        if data_evento and data_evento < data_minima:
            raise forms.ValidationError(
                "A data do evento deve ser, no mínimo, "
                "3 dias após a data da informação."
            )
        return data_evento

    def clean_oficio_comandante(self):
        arquivo = self.cleaned_data.get("oficio_comandante")
        if not arquivo:
            raise forms.ValidationError(
                "O Ofício ao Comandante da Unidade é obrigatório."
            )
        validar_pdf(arquivo)
        return arquivo

    def clean(self):
        cleaned_data = super().clean()
        oficio_comandante = cleaned_data.get("oficio_comandante")
        data_evento = cleaned_data.get("data_evento")
        if not oficio_comandante or not data_evento:
            return cleaned_data

        try:
            resultado = analisar_datas_oficio_rapido(
                oficio_comandante,
                data_evento,
            )
        except Exception as erro:
            print("ERRO AO ANALISAR OFÍCIO:", repr(erro))
            raise forms.ValidationError(
                "Não foi possível analisar o Ofício ao "
                "Comandante. Verifique se o PDF está "
                "legível e tente novamente."
            )

        if not resultado["datas"]:
            raise forms.ValidationError(
                "Não foi possível identificar uma data "
                "no Ofício ao Comandante. Confira se o "
                "documento está legível e contém a "
                "data do evento."
            )

        if not resultado["valido"]:
            datas_lidas = ", ".join(
                item["data"].strftime("%d/%m/%Y")
                for item in resultado["datas"]
            )
            raise forms.ValidationError(
                "A data do Ofício ao Comandante está "
                "diferente da data informada. "
                f"Data(s) identificada(s): {datas_lidas}."
            )

        self.aviso_multiplas_datas = resultado["multiplas_datas"]
        self.datas_encontradas_oficio = resultado["datas"]
        return cleaned_data


# ==========================================================
# FORMULÁRIO DE LANÇAMENTO MANUAL
# ==========================================================

class SolicitacaoManualForm(SolicitacaoForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campos_nao_obrigatorios = [
            "publico_estimado",
            "documento_sanitario",
            "documento_meio_ambiente",
            "oficio_comandante",
            "oficio_bombeiro",
        ]
        for campo in ["nome_evento", "solicitante"]:
            if campo in self.fields:
                self.fields[campo].widget.attrs.update({
                    "oninput": "this.value = this.value.toUpperCase();"
                })
        for campo in campos_nao_obrigatorios:
            if campo in self.fields:
                self.fields[campo].required = False
        if "cpf" in self.fields:
            self.fields["cpf"].widget.attrs.update({
                "placeholder": "Somente números",
                "maxlength": "11",
            })
        if "telefone" in self.fields:
            self.fields["telefone"].widget.attrs.update({
                "placeholder": "Somente números",
                "maxlength": "11",
            })
        if "data_evento" in self.fields:
            self.fields["data_evento"].widget.attrs.pop("min", None)

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf", "")
        cpf = re.sub(r"\D", "", cpf)
        if not cpf:
            return cpf
        if len(cpf) != 11 or cpf == cpf[0] * 11:
            raise forms.ValidationError("CPF inválido.")
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        digito1 = ((soma * 10) % 11) % 10
        if digito1 != int(cpf[9]):
            raise forms.ValidationError("CPF inválido.")
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        digito2 = ((soma * 10) % 11) % 10
        if digito2 != int(cpf[10]):
            raise forms.ValidationError("CPF inválido.")
        return cpf

    def clean_data_evento(self):
        return self.cleaned_data.get("data_evento")
