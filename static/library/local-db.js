// static/library/local-db.js
// ==================== Library Local Database (Dexie.js) ====================

import Dexie from 'https://cdn.jsdelivr.net/npm/dexie@4.0.1/dist/modern/dexie.min.mjs';

const db = new Dexie('LibraryLocalDB');

// ==================== Schema ====================
db.version(1).stores({
    books: '++local_id, server_id, title, author, isbn, series, volume, updated_at, sync_status, sync_action',
    members: '++local_id, server_id, full_name, national_id, member_code, updated_at, sync_status, sync_action',
    loans: '++local_id, server_id, book_id, member_id, status, updated_at, sync_status, sync_action',
    sync_queue: '++id, model_name, object_id, action, created_at, status',
    metadata: 'key',
    sync_log: '++id, action, status, created_at',
    conflicts: '++id, model_name, object_id, resolution, created_at'
});

// ==================== Utility Functions ====================

function getCookie(name) {
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
}

function nowISO() {
    return new Date().toISOString();
}

// ==================== Device ID ====================

export async function getDeviceId() {
    let deviceId = await db.metadata.get('device_id');
    if (!deviceId) {
        const id = 'device_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        await db.metadata.put({ key: 'device_id', value: id });
        return id;
    }
    return deviceId.value;
}

export async function getDeviceName() {
    let deviceName = await db.metadata.get('device_name');
    if (!deviceName) {
        const ua = navigator.userAgent;
        let name = 'دستگاه ناشناخته';
        if (/Android/i.test(ua)) name = 'اندروید';
        else if (/iPhone|iPad/i.test(ua)) name = 'iOS';
        else if (/Windows/i.test(ua)) name = 'ویندوز';
        else if (/Mac/i.test(ua)) name = 'مک';
        else if (/Linux/i.test(ua)) name = 'لینوکس';
        await db.metadata.put({ key: 'device_name', value: name });
        return name;
    }
    return deviceName.value;
}

export async function setDeviceName(name) {
    await db.metadata.put({ key: 'device_name', value: name });
}

// ==================== Books CRUD ====================

export async function saveBook(book) {
    const now = nowISO();
    let localId = book.local_id;

    if (!localId) {
        // کتاب جدید
        const newBook = {
            ...book,
            created_at: now,
            updated_at: now,
            sync_status: 'pending',
            sync_action: 'create'
        };
        delete newBook.local_id;
        localId = await db.books.add(newBook);

        await addToQueue('book', localId, 'create', newBook);
        await logSync('create_book', 'success', `کتاب جدید: ${book.title}`);
    } else {
        // ویرایش
        await db.books.update(localId, {
            ...book,
            updated_at: now,
            sync_status: 'pending',
            sync_action: 'update'
        });

        await addToQueue('book', localId, 'update', book);
        await logSync('update_book', 'success', `ویرایش: ${book.title}`);
    }

    return localId;
}

export async function getBooks() {
    return await db.books.toArray();
}

export async function getBook(local_id) {
    return await db.books.get(local_id);
}

export async function getBookByServerId(server_id) {
    return await db.books.where('server_id').equals(server_id).first();
}

export async function getBookByISBN(isbn) {
    if (!isbn) return null;
    return await db.books.where('isbn').equals(isbn).first();
}

export async function searchBooks(query) {
    if (!query) return await getBooks();

    const q = query.toLowerCase();
    const all = await db.books.toArray();

    return all.filter(book =>
        (book.title && book.title.toLowerCase().includes(q)) ||
        (book.author && book.author.toLowerCase().includes(q)) ||
        (book.isbn && book.isbn.includes(q))
    );
}

export async function deleteBook(local_id) {
    const book = await db.books.get(local_id);
    if (!book) return;

    // اگر در سرور وجود دارد
    if (book.server_id) {
        await addToQueue('book', local_id, 'delete', { server_id: book.server_id });
        await logSync('delete_book', 'success', `حذف: ${book.title}`);
    } else {
        // فقط در صف، حذف شود
        await db.sync_queue.where({ object_id: String(local_id), model_name: 'book' }).delete();
    }

    await db.books.delete(local_id);
}

