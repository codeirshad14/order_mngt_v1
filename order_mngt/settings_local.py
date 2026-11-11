"""Settings for running on this PC only — never used in production.

Everything comes from settings.py; only the database and DEBUG change, so the
site runs against the local db.sqlite3 file and serves its own CSS and images.

    python manage.py runserver --settings=order_mngt.settings_local
"""

from .settings import *  # noqa: F401,F403

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}
