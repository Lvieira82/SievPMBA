from django import forms
from django.core.exceptions import ValidationError
from datetime import date, timedelta
import re
from .models import Solicitacao, MatriculaAutorizada, PerfilUsuario
from .utils import analisar_datas_oficio
from django.contrib.auth.models import User


def validar_pdf(arquivo):
    if not arquivo:
        return
    extensao = arquivo.name.split(".")[-1].lower()
    if extensao != "pdf":
        raise ValidationError("Somente arquivos PDF são permitidos.")


class SolicitacaoForm(forms.ModelForm):
    # Este campo não pertence à tabela Solicitacao. Ele é recebido pelo
    # formulário e persistido explicitamente em DocumentoSolicitacao.
    oficio_comandante = forms.FileField(
        label="Ofício ao Comandante da Unidade (PDF)",
        required=True,
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".pdf,application/pdf"}),
    )

    class Meta:
        model = Solicitacao
        exclude = [
            "status", "parecer_operacional", "aprovado_por", "data_aprovacao",
            "protocolo", "usuario", "assinado_por", "data_assinatura", "criado_em",
            "opo_pdf", "gerado_por", "pesquisa_token", "pesquisa_enviada",
            "data_envio_pesquisa", "pesquisa_respondida", "data_resposta_pesquisa",
            "nota_satisfacao", "comentario_satisfacao", "documentos_expurgados",
            "motivo_correcao", "unidade", "municipio", "tipo_evento", "publico_estimado",
        ]
        widgets = {
            "cpf": forms.TextInput(attrs={"class": "form-control", "placeholder": "000.000.000-00", "maxlength": "14"}),
            "telefone": forms.TextInput(attrs={"class": "form-control", "placeholder": "(99) 99999-9999", "maxlength": "15"}),
            "data_evento": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aviso_multiplas_datas = False
        self.datas_encontradas_oficio = []
        data_minima = date.today() + timedelta(days=3)
        self.fields["data_evento"].widget.attrs.update({"type": "date", "min": data_minima.strftime("%Y-%m-%d")})
        for campo in ["nome_evento", "solicitante"]:
            if campo in self.fields:
                self.fields[campo].widget.attrs.update({"oninput": "this.value = this.value.toUpperCase();"})

    def clean_telefone(self):
        telefone = self.cleaned_data.get("telefone")
        if not telefone or not re.match(r"^\(\d{2}\)\s\d{5}-\d{4}$", telefone):
            raise forms.ValidationError("Telefone inválido. Use (99) 99999-9999")
        return telefone

    def clean_data_evento(self):
        data_evento = self.cleaned_data.get("data_evento")
        data_minima = date.today() + timedelta(days=3)
        if data_evento and data_evento < data_minima:
            raise forms.ValidationError("A data do evento deve ser, no mínimo, 3 dias após a data da informação.")
        return data_evento

    def clean_oficio_comandante(self):
        arquivo = self.cleaned_data.get("oficio_comandante")
        if not arquivo:
            raise forms.ValidationError("O Ofício ao Comandante da Unidade é obrigatório.")
        validar_pdf(arquivo)
        return arquivo

    def clean(self):
        cleaned_data = super().clean()
        oficio = cleaned_data.get("oficio_comandante")
        data_evento = cleaned_data.get("data_evento")
        if not oficio or not data_evento:
            return cleaned_data
        try:
            resultado = analisar_datas_oficio(oficio, data_evento)
        except Exception as erro:
            print("ERRO AO ANALISAR OFÍCIO:", repr(erro))
            raise forms.ValidationError("Não foi possível analisar o Ofício ao Comandante. Verifique se o PDF está legível e tente novamente.")
        if not resultado["datas"]:
            raise forms.ValidationError("Não foi possível identificar uma data no Ofício ao Comandante. Confira se o PDF está legível e contém a data do evento.")
        if not resultado["valido"]:
            datas_lidas = ", ".join(item["data"].strftime("%d/%m/%Y") for item in resultado["datas"])
            raise forms.ValidationError(f"A data do Ofício ao Comandante está diferente da data informada. Data(s) identificada(s): {datas_lidas}.")
        self.aviso_multiplas_datas = resultado["multiplas_datas"]
        self.datas_encontradas_oficio = resultado["datas"]
        return cleaned_data


class SolicitacaoManualForm(SolicitacaoForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ["publico_estimado"]:
            if campo in self.fields:
                self.fields[campo].required = False
        if "oficio_comandante" in self.fields:
            self.fields["oficio_comandante"].required = False
        if "cpf" in self.fields:
            self.fields["cpf"].widget.attrs.update({"placeholder": "Somente números", "maxlength": "11"})
        if "telefone" in self.fields:
            self.fields["telefone"].widget.attrs.update({"placeholder": "Somente números", "maxlength": "11"})
        if "data_evento" in self.fields:
            self.fields["data_evento"].widget.attrs.pop("min", None)

    def clean_data_evento(self):
        return self.cleaned_data.get("data_evento")

    def clean_telefone(self):
        telefone = "".join(filter(str.isdigit, self.cleaned_data.get("telefone", "")))
        if len(telefone) not in (10, 11):
            raise forms.ValidationError("Informe apenas os números do telefone.")
        return telefone

    def clean_cpf(self):
        cpf = "".join(filter(str.isdigit, self.cleaned_data.get("cpf", "")))
        if cpf and len(cpf) != 11:
            raise forms.ValidationError("Informe apenas os 11 números do CPF.")
        return cpf

    def clean(self):
        cleaned_data = super(SolicitacaoForm, self).clean()
        if not cleaned_data.get("publico_estimado"):
            cleaned_data["publico_estimado"] = 0
        return cleaned_data


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
        if cleaned_data.get("senha") and cleaned_data.get("confirmar_senha") and cleaned_data["senha"] != cleaned_data["confirmar_senha"]:
            raise forms.ValidationError("As senhas não coincidem.")
        return cleaned_data


class CorrecaoSolicitacaoForm(forms.ModelForm):
    class Meta:
        model = Solicitacao
        exclude = [
            "status", "parecer_operacional", "aprovado_por", "data_aprovacao", "protocolo",
            "usuario", "assinado_por", "data_assinatura", "criado_em", "opo_pdf",
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
        for campo in ["solicitante", "nome_evento"]:
            if campo in self.fields:
                self.fields[campo].widget.attrs.update({"oninput": "this.value = this.value.toUpperCase();"})