export async function clearBooks() {
    await db.books.clear();
}

// ==================== Members CRUD ====================

export async function saveMember(member) {
    const now = nowISO();
    let localId = member.local_id;

    if (!localId) {
        const newMember = {
            ...member,
            created_at: now,
            updated_at: now,
            sync_status: 'pending',
            sync_action: 'create'
        };
        delete newMember.local_id;
        localId = await db.members.add(newMember);

        await addToQueue('member', localId, 'create', newMember);
        await logSync('create_member', 'success', `عضو جدید: ${member.full_name}`);
    } else {
        await db.members.update(localId, {
            ...member,
            updated_at: now,
            sync_status: 'pending',
            sync_action: 'update'
        });

        await addToQueue('member', localId, 'update', member);
        await logSync('update_member', 'success', `ویرایش عضو: ${member.full_name}`);
    }

    return localId;
}

export async function getMembers() {
    return await db.members.toArray();
}

export async function getMember(local_id) {
    return await db.members.get(local_id);
}

export async function getMemberByNationalId(national_id) {
    if (!national_id) return null;
    return await db.members.where('national_id').equals(national_id).first();
}

export async function deleteMember(local_id) {
    const member = await db.members.get(local_id);
    if (!member) return;

    if (member.server_id) {
        await addToQueue('member', local_id, 'delete', { server_id: member.server_id });
    }

    await db.members.delete(local_id);
}

export async function clearMembers() {
    await db.members.clear();
}

// ==================== Loans CRUD ====================

export async function saveLoan(loan) {
    const now = nowISO();
    let localId = loan.local_id;

    if (!localId) {
        const newLoan = {
            ...loan,
            created_at: now,
            updated_at: now,
            sync_status: 'pending',
            sync_action: 'create'
        };
        delete newLoan.local_id;
        localId = await db.loans.add(newLoan);

        await addToQueue('loan', localId, 'create', newLoan);
    } else {
        await db.loans.update(localId, {
            ...loan,
            updated_at: now,
            sync_status: 'pending',
            sync_action: 'update'
        });

        await addToQueue('loan', localId, 'update', loan);
    }

    return localId;
}

export async function getLoans() {
    return await db.loans.toArray();
}

export async function getLoan(local_id) {
    return await db.loans.get(local_id);
}

export async function getLoansByBook(bookLocalId) {
    return await db.loans.where('book_id').equals(bookLocalId).toArray();
}

export async function getLoansByMember(memberLocalId) {
    return await db.loans.where('member_id').equals(memberLocalId).toArray();
}

export async function deleteLoan(local_id) {
    const loan = await db.loans.get(local_id);
    if (!loan) return;

    if (loan.server_id) {
        await addToQueue('loan', local_id, 'delete', { server_id: loan.server_id });
    }

    await db.loans.delete(local_id);
}

export async function clearLoans() {
    await db.loans.clear();
}

// ==================== Sync Queue ====================

export async function addToQueue(model_name, object_id, action, data) {
    const queueItem = {
        model_name: model_name,
        object_id: String(object_id),
        action: action,
        data: data,
        created_at: nowISO(),
        status: 'pending'
    };

    return await db.sync_queue.add(queueItem);
}

export async function getPendingChanges() {
    return await db.sync_queue
        .where('status')
        .equals('pending')
        .toArray();
}

export async function getPendingCount() {
    return await db.sync_queue.where('status').equals('pending').count();
}

export async function getAllQueueItems() {
    return await db.sync_queue.orderBy('created_at').reverse().toArray();
}

