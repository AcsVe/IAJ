#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
#  أزرار Termux:Widget لكل الأنظمة — زر لكل نظام بدل عشرات الأزرار
#
#   ★ لوحة الأنظمة            حالة كل المواقع في شاشة واحدة، ومنها قائمة أي نظام
#   ★ تحديث كل الأنظمة        تحديث كود كل الأنظمة على الهاتف دفعة واحدة
#   ★ فحص جاهزية الهاتف       هل كل شيء جاهز للطوارئ (doctor.sh)
#   ★ قفل أو فتح الأزرار      حماية الإجراءات الحساسة من الضغط بالخطأ
#   ★ English - عربي          لغة الرسائل
#   IAJ · الجائزة، TKT · التذاكر، …   قائمة النظام: حالته الآن وإجراءاته
#
#  يُشغَّل تلقائياً من configure لكل نظام ومن phone_fresh.sh، ويحذف الأزرار القديمة (IAJ 1، VEN 3، …).
#  لا يلمس أي زر آخر وضعه المستخدم في ~/.shortcuts.
# ================================================================
SC="$HOME/.shortcuts"
mkdir -p "$SC"
. "$HOME/iaj/standby/systems.sh"

mk() {
  printf '#!/data/data/com.termux/files/usr/bin/bash\n%s\necho; read -r -p "Enter ↵" _\n' "$2" > "$SC/$1"
  chmod +x "$SC/$1"
}

# the old buttons of every system (one per action) and the previous set of this script
for p in IAJ TKT VEN ATT TT BELL CLR SAS; do rm -f "$SC/$p "*; done
rm -f "$SC/★ "*

mk "★ لوحة الأنظمة"        "bash ~/iaj/standby/panel.sh"
mk "★ تحديث كل الأنظمة"    "bash ~/iaj/standby/panel.sh update-all"
mk "★ فحص جاهزية الهاتف"   "bash ~/iaj/standby/doctor.sh"
mk "★ قفل أو فتح الأزرار"  "bash ~/iaj/standby/panel.sh lock"
mk "★ English - عربي"      "bash ~/iaj/standby/panel.sh lang"

n=0
while IFS='|' read -r d code ar en url; do
  [ -f "$HOME/$d/standby/phone.sh" ] || continue
  mk "$code · $ar" "bash ~/iaj/standby/panel.sh $d"
  n=$((n + 1))
done <<< "$IAJ_SYSTEMS"

[ -n "$WIDGETS_QUIET" ] || printf '\n\033[1;36m» Termux:Widget: %s\033[0m\n' "$((n + 5)) buttons (5 + $n systems)"
