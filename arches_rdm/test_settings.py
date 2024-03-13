import os

# Depends on /arches being on the python path, as arches.tests is not importable
from tests.test_settings import *

APP_NAME = "arches_rdm"
APP_ROOT = os.path.dirname(__file__)
INSTALLED_APPS = (
    "webpack_loader",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "arches",
    "arches.app.models",
    "arches.management",
    "guardian",
    "captcha",
    "revproxy",
    "corsheaders",
    "oauth2_provider",
    "django_celery_results",
    "arches_rdm",
)
ROOT_URLCONF = "arches_rdm.urls"

LOCALE_PATHS = [os.path.join(APP_ROOT, "locale")]

# Further settings may need to be added from project, just don't
# want to clobber anything from core test settings for now.
# Also, settings can be overridden directly. See @override_settings
