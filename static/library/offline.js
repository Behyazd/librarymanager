// library/static/library/offline.js
// ==================== Offline-First Manager ====================

const OfflineManager = {
    DB_NAME: 'LibraryOfflineDB',
    DB_VERSION: 1,
    db: null,
    isOnline: navigator.onLine,
    syncQueue: [],
    listeners: [],

    // ==================== مقداردهی اولیه ====================
    async init() {
        await this.openDB();
        this.setupListeners();
        await this.updateOnlineStatus();
        console.log('✅ OfflineManager initialized');
    },

    // ==================== باز کردن دیتابیس ====================
    openDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.DB_NAME, this.DB_VERSION);

            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.db = request.result;
                resolve(this.db);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // کتاب‌ها
                if (!db.objectStoreNames.contains('books')) {
                    const booksStore = db.createObjectStore('books', { keyPath: 'id' });
                    booksStore.createIndex('title', 'title', { unique: false });
                    booksStore.createIndex('author', 'author', { unique: false });
                    booksStore.createIndex('isbn', 'isbn', { unique: false });
                }

                // اعضا
                if (!db.objectStoreNames.contains('members')) {
                    const membersStore = db.createObjectStore('members', { keyPath: 'id' });
                    membersStore.createIndex('full_name', 'full_name', { unique: false });
                    membersStore.createIndex('national_id', 'national_id', { unique: false });
                }

                // امانت‌ها
                if (!db.objectStoreNames.contains('loans')) {
                    const loansStore = db.createObjectStore('loans', { keyPath: 'id' });
                    loansStore.createIndex('book', 'book', { unique: false });
                    loansStore.createIndex('member', 'member', { unique: false });
                }

                // صف تغییرات (Sync Queue)
                if (!db.objectStoreNames.contains('sync_queue')) {
                    const syncStore = db.createObjectStore('sync_queue', { keyPath: 'id', autoIncrement: true });
                    syncStore.createIndex('timestamp', 'timestamp', { unique: false });
                }

                // متادیتا
                if (!db.objectStoreNames.contains('metadata')) {
                    db.createObjectStore('metadata', { keyPath: 'key' });
                }
            };
        });
    },

    // ==================== راه‌اندازی Listenerها ====================
    setupListeners() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.notifyListeners('online');
            this.syncChanges();
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.notifyListeners('offline');
        });
    },

    // ==================== بروزرسانی وضعیت ====================
    async updateOnlineStatus() {
        this.isOnline = navigator.onLine;
        this.notifyListeners(this.isOnline ? 'online' : 'offline');
    },

    // ==================== افزودن Listener ====================
    addListener(callback) {
        this.listeners.push(callback);
    },

    // ==================== اطلاع‌رسانی به Listenerها ====================
    notifyListeners(event) {
        this.listeners.forEach(cb => cb(event));
    },

    // ==================== ذخیره کتاب‌ها ====================
    async saveBooks(books) {
        const tx = this.db.transaction('books', 'readwrite');
        const store = tx.objectStore('books');

        for (const book of books) {
            store.put(book);
        }

        return new Promise((resolve, reject) => {
            tx.oncomplete = () => resolve(true);
            tx.onerror = () => reject(tx.error);
        });
    },

    // ==================== دریافت کتاب‌ها ====================
    async getBooks() {
        const tx = this.db.transaction('books', 'readonly');
        const store = tx.objectStore('books');
        return new Promise((resolve, reject) => {
            const request = store.getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    // ==================== دریافت یک کتاب ====================
    async getBook(id) {
        const tx = this.db.transaction('books', 'readonly');
        const store = tx.objectStore('books');
        return new Promise((resolve, reject) => {
            const request = store.get(id);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    // ==================== ذخیره اعضا ====================
    async saveMembers(members) {
        const tx = this.db.transaction('members', 'readwrite');
        const store = tx.objectStore('members');

        for (const member of members) {
            store.put(member);
        }

        return new Promise((resolve, reject) => {
            tx.oncomplete = () => resolve(true);
            tx.onerror = () => reject(tx.error);
        });
    },

    // ==================== دریافت اعضا ====================
    async getMembers() {
        const tx = this.db.transaction('members', 'readonly');
        const store = tx.objectStore('members');
        return new Promise((resolve, reject) => {
            const request = store.getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    // ==================== ذخیره امانت‌ها ====================
    async saveLoans(loans) {
        const tx = this.db.transaction('loans', 'readwrite');
        const store = tx.objectStore('loans');

        for (const loan of loans) {
            store.put(loan);
        }

        return new Promise((resolve, reject) => {
            tx.oncomplete = () => resolve(true);
            tx.onerror = () => reject(tx.error);
        });
    },

    // ==================== دریافت امانت‌ها ====================
    async getLoans() {
        const tx = this.db.transaction('loans', 'readonly');
        const store = tx.objectStore('loans');
        return new Promise((resolve, reject) => {
            const request = store.getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    // ==================== ذخیره متادیتا ====================
    async saveMetadata(key, value) {
        const tx = this.db.transaction('metadata', 'readwrite');
        const store = tx.objectStore('metadata');
        store.put({ key, value, timestamp: Date.now() });

        return new Promise((resolve, reject) => {
            tx.oncomplete = () => resolve(true);
            tx.onerror = () => reject(tx.error);
        });
    },

    // ==================== دریافت متادیتا ====================
    async getMetadata(key) {
        const tx = this.db.transaction('metadata', 'readonly');
        const store = tx.objectStore('metadata');
        return new Promise((resolve, reject) => {
            const request = store.get(key);
            request.onsuccess = () => resolve(request.result?.value);
            request.onerror = () => reject(request.error);
        });
    },

    // ==================== افزودن به صف تغییرات ====================
    async addToQueue(action, endpoint, data) {
        const tx = this.db.transaction('sync_queue', 'readwrite');
        const store = tx.objectStore('sync_queue');

        const item = {
            action,
            endpoint,
            data,
            timestamp: Date.now(),
            status: 'pending'
        };

        store.add(item);

        return new Promise((resolve, reject) => {
            tx.oncomplete = () => {
                this.notifyListeners('queue_updated');
                resolve(true);
            };
            tx.onerror = () => reject(tx.error);
        });
    },

    // ==================== دریافت صف تغییرات ====================
    async getQueue() {
        const tx = this.db.transaction('sync_queue', 'readonly');
        const store = tx.objectStore('sync_queue');
        return new Promise((resolve, reject) => {
            const request = store.getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    },

    // ==================== حذف از صف ====================
    async removeFromQueue(id) {
        const tx = this.db.transaction('sync_queue', 'readwrite');
        const store = tx.objectStore('sync_queue');
        store.delete(id);

        return new Promise((resolve, reject) => {
            tx.oncomplete = () => {
                this.notifyListeners('queue_updated');
                resolve(true);
            };
            tx.onerror = () => reject(tx.error);
        });
    },

    // ==================== پاک کردن صف ====================
    async clearQueue() {
        const tx = this.db.transaction('sync_queue', 'readwrite');
        const store = tx.objectStore('sync_queue');
        store.clear();

        return new Promise((resolve, reject) => {
            tx.oncomplete = () => resolve(true);
            tx.onerror = () => reject(tx.error);
        });
    },

    // ==================== Sync تغییرات با سرور ====================
    async syncChanges() {
        if (!this.isOnline) {
            console.log('❌ آفلاین هستیم، Sync انجام نمی‌شود');
            return;
        }

        const queue = await this.getQueue();
        if (queue.length === 0) {
            console.log('✅ صف خالی است');
            return;
        }

        console.log(`🔄 شروع Sync ${queue.length} تغییر`);

        for (const item of queue) {
            try {
                const response = await fetch(item.endpoint, {
                    method: item.action,
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': this.getCookie('csrftoken'),
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify(item.data),
                });

                if (response.ok) {
                    await this.removeFromQueue(item.id);
                    console.log(`✅ Sync موفق: ${item.endpoint}`);
                } else {
                    console.log(`❌ Sync ناموفق: ${item.endpoint} - ${response.status}`);
                }
            } catch (error) {
                console.error(`❌ خطا در Sync:`, error);
                break; // اگر خطای شبکه بود، متوقف شو
            }
        }

        this.notifyListeners('sync_complete');
    },

    // ==================== دریافت Cookie ====================
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    },

    // ==================== پیش‌بارگذاری داده‌ها ====================
    async preloadData() {
        if (!this.isOnline) {
            console.log('❌ آفلاین هستیم، پیش‌بارگذاری انجام نمی‌شود');
            return;
        }

        try {
            console.log('🔄 شروع پیش‌بارگذاری داده‌ها...');

            // دریافت کتاب‌ها
            const booksResponse = await fetch('/api/books/?page_size=1000', {
                credentials: 'same-origin',
            });
            if (booksResponse.ok) {
                const booksData = await booksResponse.json();
                const books = booksData.results || booksData;
                await this.saveBooks(books);
                console.log(`✅ ${books.length} کتاب ذخیره شد`);
            }

            // دریافت اعضا
            const membersResponse = await fetch('/api/members/?page_size=1000', {
                credentials: 'same-origin',
            });
            if (membersResponse.ok) {
                const membersData = await membersResponse.json();
                const members = membersData.results || membersData;
                await this.saveMembers(members);
                console.log(`✅ ${members.length} عضو ذخیره شد`);
            }

            // دریافت امانت‌ها
            const loansResponse = await fetch('/api/loans/?page_size=1000', {
                credentials: 'same-origin',
            });
            if (loansResponse.ok) {
                const loansData = await loansResponse.json();
                const loans = loansData.results || loansData;
                await this.saveLoans(loans);
                console.log(`✅ ${loans.length} امانت ذخیره شد`);
            }

            await this.saveMetadata('last_sync', Date.now());
            console.log('✅ پیش‌بارگذاری کامل شد');

        } catch (error) {
            console.error('❌ خطا در پیش‌بارگذاری:', error);
        }
    },

    // ==================== بررسی نیاز به Sync ====================
    async needsSync() {
        const queue = await this.getQueue();
        return queue.length > 0;
    },

    // ==================== تعداد آیتم‌های صف ====================
    async getQueueCount() {
        const queue = await this.getQueue();
        return queue.length;
    }
};

// ==================== راه‌اندازی خودکار ====================
document.addEventListener('DOMContentLoaded', async () => {
    await OfflineManager.init();

    // اگر آنلاین هستیم، داده‌ها را پیش‌بارگذاری کن
    if (OfflineManager.isOnline) {
        setTimeout(() => OfflineManager.preloadData(), 2000);
    }

    // Sync خودکار هر ۵ دقیقه
    setInterval(() => {
        if (OfflineManager.isOnline) {
            OfflineManager.syncChanges();
        }
    }, 5 * 60 * 1000);
});

// ==================== در دسترس قرار دادن جهانی ====================
window.OfflineManager = OfflineManager;