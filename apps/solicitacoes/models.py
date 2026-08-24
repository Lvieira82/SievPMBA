import os
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator


# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================

def gerar_protocolo_unico():
    while True:
        protocolo = uuid.uuid4().hex[:8].upper()

        if not Solicitacao.objects.filter(
            protocolo=protocolo
        ).exists():
            return protocolo


def upload_documento(instance, filename):
    return os.path.join(
        "protocolos",
        instance.solicitacao.protocolo,
        filename
    )


def upload_comandante(instance, filename):
    return os.path.join(
        "protocolos",
        instance.protocolo,
        "oficio_comandante.pdf"
    )


def pasta_opo(instance, filename):
    protocolo = instance.protocolo or "SEM_PROTOCOLO"

    return os.path.join(
        "protocolos",
        protocolo,
        "opo",
        filename
    )


# ==========================================================
# ORGANIZAÇÃO PMBA
# ==========================================================

class COPPM(models.Model):

    nome = models.CharField(
        max_length=120
    )

    sigla = models.CharField(
        max_length=20,
        unique=True
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["sigla"]
        verbose_name = "COPPM"
        verbose_name_plural = "COPPM"

    def __str__(self):
        return self.sigla


class CPR(models.Model):

    coppm = models.ForeignKey(
        COPPM,
        on_delete=models.PROTECT,
        related_name="cprs"
    )

    nome = models.CharField(
        max_length=150
    )

    sigla = models.CharField(
        max_length=20
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["sigla"]

    def __str__(self):
        return self.sigla


class Unidade(models.Model):

    TIPOS = [

        ("BPM", "BPM"),
        ("CIPM", "CIPM"),
        ("CIPE", "CIPE"),
        ("CPR", "CPR"),
        ("ESPECIALIZADA", "Especializada"),
        ("OUTRA", "Outra"),

    ]

    cpr = models.ForeignKey(
        CPR,
        on_delete=models.PROTECT,
        related_name="unidades"
    )

    nome = models.CharField(
        max_length=150
    )

    sigla = models.CharField(
        max_length=30
    )

    tipo = models.CharField(
        max_length=30,
        choices=TIPOS
    )

    telefone = models.CharField(
        max_length=20,
        blank=True
    )

    email = models.EmailField(
        blank=True
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["sigla"]

    def __str__(self):
        return self.sigla


# ==========================================================
# LOCALIZAÇÃO
# ==========================================================

class Municipio(models.Model):

    nome = models.CharField(
        max_length=120,
        unique=True
    )

    ibge = models.CharField(
        max_length=10,
        blank=True,
        null=True
    )

    unidade_responsavel = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="municipios"
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Bairro(models.Model):

    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.CASCADE,
        related_name="bairros"
    )

    nome = models.CharField(
        max_length=120
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["nome"]
        unique_together = (
            "municipio",
            "nome"
        )

    def __str__(self):
        return f"{self.nome} - {self.municipio.nome}"


class AreaResponsabilidade(models.Model):

    bairro = models.ForeignKey(
        Bairro,
        on_delete=models.CASCADE
    )

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        verbose_name = "Área de Responsabilidade"
        verbose_name_plural = "Áreas de Responsabilidade"
        unique_together = (
            "bairro",
            "unidade"
        )

    def __str__(self):
        return f"{self.bairro} → {self.unidade}"
    
# ==========================================================
# CONFIGURAÇÕES DO SISTEMA
# ==========================================================

class TipoEvento(models.Model):

    nome = models.CharField(
        max_length=120,
        unique=True
    )

    descricao = models.TextField(
        blank=True
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["nome"]
        verbose_name = "Tipo de Evento"
        verbose_name_plural = "Tipos de Eventos"

    def __str__(self):
        return self.nome


class Modulo(models.Model):

    nome = models.CharField(
        max_length=120,
        unique=True
    )

    descricao = models.TextField(
        blank=True
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class TipoDocumento(models.Model):

    nome = models.CharField(
        max_length=120,
        unique=True
    )

    descricao = models.TextField(
        blank=True
    )

    extensoes_permitidas = models.CharField(
        max_length=100,
        default="pdf"
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class ConfiguracaoUnidade(models.Model):

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.CASCADE,
        related_name="configuracoes"
    )

    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.CASCADE,
        blank=True,
        null=True
    )

    tipo_documento = models.ForeignKey(
        TipoDocumento,
        on_delete=models.CASCADE,
        blank=True,
        null=True
    )

    obrigatorio = models.BooleanField(
        default=False
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        verbose_name = "Configuração da Unidade"
        verbose_name_plural = "Configurações das Unidades"

    def __str__(self):

        if self.tipo_documento:
            return f"{self.unidade} - {self.tipo_documento}"

        if self.modulo:
            return f"{self.unidade} - {self.modulo}"

        return str(self.unidade)


# ==========================================================
# CAMPOS DINÂMICOS
# ==========================================================

class CampoPersonalizado(models.Model):

    TIPOS = [

        ("texto", "Texto"),

        ("numero", "Número"),

        ("data", "Data"),

        ("hora", "Hora"),

        ("boolean", "Sim / Não"),

        ("lista", "Lista"),

        ("textarea", "Texto Longo"),

    ]

    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.CASCADE,
        related_name="campos"
    )

    nome = models.CharField(
        max_length=120
    )

    label = models.CharField(
        max_length=150
    )

    tipo = models.CharField(
        max_length=20,
        choices=TIPOS
    )

    obrigatorio = models.BooleanField(
        default=False
    )

    ordem = models.PositiveIntegerField(
        default=0
    )

    ajuda = models.CharField(
        max_length=250,
        blank=True
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = [
            "ordem",
            "label"
        ]

    def __str__(self):
        return self.label


class OpcaoCampo(models.Model):

    campo = models.ForeignKey(
        CampoPersonalizado,
        on_delete=models.CASCADE,
        related_name="opcoes"
    )

    valor = models.CharField(
        max_length=120
    )

    ordem = models.PositiveIntegerField(
        default=0
    )

    class Meta:
        ordering = [
            "ordem",
            "valor"
        ]

    def __str__(self):
        return self.valor


# ==========================================================
# MÓDULOS DA SOLICITAÇÃO
# ==========================================================

class SolicitacaoModulo(models.Model):

    solicitacao = models.ForeignKey(
        "Solicitacao",
        on_delete=models.CASCADE,
        related_name="modulos"
    )

    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.PROTECT
    )

    class Meta:
        unique_together = (
            "solicitacao",
            "modulo"
        )

    def __str__(self):
        return f"{self.solicitacao.protocolo} - {self.modulo}"


class ValorCampo(models.Model):

    solicitacao_modulo = models.ForeignKey(
        SolicitacaoModulo,
        on_delete=models.CASCADE,
        related_name="valores"
    )

    campo = models.ForeignKey(
        CampoPersonalizado,
        on_delete=models.CASCADE
    )

    valor = models.TextField()

    class Meta:
        unique_together = (
            "solicitacao_modulo",
            "campo"
        )

    def __str__(self):
        return self.campo.label
    
# ==========================================================
# SOLICITAÇÕES
# ==========================================================

class Solicitacao(models.Model):

    STATUS = [

        ("RASCUNHO", "Rascunho"),

        ("ENVIADA", "Enviada"),

        ("EM_ANALISE", "Em análise"),

        ("PENDENTE", "Pendente"),

        ("CORRECAO", "Correção"),

        ("APROVADA", "Aprovada"),

        ("REJEITADA", "Rejeitada"),

        ("CONCLUIDA", "Concluída"),

    ]


    protocolo = models.CharField(
        max_length=20,
        unique=True,
        blank=True
    )


    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )


    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="solicitacoes",
        null=True,
        blank=True
    )


    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.PROTECT
    )


    bairro = models.ForeignKey(
        Bairro,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )


    tipo_evento = models.ForeignKey(
        TipoEvento,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    nome_evento = models.CharField(
        max_length=250
    )


    solicitante = models.CharField(
        max_length=200
    )


    cpf = models.CharField(
        max_length=14
    )


    email = models.EmailField()


    telefone = models.CharField(
        max_length=20
    )


    local = models.TextField()


    publico_estimado = models.IntegerField(
        null=True,
        blank=True
    )


    data_evento = models.DateField()


    hora_inicio = models.TimeField()


    hora_fim = models.TimeField()


    observacoes = models.TextField(
        blank=True
    )


    parecer_operacional = models.TextField(
        blank=True
    )


    aprovado_por = models.CharField(
        max_length=150,
        blank=True
    )


    data_aprovacao = models.DateTimeField(
        null=True,
        blank=True
    )


    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default="RASCUNHO"
    )


    criado_em = models.DateTimeField(
        auto_now_add=True
    )


    atualizado_em = models.DateTimeField(
        auto_now=True
    )
    ORIGEM_CHOICES = [
        ("EXTERNA", "Externa"),
        ("MANUAL", "Manual"),
        ("TRANSFERIDA", "Transferida"),
    ]

    origem = models.CharField(
        max_length=20,
        choices=ORIGEM_CHOICES,
        default="EXTERNA"
    )


    def save(self,*args,**kwargs):

        if not self.protocolo:
            self.protocolo = gerar_protocolo_unico()

        super().save(*args,**kwargs)


    def __str__(self):
        return f"{self.protocolo} - {self.nome_evento}"


# ==========================================================
# DOCUMENTOS
# ==========================================================

class DocumentoSolicitacao(models.Model):

    solicitacao = models.ForeignKey(
        Solicitacao,
        on_delete=models.CASCADE,
        related_name="documentos"
    )


    tipo_documento = models.ForeignKey(
        TipoDocumento,
        on_delete=models.PROTECT
    )


    descricao = models.CharField(
        max_length=250,
        blank=True
    )


    arquivo = models.FileField(
        upload_to=upload_documento,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["pdf"]
            )
        ]
    )


    enviado_em = models.DateTimeField(
        auto_now_add=True
    )


    class Meta:

        ordering = [

            "tipo_documento",

            "id"

        ]


    def __str__(self):

        return f"{self.solicitacao.protocolo} - {self.tipo_documento}"



