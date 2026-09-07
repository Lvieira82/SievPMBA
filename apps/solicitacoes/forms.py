from django import forms
from django.core.exceptions import ValidationError
from datetime import date, timedelta
import re
from .models import Solicitacao
from .utils import analisar_datas_oficio
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
        valor = self.cleaned_data.get("solicitante", "")
        return valor.strip().upper()

    def clean_nome_evento(self):
        valor = self.cleaned_data.get("nome_evento", "")
        return valor.strip().upper()

    def clean_telefone(self):
        telefone = self.cleaned_data.get("telefone")
        padrao = r"^\(\d{2}\)\s\d{5}-\d{4}$"
        if not telefone or not re.match(padrao, telefone):
            raise forms.ValidationError("Telefone inválido. Use (99) 99999-9999")
        return telefone

    def clean_data_evento(self):
        data_evento = self.cleaned_data.get("data_evento")
        data_minima = date.today() + timedelta(days=3)
        if data_evento and data_evento < data_minima:
            raise forms.ValidationError(
                "A data do evento deve ser, no mínimo, 3 dias após a data da informação."
            )
        return data_evento

    def clean_oficio_comandante(self):
        arquivo = self.cleaned_data.get("oficio_comandante")
        if not arquivo:
            raise forms.ValidationError("O Ofício ao Comandante da Unidade é obrigatório.")
        validar_pdf(arquivo)
        return arquivo

    def clean(self):
        cleaned_data = super().clean()
        oficio_comandante = cleaned_data.get("oficio_comandante")
        data_evento = cleaned_data.get("data_evento")
        if not oficio_comandante or not data_evento:
            return cleaned_data
        try:
            resultado = analisar_datas_oficio(oficio_comandante, data_evento)
        except Exception as erro:
            print("ERRO AO ANALISAR OFÍCIO:", repr(erro))
            raise forms.ValidationError(
                "Não foi possível analisar o Ofício ao Comandante. Verifique se o PDF está legível e tente novamente."
            )
        if not resultado["datas"]:
            raise forms.ValidationError(
                "Não foi possível identificar uma data no Ofício ao Comandante. Confira se o documento está legível e contém a data do evento."
            )
        if not resultado["valido"]:
            datas_lidas = ", ".join(
                item["data"].strftime("%d/%m/%Y") for item in resultado["datas"]
            )
            raise forms.ValidationError(
                "A data do Ofício ao Comandante está diferente da data informada. "
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
                    "oninput": "this.value = this.value.upper();"
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

    def clean_data_evento(self):
        return self.cleaned_data.get("data_evento")

    def clean_telefone(self):
        telefone = self.cleaned_data.get("telefone", "")
        telefone = "".join(filter(str.isdigit, telefone))
        if len(telefone) not in (10, 11):
            raise forms.ValidationError("Informe apenas os números do telefone.")
        return telefone

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf", "")
        cpf = "".join(filter(str.isdigit, cpf))
        if cpf and len(cpf) != 11:
            raise forms.ValidationError("Informe apenas os 11 números do CPF.")
        return cpf

    def clean(self):
        cleaned_data = super(SolicitacaoForm, self).clean()
        if not cleaned_data.get("publico_estimado"):
            cleaned_data["publico_estimado"] = 0
        return cleaned_data


# ==========================================================
# CADASTRO DE USUÁRIO DA UNIDADE
# ==========================================================

class UsuarioGestaoForm(forms.Form):
    nome = forms.CharField(label="Nome completo", max_length=150, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome completo"}))
    matricula = forms.CharField(label="Matrícula", max_length=20, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Matrícula"}))
    posto = forms.CharField(label="Posto / Graduação", max_length=30, required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: SD PM, CB PM, 1º SGT PM"}))
    username = forms.CharField(label="Usuário de acesso", max_length=150, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome de usuário"}))
    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "usuario@email.com"}))
    senha = forms.CharField(label="Senha", min_length=6, widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Mínimo de 6 caracteres"}))
    confirmar_senha = forms.CharField(label="Confirmar senha", widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Digite a senha novamente"}))

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nome de usuário já está cadastrado.")
        return username

    def clean_matricula(self):
        matricula = self.cleaned_data["matricula"].strip()
        if MatriculaAutorizada.objects.filter(matricula=matricula, ativo=True).exists():
            raise forms.ValidationError("Esta matrícula já está cadastrada.")
        return matricula

    def clean(self):
        cleaned_data = super().clean()
        senha = cleaned_data.get("senha")
        confirmar = cleaned_data.get("confirmar_senha")
        if senha and confirmar and senha != confirmar:
            raise forms.ValidationError("As senhas não coincidem.")
        return cleaned_data


class CorrecaoSolicitacaoForm(forms.ModelForm):
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
        ]
        widgets = {
            "cpf": forms.TextInput(attrs={"class": "form-control", "placeholder": "000.000.000-00", "maxlength": "14"}),
            "telefone": forms.TextInput(attrs={"class": "form-control", "placeholder": "(99) 99999-9999", "maxlength": "15"}),
            "data_evento": forms.DateInput(attrs={"type": "date", "readonly": True}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["data_evento"].initial = self.instance.data_evento
            self.fields["data_evento"].disabled = True
        if "solicitante" in self.fields:
            self.fields["solicitante"].widget.attrs.update({"oninput": "this.value = this.value.toUpperCase();"})
        if "nome_evento" in self.fields:
            self.fields["nome_evento"].widget.attrs.update({"oninput": "this.value = this.value.toUpperCase();"})

    def clean_solicitante(self):
        return self.cleaned_data.get("solicitante", "").strip().upper()

    def clean_nome_evento(self):
        return self.cleaned_data.get("nome_evento", "").strip().upper()

    def clean_cpf(self):
        cpf = re.sub(r"\D", "", self.cleaned_data.get("cpf", ""))
        if len(cpf) != 11 or cpf == cpf[0] * 11:
            raise forms.ValidationError("CPF inválido.")
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        if ((soma * 10) % 11) % 10 != int(cpf[9]):
            raise forms.ValidationError("CPF inválido.")
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        if ((soma * 10) % 11) % 10 != int(cpf[10]):
            raise forms.ValidationError("CPF inválido.")
        return cpf
