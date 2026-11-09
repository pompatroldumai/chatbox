
 // ==========================================
 // 1. INITIALIZATION & AUDIO HANDLER
 // ==========================================
var chatBody = document.getElementById('chatBody');
let currentActions = null;
let audioUnlocked = false;

// Deklarasi Elemen Audio dari DOM
const audioRefresh = document.getElementById('audioRefresh');
const audioPopup = document.getElementById('audioPopup');
const audioSuccess = document.getElementById('audioSuccess');
const audioWarning = document.getElementById('audioWarning');

// Fungsi tunggal untuk membongkar proteksi Autoplay browser
function unlockAudioEngine() {
    if (audioUnlocked) return;

    const audioList = [audioRefresh, audioPopup, audioSuccess, audioWarning];

    audioList.forEach(audio => {
        if (audio) {
            audio.play().then(() => {
                audio.pause();
                audio.currentTime = 0;
            }).catch(err => {
                console.warn("Autoplay unlocking pending user interaction:", err);
            });
        }
    });

    audioUnlocked = true;
}

// Tangkap interaksi pertama pengguna untuk mengaktifkan audio
document.addEventListener('click', unlockAudioEngine, { once: true });
document.addEventListener('touchstart', unlockAudioEngine);

// Putar suara refresh
function playRefreshSound() {
    if (audioRefresh) {
        audioRefresh.currentTime = 0;
        audioRefresh.play().catch(err => {
            console.info("Autoplay refresh diblokir browser.");
        });
    }
}

// Putar suara popup
function playPopupSound() {
    if (audioPopup) {
        audioPopup.currentTime = 0;
        audioPopup.play().catch(err => {
            console.warn("Gagal memutar audio popup:", err);
        });
    }
}

// Putar suara hasil
function playResultSound(status) {
    if (status === 'success' && audioSuccess) {
        audioSuccess.currentTime = 0;
        audioSuccess.play().catch(err => console.warn("Gagal memutar audio success:", err));
    } else if ((status === 'warning' || status === 'danger') && audioWarning) {
        audioWarning.currentTime = 0;
        audioWarning.play().catch(err => console.warn("Gagal memutar audio warning/danger:", err));
    }
}

// Putar suara pembuka saat dokumen dimuat
document.addEventListener('DOMContentLoaded', () => {
    playRefreshSound();
});

// ==========================================
// 2. PARSER MARKDOWN & HELPER FUNCTIONS
// ==========================================
function parseMarkdown(text) {
    if (!text) return '';

    let formatted = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    const lines = formatted.split('\n');
    let inList = false;
    let result = '';

    lines.forEach(line => {
        let trimmed = line.trim();

        if (trimmed.startsWith('•') || trimmed.startsWith('-')) {
            if (!inList) {
                result += '<ul class="chat-list">';
                inList = true;
            }

            result += `<li>${trimmed.replace(/^[•-]\s*/, '')}</li>`;
        } else {
            if (inList) {
                result += '</ul>';
                inList = false;
            }

            if (trimmed !== '') {
                result += line + '<br>';
            }
        }
    });

    if (inList) result += '</ul>';

    return result;
}

