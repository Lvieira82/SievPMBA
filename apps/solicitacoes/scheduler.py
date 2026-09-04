from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from django.conf import settings

from .services.rotina import executar_rotina_diaria

scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)


def iniciar_scheduler():

    if scheduler.running:
        return

    scheduler.add_job(
        executar_rotina_diaria,
        trigger=CronTrigger(hour=9, minute=0),
        id="rotina_diaria",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()

    print("Scheduler iniciado.")
    for job in scheduler.get_jobs():
        print(job)
