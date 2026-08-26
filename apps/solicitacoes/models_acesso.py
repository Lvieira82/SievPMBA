from django.conf import settings
from django.db import models


class AcessoInstitucional(models.Model):
    PERFIS = [("COPPM", "COPPM"), ("CPR", "CPR"), ("UNIDADE", "Unidade")]
    FUNCOES = [("GESTOR", "Gestor"), ("MEMBRO", "Membro")]

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="acesso_institucional")
    matricula = models.CharField(max_length=30, unique=True)
    cpf = models.CharField(max_length=14, unique=True, null=True, blank=True)
    telefone = models.CharField(max_length=25, blank=True)
    perfil = models.CharField(max_length=20, choices=PERFIS)
    funcao = models.CharField(max_length=10, choices=FUNCOES, default="MEMBRO")
    cpr = models.ForeignKey("solicitacoes.CPR", on_delete=models.SET_NULL, null=True, blank=True, related_name="acessos_institucionais")
    unidade = models.ForeignKey("solicitacoes.Unidade", on_delete=models.SET_NULL, null=True, blank=True, related_name="acessos_institucionais")
    primeiro_acesso = models.BooleanField(default=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["usuario__first_name", "matricula"]
        verbose_name = "Acesso Institucional"
        verbose_name_plural = "Acessos Institucionais"

    def __str__(self):
        return f"{self.matricula} - {self.usuario.get_full_name()}"


class DispositivoAutorizado(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dispositivos_autorizados")
    token_hash = models.CharField(max_length=64, unique=True)
    rotulo = models.CharField(max_length=120, blank=True)
    user_agent = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    ultimo_acesso = models.DateTimeField(auto_now=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["-ultimo_acesso"]
        verbose_name = "Dispositivo Autorizado"
        verbose_name_plural = "Dispositivos Autorizados"

    def __str__(self):
        return f"{self.usuario} - {self.rotulo or 'Dispositivo'}"


class CodigoNovoNavegador(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="codigos_novo_navegador")
    codigo_hash = models.CharField(max_length=128)
    expira_em = models.DateTimeField()
    criado_em = models.DateTimeField(auto_now_add=True)
    tentativas = models.PositiveSmallIntegerField(default=0)
    usado = models.BooleanField(default=False)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Código de Novo Navegador"
        verbose_name_plural = "Códigos de Novo Navegador"

    def __str__(self):
        return f"{self.usuario} - {self.criado_em:%d/%m/%Y %H:%M}"
