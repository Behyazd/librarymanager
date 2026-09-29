// library/static/library/pwa-install.js
// ==================== PWA Install Manager ====================

const PWAInstall = {
    deferredPrompt: null,
    installButton: null,

    init() {
        this.installButton = document.getElementById('pwa-install-btn');

        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            this.deferredPrompt = e;
            this.showInstallButton();
        });

        window.addEventListener('appinstalled', () => {
            console.log('✅ PWA نصب شد');
            this.hideInstallButton();
            this.deferredPrompt = null;
        });

        // بررسی اینکه آیا قبلاً نصب شده است
        if (window.matchMedia('(display-mode: standalone)').matches) {
            this.hideInstallButton();
        }

        // بررسی دکمه
        if (this.installButton) {
            this.installButton.addEventListener('click', () => this.install());
        }
    },

    showInstallButton() {
        if (this.installButton) {
            this.installButton.style.display = 'inline-flex';
        }
    },

    hideInstallButton() {
        if (this.installButton) {
            this.installButton.style.display = 'none';
        }
    },

    async install() {
        if (!this.deferredPrompt) {
            alert('این مرورگر از نصب PWA پشتیبانی نمی‌کند یا برنامه قبلاً نصب شده است.');
            return;
        }

        this.deferredPrompt.prompt();
        const { outcome } = await this.deferredPrompt.userChoice;

        console.log(`User choice: ${outcome}`);

        this.deferredPrompt = null;
        this.hideInstallButton();
    }
};

document.addEventListener('DOMContentLoaded', () => {
    PWAInstall.init();
});

window.PWAInstall = PWAInstall;