export async function markAsSynced(queue_id, server_id = null) {
    const item = await db.sync_queue.get(queue_id);
    if (!item) return;

    // به‌روزرسانی صف
    await db.sync_queue.update(queue_id, {
        status: 'synced',
        synced_at: nowISO()
    });

    // به‌روزرسانی شیء اصلی
    if (item.model_name === 'book' && server_id) {
        const book = await db.books.get(parseInt(item.object_id));
        if (book) {
            await db.books.update(book.local_id, {
                server_id: server_id,
                sync_status: 'synced',
                sync_action: null
            });
        }
    } else if (item.model_name === 'member' && server_id) {
        const member = await db.members.get(parseInt(item.object_id));
        if (member) {
            await db.members.update(member.local_id, {
                server_id: server_id,
                sync_status: 'synced',
                sync_action: null
            });
        }
    } else if (item.model_name === 'loan' && server_id) {
        const loan = await db.loans.get(parseInt(item.object_id));
        if (loan) {
            await db.loans.update(loan.local_id, {
                server_id: server_id,
                sync_status: 'synced',
                sync_action: null
            });
        }
    }
}

export async function clearSyncedQueue() {
    await db.sync_queue.where('status').equals('synced').delete();
}

export async function clearAllQueue() {
    await db.sync_queue.clear();
}

// ==================== Sync Push ====================