# ==========================================================
# OPO
# ==========================================================

class AnexoOPO(models.Model):

    solicitacao = models.ForeignKey(
        Solicitacao,
        on_delete=models.CASCADE,
        related_name="opos"
    )


    arquivo = models.FileField(
        upload_to=pasta_opo
    )


    descricao = models.CharField(
        max_length=250,
        blank=True
    )


    criado_em = models.DateTimeField(
        auto_now_add=True
    )


    def __str__(self):

        return self.arquivo.name
# ==========================================================
# MATRÍCULAS AUTORIZADAS
# ==========================================================

class MatriculaAutorizada(models.Model):

    matricula = models.CharField(
        max_length=20,
        unique=True
    )

    nome = models.CharField(
        max_length=150
    )

    posto = models.CharField(
        max_length=30,
        blank=True
    )

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    ativo = models.BooleanField(
        default=True
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        ordering = [

            "nome"

        ]

        verbose_name = "Matrícula Autorizada"

        verbose_name_plural = "Matrículas Autorizadas"

    def __str__(self):

        if self.unidade:
            return f"{self.posto} {self.nome} ({self.unidade})"

        return f"{self.posto} {self.nome}"


# ==========================================================
# PERFIL DO USUÁRIO
# ==========================================================

# ==========================================================
# PERFIL E ACESSO DO USUÁRIO
# ==========================================================

class PerfilUsuario(models.Model):

    PERFIS = [
        ("COPPM", "Gestor COPPM"),
        ("CPR", "Gestor CPR"),
        ("UNIDADE", "Gestor de Unidade"),
    ]

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil_siev"
    )

    perfil = models.CharField(
        max_length=20,
        choices=PERFIS
    )

    # Usado pelo gestor CPR
    cpr = models.ForeignKey(
        CPR,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gestores_siev"
    )

    # Usado pelo gestor de Unidade
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gestores_siev"
    )

    ativo = models.BooleanField(
        default=True
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    atualizado_em = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        verbose_name = "Perfil de Usuário"

        verbose_name_plural = "Perfis de Usuários"

    def __str__(self):

        if self.perfil == "COPPM":

            return (
                f"{self.usuario.username} - "
                f"Gestor COPPM"
            )

        if self.perfil == "CPR":

            return (
                f"{self.usuario.username} - "
                f"Gestor CPR - {self.cpr}"
            )

        if self.perfil == "UNIDADE":

            return (
                f"{self.usuario.username} - "
                f"Gestor Unidade - {self.unidade}"
            )

        return self.usuario.username

UsuarioPerfil = PerfilUsuario
# ==========================================================
# LOG DO SISTEMA
# ==========================================================

class LogSistema(models.Model):

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    solicitacao = models.ForeignKey(
        Solicitacao,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    acao = models.CharField(
        max_length=200
    )

    detalhes = models.TextField(
        blank=True
    )

    ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        ordering = [

            "-criado_em"

        ]

        verbose_name = "Log"

        verbose_name_plural = "Logs"

    def __str__(self):

        return f"{self.criado_em:%d/%m/%Y %H:%M} - {self.acao}"
    
class TransferenciaSolicitacao(models.Model):

    solicitacao = models.ForeignKey(
        Solicitacao,
        on_delete=models.CASCADE,
        related_name="transferencias"
    )

    unidade_origem = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="transferencias_origem"
    )

    unidade_destino = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="transferencias_destino"
    )

    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="transferencias_realizadas"
    )

    motivo = models.TextField(
        blank=True
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):

        return (
            f"{self.solicitacao.protocolo} - "
            f"{self.unidade_origem} → "
            f"{self.unidade_destino}"
        )


# ==========================================================
# HISTÓRICO DE MOVIMENTAÇÕES
# ==========================================================

class HistoricoSolicitacao(models.Model):

    solicitacao = models.ForeignKey(
        Solicitacao,
        on_delete=models.CASCADE,
        related_name="historico"
    )

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historicos_siev"
    )

    # Compatibilidade com registros/rotinas antigas
    status = models.CharField(
        max_length=40,
        blank=True
    )

    # Mudança de status
    status_anterior = models.CharField(
        max_length=40,
        blank=True
    )

    status_novo = models.CharField(
        max_length=40,
        blank=True
    )

    # Mudança de unidade
    unidade_anterior = models.ForeignKey(
        Unidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historicos_unidade_anterior"
    )

    unidade_nova = models.ForeignKey(
        Unidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historicos_unidade_nova"
    )

    # Tipo da movimentação
    acao = models.CharField(
        max_length=50,
        blank=True
    )

    observacao = models.TextField(
        blank=True
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        ordering = [
            "-criado_em"
        ]

    def __str__(self):

        return (
            f"{self.solicitacao.protocolo} - "
            f"{self.acao or self.status_novo or self.status}"
        )