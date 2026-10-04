if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.getRegistrations().then((registrations) => {
            registrations.forEach((registration) => registration.unregister());
        }).catch(() => { });

        if (window.isSecureContext || location.hostname === 'localhost' || location.hostname === '127.0.0.1') {
            navigator.serviceWorker.register('/service-worker.js', { scope: '/' }).catch(() => { });
        }
    });
}

console.log('Legacy Vault app loaded');
