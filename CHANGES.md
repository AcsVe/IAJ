# IAJ — Fixes (Oct 2026)

## Deploy
1. Push to GitHub → Render redeploys.
2. Run once: `python manage.py migrate` (safe on the live DB — tested against a copy of the schema).
3. Optional, to move old Cloudinary images into the DB: `python manage.py move_images_to_db --dry-run` then without `--dry-run`.

## Image storage
- New image uploads are saved in the Postgres database (`StoredFile`) and served from `/media/db/...` (auto-resized to max 2400px, cached 1 year).
- Videos and PDFs still go to Cloudinary. Old Cloudinary image links keep working.
- Replacing/deleting an image removes the old copy automatically.
- Admin: "الصور المخزّنة في قاعدة البيانات" shows what is stored and its size.

## Hero
- Admin → إعدادات الموقع → "صورة جانبية": picture beside the main hero picture (left on desktop, below on mobile). Empty = main picture full width.
- Moving credits stay over the main picture. Speed: `creditsRise 40s` in home.html.

## Ticker
- Speed now comes from Admin → إعدادات الشريط → السرعة (pixels/second: 40 slow, 60 medium, 100 fast). Was hard-coded to 100 before.
- Font colour and fade width settings now apply; no gaps with short messages; tap to pause on mobile.

## Scroll arrows
- Up and down arrows both pulse and step exactly one section each way (incl. news section and footer).

## Errors fixed
- Photos page crashed (wrong model) · Submit crashed after saving (missing success.html)
- News list always empty / news detail blank (wrong variable names)
- News editor invisible in admin (quill_init.js wrong path)
- Inner pages had no logo/footer text/button label · Admin CSRF on Render (proxy https)
- DEBUG=True crashed (MEDIA_URL missing) · 46px horizontal scroll (flip cards) · migration drift
- Removed unused base_mob.html / home_mob.html — one responsive template now.
