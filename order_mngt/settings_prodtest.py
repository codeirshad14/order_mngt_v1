"""Production-mode test on this PC: DEBUG off, exactly as on the server, but
on the local db.sqlite3. Never used on the server itself.

    python manage.py runserver --insecure --settings=order_mngt.settings_prodtest

--insecure lets runserver hand out the CSS/JS with DEBUG off; on the server
nginx does that job.
"""

from .settings_local import *  # noqa: F401,F403

DEBUG = False

# the server's nginx serves /media/ (logo, product photos); here a small
# URL file does it, so the pages look the same
ROOT_URLCONF = "order_mngt.urls_prodtest"
