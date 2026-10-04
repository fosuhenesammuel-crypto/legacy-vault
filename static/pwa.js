if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/service-worker.js').catch(() => undefined);
    });
}

const installButton = document.querySelector('#install-app');
const iosInstallHint = document.querySelector('#ios-install-hint');
const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);

if (isIos && !navigator.standalone && iosInstallHint) {
    iosInstallHint.hidden = false;
}

let installPrompt;
window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    installPrompt = event;
    if (installButton) installButton.hidden = false;
});

installButton?.addEventListener('click', async () => {
    if (!installPrompt) return;
    await installPrompt.prompt();
    installPrompt = undefined;
    installButton.hidden = true;
});

window.addEventListener('appinstalled', () => {
    if (installButton) installButton.hidden = true;
});