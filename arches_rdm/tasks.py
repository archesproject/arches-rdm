import logging
from celery import shared_task
from django.contrib.auth.models import User
from django.utils.translation import gettext as _
from arches.app.models import models
from arches_rdm.etl_modules import migrate_rdm
from arches.app.tasks import notify_completion

@shared_task
def migrate_rdm_task(userid, loadid):
    logger = logging.getLogger(__name__)

    try:
        RDMMigrator = migrate_rdm.RDMMigrator(loadid=loadid)
        RDMMigrator.run_load_task(userid, loadid)

        load_event = models.LoadEvent.objects.get(loadid=loadid)
        status = _("Completed") if load_event.status == "indexed" else _("Failed")
    except Exception as e:
        logger.error(e)
        load_event = models.LoadEvent.objects.get(loadid=loadid)
        load_event.status = "failed"
        load_event.save()
        status = _("Failed")
    finally:
        msg = _("RDM Migration: [{}]").format(status)
        user = User.objects.get(id=userid)
        notify_completion(msg, user)
