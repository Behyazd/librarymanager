// library/static/library/dark-mode.js
// ==================== Dark Mode Manager ====================

const DarkMode = {
    STORAGE_KEY: 'library_theme',
    currentTheme: 'light',

    // ==================== مقداردهی اولیه ====================
    init() {
        // خواندن تم از localStorage
        const savedTheme = localStorage.getItem(this.STORAGE_KEY);

        if (savedTheme) {
            this.currentTheme = savedTheme;
        } else {
            // بررسی تم سیستم‌عامل
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                this.currentTheme = 'dark';
            }
        }

        this.applyTheme(this.currentTheme);
        this.setupListeners();
        this.setupSystemThemeListener();
    },

    // ==================== اعمال تم ====================
    applyTheme(theme) {
        this.currentTheme = theme;
        document.documentElement.setAttribute('data-theme', theme);

        // ذخیره در localStorage
        localStorage.setItem(this.STORAGE_KEY, theme);

        // بروزرسانی دکمه
        this.updateButton();

        // بروزرسانی meta theme-color
        const metaThemeColor = document.querySelector('meta[name="theme-color"]');
        if (metaThemeColor) {
            metaThemeColor.setAttribute('content', theme === 'dark' ? '#1a1a2e' : '#0A76D6');
        }
    },

    // ==================== تغییر تم ====================
    toggle() {
        const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.applyTheme(newTheme);
    },

    // ==================== بروزرسانی دکمه ====================
    updateButton() {
        const btn = document.getElementById('dark-mode-toggle');
        if (!btn) return;

        if (this.currentTheme === 'dark') {
            btn.innerHTML = '☀️';
            btn.title = 'حالت روز';
        } else {
            btn.innerHTML = '🌙';
            btn.title = 'حالت شب';
        }
    },

    // ==================== تنظیم Listener ====================
    setupListeners() {
        const btn = document.getElementById('dark-mode-toggle');
        if (btn) {
            btn.addEventListener('click', () => this.toggle());
        }
    },

    // ==================== Listener برای تغییر تم سیستم ====================
    setupSystemThemeListener() {
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                // فقط اگر کاربر تم را دستی تغییر نداده باشد
                if (!localStorage.getItem(this.STORAGE_KEY)) {
                    this.applyTheme(e.matches ? 'dark' : 'light');
                }
            });
        }
    }
};

// ==================== راه‌اندازی خودکار ====================
// برای جلوگیری از flicker، این را در بالای head صدا می‌زنیم
(function() {
    const savedTheme = localStorage.getItem('library_theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
})();

document.addEventListener('DOMContentLoaded', () => {
    DarkMode.init();
});

window.DarkMode = DarkMode;