#!/usr/bin/env bash
# =====================================================================
#  تشغيل موقع الجائزة على خادم Oracle Cloud (Ubuntu 24.04 — ARM أو AMD)
#
#  الاستخدام:
#     bash oracle_setup.sh https://test.iajaward.org  [CLOUDFLARE_TUNNEL_TOKEN]
#
#  قبل التشغيل: ضع نسخة الكمبيوتر في ~/iaj-transfer
#     ~/iaj-transfer/db/iaj-....dump     (من backups\db)
#     ~/iaj-transfer/media/              (من backups\media)
#
#  آمن للتكرار: إعادة التشغيل تحدّث الكود وتعيد استرجاع النسخة.
# =====================================================================
set -euo pipefail

SITE_URL="${1:-}"
CF_TOKEN="${2:-}"
APP=/opt/iaj
SRC="$HOME/iaj-transfer"
REPO=https://github.com/AcsVe/IAJ.git
PGVER=18

say() { printf '\n\033[1;33m== %s ==\033[0m\n' "$*"; }

[ -n "$SITE_URL" ] || { echo "اكتب عنوان الموقع: bash oracle_setup.sh https://test.iajaward.org [TOKEN]"; exit 1; }
DUMP=$(ls -t "$SRC"/db/*.dump* 2>/dev/null | head -1 || true)
[ -n "$DUMP" ] || { echo "لم أجد ملف .dump في $SRC/db — انسخ النسخة الاحتياطية أولاً"; exit 1; }
[ -d "$SRC/media" ] || echo "تنبيه: لا يوجد $SRC/media — سيعمل الموقع بدون الصور القديمة"

say "1/8 تثبيت الحزم"
sudo apt-get update -y
sudo apt-get install -y git curl ca-certificates python3-venv python3-dev build-essential libpq-dev \
     libjpeg-dev zlib1g-dev postgresql-common openssl
# PostgreSQL 18 (نفس إصدار الكمبيوتر — ضروري لاسترجاع النسخة)
if ! dpkg -s postgresql-$PGVER >/dev/null 2>&1; then
  sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
  sudo apt-get install -y postgresql-$PGVER
fi
sudo systemctl enable --now postgresql

say "2/8 قاعدة البيانات"
DBPASS_FILE="$HOME/.iaj_dbpass"
[ -f "$DBPASS_FILE" ] || openssl rand -hex 16 > "$DBPASS_FILE"
chmod 600 "$DBPASS_FILE"
DBPASS=$(cat "$DBPASS_FILE")
sudo systemctl stop iaj 2>/dev/null || true
sudo -u postgres psql -v ON_ERROR_STOP=1 -q <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='iaj') THEN CREATE ROLE iaj LOGIN PASSWORD '$DBPASS';
  ELSE ALTER ROLE iaj PASSWORD '$DBPASS'; END IF;
END \$\$;
SQL
sudo -u postgres dropdb --if-exists iaj
sudo -u postgres createdb -O iaj -E UTF8 -T template0 iaj

say "3/8 الكود من GitHub"
sudo mkdir -p "$APP" && sudo chown "$USER":"$USER" "$APP"
if [ -d "$APP/.git" ]; then git -C "$APP" fetch -q origin main && git -C "$APP" reset -q --hard origin/main
else git clone -q "$REPO" "$APP"; fi

say "4/8 مكتبات Python"
python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q -r "$APP/requirements.txt"

say "5/8 استرجاع البيانات والصور"
echo "ملف القاعدة: $DUMP"
PGPASSWORD="$DBPASS" /usr/lib/postgresql/$PGVER/bin/pg_restore -h localhost -U iaj --no-owner --no-privileges -d iaj "$DUMP"
if [ -d "$SRC/media" ]; then rm -rf "$APP/media"; cp -r "$SRC/media" "$APP/media"; fi
mkdir -p "$APP/media" "$APP/backups" "$APP/logs"

say "6/8 ملف الإعدادات"
HOSTNAME_ONLY=$(echo "$SITE_URL" | sed -E 's#^https?://##; s#/.*$##')
SECRET=$(grep -s '^SECRET_KEY=' "$APP/.env" | cut -d= -f2- || true)
[ -n "$SECRET" ] || SECRET=$(openssl rand -base64 48 | tr -d '\n/+=')
cat > "$APP/.env" <<ENV
DATABASE_URL=postgresql://iaj:$DBPASS@localhost:5432/iaj
SECRET_KEY=$SECRET
DEBUG=False
SITE_URL=$SITE_URL
CSRF_TRUSTED_ORIGINS=$SITE_URL
ALLOWED_HOSTS=$HOSTNAME_ONLY,localhost,127.0.0.1
PORT=8000
HOST=127.0.0.1
BACKUP_DIR=$APP/backups
PG_BIN=/usr/lib/postgresql/$PGVER/bin
ENV
chmod 600 "$APP/.env"
cd "$APP"
venv/bin/python manage.py migrate --noinput
venv/bin/python manage.py collectstatic --noinput >/dev/null
venv/bin/python manage.py check
venv/bin/python manage.py shell -c "from award.models import News,Field,Track; from django.contrib.auth.models import User; print('الأخبار',News.objects.count(),'المجالات',Field.objects.count(),'المسارات',Track.objects.count(),'المستخدمون',User.objects.count())"

say "7/8 تشغيل دائم + نسخة احتياطية يومية"
sudo tee /etc/systemd/system/iaj.service >/dev/null <<UNIT
[Unit]
Description=IAJ Award website
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$APP
ExecStart=$APP/venv/bin/python serve.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now iaj
sudo systemctl restart iaj
( crontab -l 2>/dev/null | grep -v 'manage.py backup_site' ; echo "0 2 * * * cd $APP && venv/bin/python manage.py backup_site >> $APP/logs/backup.log 2>&1" ) | crontab -
sleep 4
curl -fsS -o /dev/null -w "الموقع يرد محلياً: HTTP %{http_code}\n" http://127.0.0.1:8000/ || echo "تنبيه: الموقع لم يرد — راجع: sudo journalctl -u iaj -n 50"

say "8/8 Cloudflare Tunnel"
if ! command -v cloudflared >/dev/null; then
  ARCH=$(dpkg --print-architecture)   # arm64 أو amd64
  curl -fsSL -o /tmp/cloudflared.deb "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$ARCH.deb"
  sudo dpkg -i /tmp/cloudflared.deb
fi
if [ -n "$CF_TOKEN" ]; then
  sudo cloudflared service uninstall >/dev/null 2>&1 || true
  sudo cloudflared service install "$CF_TOKEN"
  echo "✓ النفق مثبّت — تأكد في لوحة Cloudflare أن حالته Healthy"
else
  echo "لم يُعطَ رمز نفق. لاحقاً: sudo cloudflared service install <TOKEN>"
fi

say "تم"
echo "الموقع: $SITE_URL   (محلياً على الخادم: http://127.0.0.1:8000)"
echo "أوامر مفيدة:"
echo "  sudo systemctl status iaj        حالة الموقع"
echo "  sudo systemctl restart iaj       إعادة التشغيل"
echo "  sudo journalctl -u iaj -f        السجل المباشر"
echo "  bash $APP/deploy/oracle_update.sh  تحديث الكود من GitHub"
