"""يبني award/static/award/js/icons.js: أيقونات SVG للعناصر التي تُنشئها الجافاسكربت بعد تحميل الصفحة.
(الأيقونات في HTML نفسه تُملأ على السيرفر — انظر award/svg_icons.py). يُشغَّل تلقائياً في update.bat."""
import json
import os
import re

from django.core.management.base import BaseCommand

from award.svg_icons import MODIFIERS, js_map

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # مجلد award

JS = r"""/* أيقونات SVG للعناصر المضافة بالجافاسكربت — مولَّد تلقائياً (build_icons_js). Font Awesome Free 6.5.1, CC BY 4.0 */
(function () {
  var M = __MAP__;
  var MOD = /^fa-(fw|spin|pulse|xs|sm|lg|xl|2xs|2xl|\dx|10x|rotate-(90|180|270)|flip-(horizontal|vertical|both)|solid|regular|brands|beat|fade|bounce|shake|border|inverse|li|stack(-\dx)?)$/;
  function fill(el) {
    var cls = (el.getAttribute('class') || '').split(/\s+/), name = null;
    for (var i = 0; i < cls.length; i++) { var c = cls[i]; if (c.indexOf('fa-') === 0 && !MOD.test(c)) { name = c.slice(3); break; } }
    var ic = name && M[name];
    if (!ic || el.getAttribute('data-ic') === name) return;
    var d = typeof ic[2] === 'string' ? [ic[2]] : ic[2], p = '';
    for (var j = 0; j < d.length; j++) p += '<path d="' + d[j] + '"/>';
    el.innerHTML = '<svg class="ic" viewBox="0 0 ' + ic[0] + ' ' + ic[1] + '" width="' + (ic[0] / ic[1]).toFixed(3) + 'em" height="1em" fill="currentColor" aria-hidden="true" focusable="false">' + p + '</svg>';
    el.setAttribute('data-ic', name);
  }
  function scan(root) {
    if (root.nodeType !== 1) return;
    if (root.tagName === 'I' && /\bfa-/.test(root.className)) fill(root);
    var list = root.querySelectorAll ? root.querySelectorAll('i[class*="fa-"]') : [];
    for (var i = 0; i < list.length; i++) if (!list[i].firstElementChild || list[i].getAttribute('data-ic')) fill(list[i]);
  }
  new MutationObserver(function (muts) {
    muts.forEach(function (m) {
      if (m.type === 'attributes') { if (m.target.tagName === 'I') fill(m.target); return; }
      for (var i = 0; i < m.addedNodes.length; i++) scan(m.addedNodes[i]);
    });
  }).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
  if (document.readyState !== 'loading') scan(document.body); else document.addEventListener('DOMContentLoaded', function () { scan(document.body); });
})();
"""


class Command(BaseCommand):
    help = 'بناء ملف أيقونات SVG للجافاسكربت'

    def handle(self, *args, **opts):
        names = set()
        for root, _dirs, files in os.walk(HERE):
            if 'migrations' in root or 'static' in root:
                continue
            for f in files:
                if f.endswith(('.html', '.py', '.js')):
                    txt = open(os.path.join(root, f), encoding='utf-8', errors='ignore').read()
                    names.update(m for m in re.findall(r'\bfa-([a-z0-9-]+)', txt) if 'fa-' + m not in MODIFIERS)
        try:   # الأيقونات المكتوبة في لوحة التحكم
            from django.apps import apps
            for model in apps.get_app_config('award').get_models():
                for fld in model._meta.fields:
                    if fld.name in ('icon', 'icon_class'):
                        for v in model.objects.values_list(fld.name, flat=True):
                            names.update(re.findall(r'\bfa-([a-z0-9-]+)', v or ''))
        except Exception:
            pass
        data = js_map(sorted(names))
        out = os.path.join(HERE, 'static', 'award', 'js', 'icons.js')
        with open(out, 'w', encoding='utf-8') as fh:
            fh.write(JS.replace('__MAP__', json.dumps(data, separators=(',', ':'))))
        self.stdout.write(f'icons.js: {len(data)} icons, {os.path.getsize(out) // 1024} KB')