// ==========================================
// 3. CHAT DISPLAY & MESSAGE BUILDERS
// ==========================================
function appendUserMessage(text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message user-message';
    msgDiv.innerHTML = `<div class="message-content">${text}</div>`;

    chatBody.appendChild(msgDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

function appendBotMessage(text, options = null, inputKey = null) {
    playPopupSound();

    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot-message';

    let formattedText = parseMarkdown(text);
    let htmlContent = `<div class="message-content">${formattedText}</div>`;

    if (options && options.length > 0) {
        htmlContent += `<div class="options-group">`;

        options.forEach(opt => {
            if (inputKey === 'psikotropika_check') {
                htmlContent += `<button onclick="sendPsikoAnswer(${opt.id === 'psiko_ya'})">${opt.text}</button>`;
            } else if (inputKey === 'pkmk') {
                htmlContent += `<button onclick="sendPkmkAnswer(${opt.id === 'pkmk_ya'})">${opt.text}</button>`;
            } else {
                htmlContent += `<button onclick="sendDrugType('${opt.id}', '${opt.text}')">${opt.text}</button>`;
            }
        });

        htmlContent += `</div>`;
    }

    if (inputKey && !options) {
        htmlContent += `
            <div class="input-group-chat">
                <input type="number" id="inputQty_${inputKey}" placeholder="Masukkan Angka" min="1" step="any">
                <button onclick="submitQuantity('${inputKey}')">Kirim</button>
            </div>
        `;
    }

    msgDiv.innerHTML = htmlContent;
    chatBody.appendChild(msgDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

function appendMainMenu(message, options) {
    playPopupSound();

    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot-message';

    let htmlContent = `<div class="message-content"><strong>${message}</strong></div>`;
    htmlContent += `<div class="options-group">`;

    options.forEach(opt => {
        const icon = opt.icon ? `<span class="option-icon">${opt.icon}</span>` : '';
        const note = opt.note ? `<small class="note-text">${opt.note}</small>` : '';

        htmlContent += `
            <button onclick="sendCategory('${opt.id}')">
                ${icon}
                <span class="option-text">${opt.text} ${note}</span>
            </button>
        `;
    });

    htmlContent += `</div>`;
    msgDiv.innerHTML = htmlContent;

    chatBody.appendChild(msgDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

function appendAfterActionOptions(actions) {
    playPopupSound();

    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot-message';

    let htmlContent = `<div class="message-content">Apakah Anda ingin mengecek barang lainnya?</div>`;
    htmlContent += `<div class="options-group">`;

    actions.forEach(opt => {
        htmlContent += `<button onclick="handleAfterAction('${opt.id}', '${opt.text}')">${opt.text}</button>`;
    });

    htmlContent += `</div>`;
    msgDiv.innerHTML = htmlContent;

    chatBody.appendChild(msgDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

// ==========================================
// 4. FLOW & API LOGIC
// ==========================================

// >>> BAGIAN INI SUDAH DIUBAH <<<
// Klik TIDAK sekarang membuka popup feedback
function handleConsultation(isYes) {
    const optionsGroup = document.getElementById('consultationOptions');

    if (optionsGroup) {
        optionsGroup.remove();
    }

    if (isYes) {
        appendUserMessage("Ya");

        appendBotMessage(
            "Selamat datang di layanan pengecekan Batasan Jumlah Barang Bawaan Anda."
        );

        fetch('/api/main_menu')
            .then(res => res.json())
            .then(data => {
                appendMainMenu(data.message, data.options);
            })
            .catch(() => {
                showDefaultMainMenu();
            });

    } else {
        appendUserMessage("Tidak");

        appendBotMessage("Semoga perjalanan Anda menyenangkan! 👋");

        // POPUP FEEDBACK MUNCUL SETELAH KLIK TIDAK
        setTimeout(() => {
            if (typeof openFeedbackModal === 'function') {
                openFeedbackModal();
            } else {
                console.error("Fungsi openFeedbackModal() belum tersedia.");
            }
        }, 500);
    }
}

function showDefaultMainMenu() {
    const defaultOptions = [
        { id: 'obat', text: 'Obat', icon: '💊' },
        { id: 'obat_tradisional', text: 'Obat Tradisional', icon: '🌿' },
        { id: 'suplemen', text: 'Suplemen Kesehatan', icon: '🧪' },
        { id: 'kosmetik', text: 'Kosmetika', icon: '💄' },
        { id: 'pkmk', text: 'Pangan Olahan Medis Khusus (PKMK)', icon: '🏥' },
        { id: 'makanan', text: 'Pangan Olahan Lain (Makanan)', icon: '🍱', note: 'kecuali minuman beralkohol' }
    ];

    appendMainMenu("Kamu membawa apa?", defaultOptions);
}

function sendCategory(categoryKey) {
    const categoryNames = {
        'obat': '💊 Obat',
        'obat_tradisional': '🌿 Obat Bahan Alam / Obat Kuasi / Tradisional',
        'suplemen': '🧪 Suplemen Kesehatan',
        'kosmetik': '💄 Kosmetik',
        'pkmk': '🏥 Pangan Olahan Medis Khusus (PKMK)',
        'makanan': '🍱 Pangan Olahan Lain (Makanan)'
    };

    appendUserMessage(categoryNames[categoryKey] || categoryKey);

    fetch('/api/select_category', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: categoryKey })
    })
    .then(res => res.json())
    .then(data => {
        if (data.type === 'question') {
            appendBotMessage(data.message, data.options);
        } else if (data.type === 'input_quantity') {
            appendBotMessage(data.message, null, data.item_key);
        } else if (data.type === 'question_bool') {
            appendBotMessage(data.message, data.options, data.item_key);
        }
    });
}

function sendDrugType(drugTypeId, drugText) {
    appendUserMessage(drugText);

    fetch('/api/select_drug_type', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ drug_type: drugTypeId })
    })
    .then(res => res.json())
    .then(data => {
        if (data.type === 'result_popup') {
            showModal(data.status, data.title, data.message, data.actions);
        } else if (data.type === 'question_psikotropika') {
            appendBotMessage(data.message, data.options, 'psikotropika_check');
        } else if (data.type === 'input_quantity') {
            appendBotMessage(data.message, null, data.item_key);
        }
    });
}

function submitQuantity(itemKey) {
    const inputElem = document.getElementById(`inputQty_${itemKey}`);
    const qty = inputElem.value;

    if (!qty || qty <= 0) {
        alert("Silakan masukkan jumlah angka yang valid.");
        return;
    }

    appendUserMessage(`Jumlah yang dibawa: ${qty}`);
    inputElem.disabled = true;

    fetch('/api/validate_input', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_key: itemKey, quantity: qty })
    })
    .then(res => res.json())
    .then(data => {
        if (data.type === 'result_popup') {
            showModal(data.status, data.title, data.message, data.actions);
        }
    });
}