export async function pushChanges(apiUrl = '', token = null) {
    const changes = await getPendingChanges();

    if (changes.length === 0) {
        return {
            success: true,
            message: 'تغییری برای ارسال نیست',
            results: [],
            pushed_count: 0
        };
    }

    // آماده‌سازی داده‌ها
    const payload = [];
    for (const change of changes) {
        let data = {};

        if (change.model_name === 'book') {
            const book = await db.books.get(parseInt(change.object_id));
            data = book ? { ...book } : {};
            if (data.local_id) data.local_id = change.object_id;
        } else if (change.model_name === 'member') {
            const member = await db.members.get(parseInt(change.object_id));
            data = member ? { ...member } : {};
            if (data.local_id) data.local_id = change.object_id;
        } else if (change.model_name === 'loan') {
            const loan = await db.loans.get(parseInt(change.object_id));
            data = loan ? { ...loan } : {};
            if (data.local_id) data.local_id = change.object_id;
        }

        // اگر حذف است، فقط server_id لازم است
        if (change.action === 'delete') {
            data = { server_id: data.server_id };
        }

        payload.push({
            queue_id: change.id,
            model_name: change.model_name,
            object_id: change.object_id,
            action: change.action,
            server_id: data.server_id || null,
            data: data
        });
    }

    const deviceId = await getDeviceId();

    try {
        const response = await fetch(`${apiUrl}/api/sync/push/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
                // ❌ خط Authorization حذف شد
            },
            credentials: 'same-origin',  // ✅ ارسال کوکی session
            body: JSON.stringify({
                changes: payload,
                device_id: deviceId,
            })
        });

        const result = await response.json();

        if (result.success) {
            if (result.results) {
                for (const item of result.results) {
                    await markAsSynced(item.queue_id, item.server_id);
                }
            }
            await clearSyncedQueue();
            await logSync('push', 'success', `${result.pushed_count} تغییر ارسال شد`);

            return {
                success: true,
                results: result.results,
                pushed_count: result.pushed_count,
                failed_count: result.failed_count || 0,
            };
        } else {
            await logSync('push', 'failed', result.error || 'خطای نامشخص');
            return {
                success: false,
                error: result.error || 'خطا در ارسال',
                errors: result.errors || [],
            };
        }
    } catch (error) {
        await logSync('push', 'failed', error.message);
        return { success: false, error: error.message };
    }
}

// ==================== Sync Pull ====================

export async function pullChanges(apiUrl = '', token = null) {
    const lastSync = await db.metadata.get('last_sync');
    const since = lastSync ? lastSync.value : null;
    const deviceId = await getDeviceId();

    try {
        let url = `${apiUrl}/api/sync/pull/?device_id=${deviceId}`;
        if (since) {
            url += `&since=${since}`;
        }

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                // ❌ خط Authorization حذف شد
            },
            credentials: 'same-origin',  // ✅ ارسال کوکی session
        });

        const result = await response.json();

        if (result.success) {
            // ... بقیه کد
        }
        // ...
    } catch (error) {
        // ...
    }
}

// ==================== Merge ====================

async function mergeBook(serverBook) {
    const localBook = await db.books.where('server_id').equals(serverBook.id).first();

    if (!localBook) {
        // کتاب جدید از سرور
        await db.books.add({
            server_id: serverBook.id,
            title: serverBook.title || '',
            subtitle: serverBook.subtitle || '',
            author: serverBook.author || '',
            author_dates: serverBook.author_dates || '',
            isbn: serverBook.isbn || '',
            publisher: serverBook.publisher || '',
            publish_place: serverBook.publish_place || '',
            publish_year: serverBook.publish_year || '',
            pages: serverBook.pages || '',
            dimensions: serverBook.dimensions || '',
            dewey_class: serverBook.dewey_class || '',
            lcc_class: serverBook.lcc_class || '',
            subject: serverBook.subject || '',
            notes: serverBook.notes || '',
            fapa: serverBook.fapa || '',
            volume: serverBook.volume || '',
            series: serverBook.series || '',
            series_number: serverBook.series_number || null,
            language: serverBook.language || 'فارسی',
            condition: serverBook.condition || 'good',
            location: serverBook.location || '',
            total_copies: serverBook.total_copies || 1,
            available_copies: serverBook.available_copies || 1,
            statement_of_responsibility: serverBook.statement_of_responsibility || '',
            marc_record: serverBook.marc_record || '',
            created_at: serverBook.created_at || nowISO(),
            updated_at: serverBook.updated_at || nowISO(),
            sync_status: 'synced',
            sync_action: null
        });
    } else {
        // بررسی تعارض
        const localTime = new Date(localBook.updated_at || 0);
        const serverTime = new Date(serverBook.updated_at || 0);

        if (localBook.sync_status === 'pending') {
            // تعارض: هم محلی و هم سرور تغییر کرده
            if (serverTime.getTime() !== localTime.getTime()) {
                await db.conflicts.add({
                    model_name: 'book',
                    object_id: String(localBook.local_id),
                    local_data: localBook,
                    remote_data: serverBook,
                    local_updated_at: localBook.updated_at,
                    remote_updated_at: serverBook.updated_at,
                    resolution: 'pending',
                    created_at: nowISO()
                });
                await logSync('conflict', 'warning', `تعارض در: ${serverBook.title}`);
            }
        } else if (serverTime > localTime) {
            // سرور جدیدتر است
            await db.books.update(localBook.local_id, {
                ...serverBook,
                local_id: localBook.local_id,
                server_id: serverBook.id,
                sync_status: 'synced',
                sync_action: null
            });
        }
    }
}

async function mergeMember(serverMember) {
    const localMember = await db.members.where('server_id').equals(serverMember.id).first();

    if (!localMember) {
        await db.members.add({
            server_id: serverMember.id,
            first_name: serverMember.first_name || '',
            last_name: serverMember.last_name || '',
            full_name: `${serverMember.first_name || ''} ${serverMember.last_name || ''}`.trim(),
            national_id: serverMember.national_id || '',
            phone: serverMember.phone || '',
            address: serverMember.address || '',
            member_code: serverMember.member_code || '',
            join_date: serverMember.join_date || '',
            is_active: serverMember.is_active !== false,
            max_loans: serverMember.max_loans || 3,
            notes: serverMember.notes || '',
            created_at: serverMember.created_at || nowISO(),
            updated_at: serverMember.updated_at || nowISO(),
            sync_status: 'synced',
            sync_action: null
        });
    } else {
        const serverTime = new Date(serverMember.updated_at || 0);
        const localTime = new Date(localMember.updated_at || 0);

        if (localMember.sync_status !== 'pending' && serverTime > localTime) {
            await db.members.update(localMember.local_id, {
                ...serverMember,
                local_id: localMember.local_id,
                server_id: serverMember.id,
                full_name: `${serverMember.first_name || ''} ${serverMember.last_name || ''}`.trim(),
                sync_status: 'synced',
                sync_action: null
            });
        }
    }
}

async function mergeLoan(serverLoan) {
    const localLoan = await db.loans.where('server_id').equals(serverLoan.id).first();

    if (!localLoan) {
        // پیدا کردن book_id و member_id محلی
        const book = await db.books.where('server_id').equals(serverLoan.book).first();
        const member = await db.members.where('server_id').equals(serverLoan.member).first();

        if (book && member) {
            await db.loans.add({
                server_id: serverLoan.id,
                book_id: book.local_id,
                member_id: member.local_id,
                book_title: book.title,
                member_name: member.full_name,
                loan_date: serverLoan.loan_date || '',
                due_date: serverLoan.due_date || '',
                returned_date: serverLoan.returned_date || null,
                status: serverLoan.status || 'active',
                renewal_count: serverLoan.renewal_count || 0,
                notes: serverLoan.notes || '',
                created_at: serverLoan.created_at || nowISO(),
                updated_at: serverLoan.updated_at || nowISO(),
                sync_status: 'synced',
                sync_action: null
            });
        }
    } else {
        const serverTime = new Date(serverLoan.updated_at || 0);
        const localTime = new Date(localLoan.updated_at || 0);

        if (localLoan.sync_status !== 'pending' && serverTime > localTime) {
            await db.loans.update(localLoan.local_id, {
                ...serverLoan,
                local_id: localLoan.local_id,
                server_id: serverLoan.id,
                sync_status: 'synced',
                sync_action: null
            });
        }
    }
}

// ==================== Conflict Resolution ====================

export async function getConflicts() {
    return await db.conflicts.where('resolution').equals('pending').toArray();
}

export async function getConflictsCount() {
    return await db.conflicts.where('resolution').equals('pending').count();
}

export async function resolveConflict(conflict_id, resolution, customData = null) {
    const conflict = await db.conflicts.get(conflict_id);
    if (!conflict) return { success: false, error: 'تعارض یافت نشد' };

    let finalData;

    if (resolution === 'local') {
        finalData = conflict.local_data;
    } else if (resolution === 'remote') {
        finalData = conflict.remote_data;
    } else if (resolution === 'merged') {
        // ادغام: اولویت به داده‌های جدیدتر
        const localTime = new Date(conflict.local_updated_at || 0);
        const remoteTime = new Date(conflict.remote_updated_at || 0);

        if (localTime > remoteTime) {
            finalData = { ...conflict.remote_data, ...conflict.local_data };
        } else {
            finalData = { ...conflict.local_data, ...conflict.remote_data };
        }
    } else if (resolution === 'custom' && customData) {
        finalData = customData;
    } else {
        return { success: false, error: 'راه حل نامعتبر' };
    }

    // به‌روزرسانی داده اصلی
    if (conflict.model_name === 'book') {
        const book = await db.books.get(parseInt(conflict.object_id));
        if (book) {
            await db.books.update(book.local_id, {
                ...finalData,
                local_id: book.local_id,
                updated_at: nowISO(),
                sync_status: 'pending',
                sync_action: 'update'
            });

            // افزودن به صف
            await addToQueue('book', book.local_id, 'update', finalData);
        }
    }

    // علامت‌گذاری تعارض
    await db.conflicts.update(conflict_id, {
        resolution: resolution,
        resolved_data: finalData,
        resolved_at: nowISO()
    });

    await logSync('resolve_conflict', 'success', `تعارض حل شد: ${resolution}`);

    return { success: true };
}

export async function clearResolvedConflicts() {
    await db.conflicts.where('resolution').notEqual('pending').delete();
}

// ==================== Sync Log ====================

async function logSync(action, status, message) {
    await db.sync_log.add({
        action: action,
        status: status,
        message: message,
        created_at: nowISO()
    });
}

export async function getSyncLog(limit = 50) {
    return await db.sync_log.orderBy('created_at').reverse().limit(limit).toArray();
}

export async function clearSyncLog() {
    await db.sync_log.clear();
}

// ==================== Backup / Restore ====================

export async function exportBackup() {
    const deviceId = await getDeviceId();
    const deviceName = await getDeviceName();

    const data = {
        version: '1.0',
        exported_at: nowISO(),
        device_id: deviceId,
        device_name: deviceName,
        stats: {
            books: await db.books.count(),
            members: await db.members.count(),
            loans: await db.loans.count(),
        },
        books: await db.books.toArray(),
        members: await db.members.toArray(),
        loans: await db.loans.toArray(),
        conflicts: await db.conflicts.toArray(),
    };

    return JSON.stringify(data, null, 2);
}

export async function exportBackupAsFile() {
    const json = await exportBackup();
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `library_local_backup_${new Date().toISOString().slice(0,10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    return true;
}

export async function importBackup(jsonData, mode = 'merge') {
    let data;

    if (typeof jsonData === 'string') {
        data = JSON.parse(jsonData);
    } else {
        data = jsonData;
    }

    if (!data.books && !data.members) {
        return { success: false, error: 'فایل بکاپ نامعتبر است' };
    }

    const stats = {
        books_created: 0,
        books_updated: 0,
        books_skipped: 0,
        members_created: 0,
        members_updated: 0,
        members_skipped: 0,
        loans_created: 0,
        errors: []
    };

    if (mode === 'replace') {
        await db.books.clear();
        await db.members.clear();
        await db.loans.clear();
    }

    // کتاب‌ها
    for (const book of (data.books || [])) {
        try {
            const existingByISBN = book.isbn ? await db.books.where('isbn').equals(book.isbn).first() : null;
            const existingByServerId = book.server_id ? await db.books.where('server_id').equals(book.server_id).first() : null;
            const existing = existingByISBN || existingByServerId;

            if (existing && mode === 'merge') {
                // ادغام: فقط اگر داده جدیدتر باشد
                const existingTime = new Date(existing.updated_at || 0);
                const newTime = new Date(book.updated_at || 0);

                if (newTime > existingTime) {
                    await db.books.update(existing.local_id, {
                        ...book,
                        local_id: existing.local_id,
                        updated_at: nowISO(),
                        sync_status: 'pending',
                        sync_action: 'update'
                    });
                    await addToQueue('book', existing.local_id, 'update', book);
                    stats.books_updated++;
                } else {
                    stats.books_skipped++;
                }
            } else {
                const newBook = { ...book };
                delete newBook.local_id;
                const localId = await db.books.add({
                    ...newBook,
                    created_at: newBook.created_at || nowISO(),
                    updated_at: nowISO(),
                    sync_status: 'pending',
                    sync_action: 'create'
                });
                await addToQueue('book', localId, 'create', newBook);
                stats.books_created++;
            }
        } catch (e) {
            stats.errors.push(`کتاب: ${e.message}`);
        }
    }

    // اعضا
    for (const member of (data.members || [])) {
        try {
            const existingByNID = member.national_id ? await db.members.where('national_id').equals(member.national_id).first() : null;
            const existingByServerId = member.server_id ? await db.members.where('server_id').equals(member.server_id).first() : null;
            const existing = existingByNID || existingByServerId;

            if (existing && mode === 'merge') {
                const existingTime = new Date(existing.updated_at || 0);
                const newTime = new Date(member.updated_at || 0);

                if (newTime > existingTime) {
                    await db.members.update(existing.local_id, {
                        ...member,
                        local_id: existing.local_id,
                        updated_at: nowISO(),
                        sync_status: 'pending',
                        sync_action: 'update'
                    });
                    await addToQueue('member', existing.local_id, 'update', member);
                    stats.members_updated++;
                } else {
                    stats.members_skipped++;
                }
            } else {
                const newMember = { ...member };
                delete newMember.local_id;
                const localId = await db.members.add({
                    ...newMember,
                    full_name: `${newMember.first_name || ''} ${newMember.last_name || ''}`.trim(),
                    created_at: newMember.created_at || nowISO(),
                    updated_at: nowISO(),
                    sync_status: 'pending',
                    sync_action: 'create'
                });
                await addToQueue('member', localId, 'create', newMember);
                stats.members_created++;
            }
        } catch (e) {
            stats.errors.push(`عضو: ${e.message}`);
        }
    }

    await logSync('import_backup', 'success',
        `کتاب: ${stats.books_created} جدید، ${stats.books_updated} ویرایش | اعضا: ${stats.members_created} جدید، ${stats.members_updated} ویرایش`);

    return {
        success: true,
        stats: stats,
        message: `کتاب: ${stats.books_created} جدید، ${stats.books_updated} ویرایش | اعضا: ${stats.members_created} جدید، ${stats.members_updated} ویرایش`
    };
}

export async function importBackupFromFile(file, mode = 'merge') {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();

        reader.onload = async (e) => {
            try {
                const result = await importBackup(e.target.result, mode);
                resolve(result);
            } catch (error) {
                reject(error);
            }
        };

        reader.onerror = () => reject(new Error('خطا در خواندن فایل'));
        reader.readAsText(file);
    });
}

// ==================== Statistics ====================

export async function getStats() {
    return {
        books: await db.books.count(),
        members: await db.members.count(),
        loans: await db.loans.count(),
        pending: await getPendingCount(),
        conflicts: await getConflictsCount(),
        last_sync: (await db.metadata.get('last_sync'))?.value || null,
    };
}

// ==================== Clear All ====================

export async function clearAll() {
    await db.books.clear();
    await db.members.clear();
    await db.loans.clear();
    await db.sync_queue.clear();
    await db.conflicts.clear();
    await db.sync_log.clear();
    // metadata را نگه می‌داریم (device_id)
}

// ==================== Initialize ====================

export async function initializeDB() {
    const deviceId = await getDeviceId();
    const deviceName = await getDeviceName();

    console.log('✅ LibraryLocalDB initialized');
    console.log(`   Device ID: ${deviceId}`);
    console.log(`   Device Name: ${deviceName}`);

    return { deviceId, deviceName };
}

// ==================== Export ====================

export default db;

// همه توابع را در window قرار می‌دهیم برای دسترسی آسان
if (typeof window !== 'undefined') {
    window.LibraryDB = {
        // Book
        saveBook, getBooks, getBook, getBookByServerId, getBookByISBN,
        searchBooks, deleteBook, clearBooks,

        // Member
        saveMember, getMembers, getMember, getMemberByNationalId,
        deleteMember, clearMembers,

        // Loan
        saveLoan, getLoans, getLoan, getLoansByBook, getLoansByMember,
        deleteLoan, clearLoans,

        // Sync
        pushChanges, pullChanges,
        getPendingChanges, getPendingCount, getAllQueueItems,
        clearSyncedQueue, clearAllQueue,

        // Conflicts
        getConflicts, getConflictsCount, resolveConflict, clearResolvedConflicts,

        // Log
        getSyncLog, clearSyncLog,

        // Backup
        exportBackup, exportBackupAsFile,
        importBackup, importBackupFromFile,

        // Stats
        getStats,

        // Device
        getDeviceId, getDeviceName, setDeviceName,

        // Clear
        clearAll,

        // Init
        initializeDB,

        // DB instance
        db: db
    };
}