from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver

from django.conf import settings

from .models_acesso import AcessoInstitucional


@receiver(post_save, sender=User)
def enviar_email_inicial_usuario(sender, instance, created, **kwargs):
    """Envia automaticamente o e-mail inicial quando um usuário institucional nasce."""
    if not created or instance.is_superuser or not instance.email:
        return

    acesso = AcessoInstitucional.objects.filter(usuario=instance).first()
    if not acesso:
        return

    nome = instance.get_full_name() or acesso.matricula
    send_mail(
        "Seu acesso ao SiEvPM foi criado",
        f"Olá, {nome}.\n\nSeu acesso institucional ao SiEvPM foi criado com sucesso.\n\n"
        f"Matrícula: {acesso.matricula}\n"
        "No primeiro acesso, utilize a senha fornecida pelo administrador e conclua a definição da sua senha.\n\n"
        "Por segurança, um código de confirmação será solicitado somente quando o acesso ocorrer em um dispositivo novo. Depois de autorizado, este dispositivo permanecerá confiável.\n\n"
        "Se você não solicitou este acesso, procure o administrador do sistema.",
        settings.DEFAULT_FROM_EMAIL,
        [instance.email],
        fail_silently=False,
    )