function sendPsikoAnswer(isValid) {
    appendUserMessage(
        isValid
            ? "Ya, WNA/Wisatawan Asing & Membawa Resep Dokter"
            : "Tidak Memenuhi Syarat"
    );

    fetch('/api/validate_input', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            item_key: 'psikotropika_check',
            is_valid: isValid
        })
    })
    .then(res => res.json())
    .then(data => {
        showModal(data.status, data.title, data.message, data.actions);
    });
}

function sendPkmkAnswer(hasPrescription) {
    appendUserMessage(
        hasPrescription
            ? "Ya, membawa resep dokter"
            : "Tidak membawa resep dokter"
    );

    fetch('/api/validate_input', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            item_key: 'pkmk',
            has_prescription: hasPrescription
        })
    })
    .then(res => res.json())
    .then(data => {
        showModal(data.status, data.title, data.message, data.actions);
    });
}

function handleAfterAction(actionId, text) {
    appendUserMessage(text);

    if (actionId === 'check_another') {
        fetch('/api/main_menu')
            .then(res => res.json())
            .then(data => {
                appendMainMenu(data.message, data.options);
            })
            .catch(() => {
                showDefaultMainMenu();
            });

    } else if (actionId === 'finish') {
        appendBotMessage(
            "Terima kasih telah menggunakan layanan pengecekan batasan barang bawaan. Semoga perjalanan Anda menyenangkan! 👋"
        );
    }
}

// ==========================================
// 5. MODALS & UTILITY FUNCTIONS
// ==========================================
function showModal(status, title, message, actions = null) {
    const modalIcon = document.getElementById('modalIcon');
    const modalBtn = document.getElementById('modalBtn');

    currentActions = actions;

    document.getElementById('modalTitle').innerText = title;
    document.getElementById('modalMessage').innerHTML = parseMarkdown(message);

    modalIcon.className = `modal-icon ${status}`;
    modalBtn.className = `btn-${status}`;

    if (status === 'success') {
        modalIcon.innerHTML = `<i class="fa-solid fa-circle-check"></i>`;
    } else if (status === 'warning') {
        modalIcon.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i>`;
    } else {
        modalIcon.innerHTML = `<i class="fa-solid fa-circle-xmark"></i>`;
    }

    playResultSound(status);

    document.getElementById('modalPopup').style.display = 'flex';
}

function closeModal() {
    document.getElementById('modalPopup').style.display = 'none';

    if (currentActions && currentActions.length > 0) {
        appendAfterActionOptions(currentActions);
        currentActions = null;
    }
}

function openFaqModal() {
    const faqModal = document.getElementById('faqModal');

    if (faqModal) {
        faqModal.style.display = 'flex';
    }
}

function closeFaqModal() {
    const faqModal = document.getElementById('faqModal');

    if (faqModal) {
        faqModal.style.display = 'none';
    }
}

function resetChat() {
    window.location.reload();
}


// ==========================================
// STATISTIK PENGECEKAN 6 KATEGORI BARANG
// ==========================================

async function loadCategoryStats() {

    try {

        const response = await fetch('/api/category_stats');

        if (!response.ok) {
            throw new Error('Gagal mengambil statistik kategori');
        }

        const data = await response.json();

        const categories = [
            'obat',
            'obat_tradisional',
            'suplemen',
            'kosmetik',
            'pkmk',
            'makanan'
        ];

        categories.forEach(category => {

            const element = document.getElementById(
                'count-' + category
            );

            if (element) {

                element.textContent = (
                    data[category] || 0
                ).toLocaleString('id-ID');

            }

        });

    } catch (error) {

        console.error(
            'Gagal memperbarui statistik kategori:',
            error
        );

    }

}


// Ambil statistik saat halaman pertama kali dibuka
document.addEventListener('DOMContentLoaded', function() {

    loadCategoryStats();

});


// Perbarui statistik setiap 3 detik
setInterval(function() {

    loadCategoryStats();

}, 3000);
