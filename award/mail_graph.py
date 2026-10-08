"""
إرسال البريد عبر Microsoft 365 (Graph API) من صندوق مثل info@iajaward.org.
يعمل على المنفذ 443 فقط — لا يتأثر بحجب منافذ SMTP في الشبكة.

.env:
  MS_TENANT_ID=...
  MS_CLIENT_ID=...
  MS_CLIENT_SECRET=...
  MS_SENDER=info@iajaward.org
يحتاج التطبيق في Entra صلاحية Mail.Send (Application) مع Grant admin consent.
"""
import base64
import threading
import time

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

_token = {'value': None, 'exp': 0}
_lock = threading.Lock()


def _get_token():
    with _lock:
        if _token['value'] and time.time() < _token['exp'] - 120:
            return _token['value']
        r = requests.post(
            f'https://login.microsoftonline.com/{settings.MS_TENANT_ID}/oauth2/v2.0/token',
            data={'client_id': settings.MS_CLIENT_ID, 'client_secret': settings.MS_CLIENT_SECRET,
                  'scope': 'https://graph.microsoft.com/.default', 'grant_type': 'client_credentials'},
            timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f'Microsoft login failed ({r.status_code}): {r.text[:400]}')
        data = r.json()
        _token['value'] = data['access_token']
        _token['exp'] = time.time() + int(data.get('expires_in', 3600))
        return _token['value']


def _recipients(addrs):
    return [{'emailAddress': {'address': a}} for a in addrs if a]


class GraphEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for msg in email_messages:
            try:
                self._send(msg)
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, msg):
        html = None
        for content, mimetype in getattr(msg, 'alternatives', []) or []:
            if mimetype == 'text/html':
                html = content
        message = {
            'subject': msg.subject,
            'body': {'contentType': 'HTML' if html else 'Text', 'content': html or msg.body},
            'toRecipients': _recipients(msg.to),
        }
        if msg.cc:
            message['ccRecipients'] = _recipients(msg.cc)
        if msg.bcc:
            message['bccRecipients'] = _recipients(msg.bcc)
        if msg.reply_to:
            message['replyTo'] = _recipients(msg.reply_to)
        atts = []
        for a in msg.attachments or []:
            if isinstance(a, tuple):
                name, content, mime = a
                if isinstance(content, str):
                    content = content.encode()
                atts.append({'@odata.type': '#microsoft.graph.fileAttachment', 'name': name,
                             'contentType': mime or 'application/octet-stream',
                             'contentBytes': base64.b64encode(content).decode()})
        if atts:
            message['attachments'] = atts
        sender = settings.MS_SENDER
        r = requests.post(f'https://graph.microsoft.com/v1.0/users/{sender}/sendMail',
                          headers={'Authorization': f'Bearer {_get_token()}', 'Content-Type': 'application/json'},
                          json={'message': message, 'saveToSentItems': True}, timeout=30)
        if r.status_code not in (200, 202):
            raise RuntimeError(f'Graph sendMail failed ({r.status_code}): {r.text[:400]}')
