#!/usr/bin/env bash
# تحديث موقع الجائزة على خادم Oracle من GitHub (البيانات والصور لا تُلمس)
set -euo pipefail
cd /opt/iaj
git fetch -q origin main && git reset -q --hard origin/main
venv/bin/pip install -q -r requirements.txt
venv/bin/python manage.py migrate --noinput
venv/bin/python manage.py collectstatic --noinput >/dev/null
sudo systemctl restart iaj
git log -1 --oneline
echo "✓ تم التحديث"
