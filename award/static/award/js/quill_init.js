// تهيئة محرر Quill لحقول الأخبار في لوحة التحكم
document.addEventListener('DOMContentLoaded', function () {
    if (typeof Quill === 'undefined') return;
    document.querySelectorAll('.quill-wrapper > div[id$="_editor"]').forEach(function (editorEl) {
        var textarea = document.getElementById(editorEl.id.replace(/_editor$/, ''));
        if (!textarea) return;
        var quill = new Quill(editorEl, {
            theme: 'snow',
            modules: {
                toolbar: [
                    [{ 'header': [2, 3, 4, false] }],
                    [{ 'direction': 'rtl' }, { 'align': [] }],
                    ['bold', 'italic', 'underline', 'strike'],
                    [{ 'color': [] }, { 'background': [] }],
                    [{ 'list': 'ordered' }, { 'list': 'bullet' }],
                    ['link', 'image'],
                    ['clean']
                ]
            }
        });
        quill.root.setAttribute('dir', 'rtl');
        quill.root.style.textAlign = 'right';
        if (textarea.value) quill.root.innerHTML = textarea.value;
        var sync = function () { textarea.value = quill.root.innerHTML; };
        quill.on('text-change', sync);
        var form = textarea.closest('form');
        if (form) form.addEventListener('submit', sync);
    });
});
