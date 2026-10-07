# IAJ — local hosting (no Neon / Cloudinary / Render)

- Database: PostgreSQL on this PC (`DATABASE_URL` in `.env`).
- Files: everything uploaded (images, videos, PDFs) is saved in `media/`. Images are resized and compressed automatically.
- Server: Waitress (`serve.py`), works on Windows. Media served with Range support (video seeking).
- Public access: Cloudflare Tunnel → `http://localhost:8000` (see LOCAL_HOSTING.md).

Scripts: `1_setup.bat`, `import_cloud.bat` (repeat the Neon/Cloudinary copy), `2_start.bat`, `3_autostart.bat`, `stop_autostart.bat`, `backup_now.bat`.

Commands:
- `setup_local` — writes `.env`, creates the PostgreSQL database
- `import_from_cloud --yes` — copies all data from Neon (`CLOUD_DATABASE_URL`)
- `localize_media [--cleanup]` — downloads Cloudinary files and DB-stored images into `media/`
- `backup_site` / `restore_site <file> --yes`

## Hero media slideshow
- Admin → «بطاقة الفيديو والصور — الشرائح»: add any number of images, mp4 videos, or YouTube links (order, show/hide, optional cover and title).
- Images change automatically (seconds set in «إعدادات الموقع» → مدة عرض كل صورة). Videos never autoplay: they play with sound only when clicked; the show pauses while a video plays and moves on when it ends.
- Arrows, dots, swipe on mobile, pause on hover. Without slides, the old single image/video fields are used.
- Timer line on the slideshow is optional («إعدادات الموقع» → إظهار شريط الوقت).
- Each image slide has a click action: zoom to full screen (default, with next/previous between images), open a link, or nothing.

## Gradients and glass everywhere
- «الألوان والخطوط»: نمط الموقع (زجاجي بتدرّج / كلاسيكي) + ألوان البطاقات القلابة (كحلي / معكوس ذهبي).
- Every section background is a gradient: default sections, admin colors (auto second shade or «لون التدرّج الثاني»), overlays, header after scroll, footer.
- Glass cards for judges, timeline items, news sidebar (in addition to existing glass boxes).

## Countdown, ticker, flip cover, register button
- Countdown: show/hide days, hours, minutes, seconds (إعدادات الموقع). Hidden units roll into the next visible one.
- Ticker: font size, bar height, image size, separator image (centered between news), pulse and fade each with on/off and speed, option to apply effects to news logos.
- Flip cards: star removed, large bold title, optional cover image per field with darkness control.
- «سجل الآن»: rounded pill with the same glass/pulse/dot effects as the countdown pill.

## Search
- Site search: magnifier button in the header (or press /), live results while typing, full results page at /search/. Arabic-friendly (أ/ا، ة/ه، ى/ي، diacritics ignored).
- Admin search: box at the top of every admin page searching all tables at once (/admin/search/). Every admin table now has its own search box too.
- Flip card cover: English name larger and bolder.

## Logo, mobile menu, mobile hero, text slides
- Logo size settings (desktop / after scroll / mobile); the logo no longer shrinks when the header is crowded.
- Mobile menu closes when scrolling or tapping outside it. Mobile header no longer wraps to two lines.
- Mobile hero: media card sits right under the header, text card under it, scrolling title moved to the bottom.
- Text card under the video: several texts rotating automatically (time per text based on its length), 6 transition effects, arrows, swipe, pause on hover.

## Track details
- Each track: short summary, a details table (rows like target group, examples, requirements, criteria, outcomes — each line becomes a bullet), and a rich-text explanation.
- Admin: new tracks open with 6 suggested rows ready to fill (empty rows are ignored).
- Track modal shows summary + table + link to the full page, with «قدّم في هذا المسار» at the bottom.
- New page /tracks/<id>/ with breadcrumb, table, explanation, apply box, other tracks in the same field. Search results link to it.
- Sponsors heading uses the standard section heading (text + colors from admin).
- Each track: enable/disable (hidden everywhere when disabled; bulk actions too) and an optional scrolling notice strip (text + speed) shown in the track modal and page.
