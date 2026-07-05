document.addEventListener('DOMContentLoaded', function() {
    var editors = document.querySelectorAll('.quill-wrapper > div[id$="_editor"]');
    editors.forEach(function(editorEl) {
        var textareaId = editorEl.id.replace('_editor', '');
        var textarea = document.getElementById(textareaId);
        var quill = new Quill(editorEl, {
            theme: 'snow',
            modules: {
                toolbar: [
                    [{ 'direction': 'rtl' }, { 'direction': 'ltr' }, { 'align': [] }],
                    ['bold', 'italic', 'underline', 'strike'],
                    [{ 'color': [] }, { 'background': [] }],
                    [{ 'list': 'ordered' }, { 'list': 'bullet' }],
                    ['link', 'image'],
                    ['clean']
                ]
            }
        });
        // تحميل المحتوى الموجود
        if (textarea && textarea.value) {
            quill.root.innerHTML = textarea.value;
        }
        // حفظ HTML في textarea عند الإرسال
        var form = textarea ? textarea.closest('form') : null;
        if (form) {
            form.addEventListener('submit', function() {
                textarea.value = quill.root.innerHTML;
            });
        }
        // حفظ تلقائي كل 5 ثواني (لحالة الحفظ التلقائي في الإدمن)
        setInterval(function() {
            if (textarea) {
                textarea.value = quill.root.innerHTML;
            }
        }, 5000);
    });
});