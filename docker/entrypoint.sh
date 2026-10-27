#!/bin/sh
set -eu
python manage.py migrate --noinput
python manage.py setup_roles
python manage.py bootstrap_admin
python manage.py collectstatic --noinput
python manage.py check --deploy
exec "$@"
