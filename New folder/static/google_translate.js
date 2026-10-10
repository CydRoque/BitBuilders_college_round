(function () {
    const toggle = document.getElementById('chat-translate-toggle');
    const container = document.getElementById('chat-google-translate');
    if (!toggle || !container) return;

    let scriptRequested = false;

    function initializeGoogleTranslate() {
        if (!window.google || !window.google.translate) return;
        new window.google.translate.TranslateElement({
            pageLanguage: 'en',
            includedLanguages: 'en,hi,kn,mr,ta,te',
            layout: window.google.translate.TranslateElement.InlineLayout.SIMPLE,
            autoDisplay: false
        }, 'chat-google-translate');
    }

    window.googleTranslateElementInit = initializeGoogleTranslate;

    toggle.addEventListener('click', function () {
        const isOpening = container.classList.contains('hidden');
        container.classList.toggle('hidden', !isOpening);
        toggle.setAttribute('aria-expanded', String(isOpening));
        if (!isOpening || scriptRequested) return;

        scriptRequested = true;
        const script = document.createElement('script');
        script.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
        script.async = true;
        script.onerror = function () {
            scriptRequested = false;
            container.textContent = 'Google Translate could not load. Check your internet connection and try again.';
        };
        document.head.appendChild(script);
    });
})();
