// ── State ─────────────────────────────────────────────────────
const userName = localStorage.getItem('userName') || '';
if (!userName) { window.location.href = 'perakafe_login.html'; }

let currentLang  = localStorage.getItem('peraLang') || 'tr';
let t            = UI[currentLang] || UI.tr;
let chatMessages = [];
let voiceMode    = 'off';

// ── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const initials = userName.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
    document.getElementById('av-circle').textContent   = initials || '?';
    document.getElementById('topbar-name').textContent = userName;

    applyTheme(localStorage.getItem('peraTheme') || 'light');
    applyLang();

    fetchMenu();
    fetchCampaigns();
    initRecognition();

    // Giriş cümlesini sesli söyle, bitince dinlemeye başla
    speakGreeting();
});

// ── Giriş karşılaması ─────────────────────────────────────────
async function speakGreeting() {
    const greeting = t.greeting(userName);

    // Ekrana yaz
    chatMessages = [{ role: 'assistant', content: greeting }];
    document.getElementById('chat-history').innerHTML = '';
    appendMessage('assistant', greeting);

    // Backend'den TTS al
    try {
        const res = await fetch(window.location.origin + '/chat', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({
                messages:  [{ role: 'user', content: '__greeting__' }],
                user_name: userName,
                lang:      currentLang,
            }),
        });
        const data = await res.json();

        if (data.audio_base64) {
            setPill('speaking');
            voiceEnabled = true;            // ses bitince dinlemeye geçebilsin
            playAudioAndResume(data.audio_base64);
        } else {
            startVoiceSystem();             // ses yoksa direkt dinlemeye başla
        }
    } catch(e) {
        startVoiceSystem();
    }
}


function applyLang() {
    t = UI[currentLang] || UI.tr;
    document.documentElement.lang = t.htmlLang;
    document.documentElement.dir  = t.dir;

    setText('txt-logout',        t.logout);
    setText('txt-menu-title',    t.menuTitle);
    setText('txt-loading-menu',  t.menuLoading);
    setText('txt-chat-title',    t.chatTitle);
    setText('txt-receipt-title', t.receiptTitle);
    setText('btn-pay',           t.btnPay);
    setText('txt-send',          t.btnSend);
    setText('loading',           t.loading + ' ');
    setAttr('user-input', 'placeholder', t.inputPlaceholder);

    updatePillText();
    renderCart();
    fetchMenu();

    if (voiceEnabled) {
        stopVoiceSystem();
        setTimeout(startVoiceSystem, 400);
    }
}

function checkLangChange() {
    const stored = localStorage.getItem('peraLang') || 'tr';
    if (stored !== currentLang) {
        currentLang = stored;
        chatMessages = [];
        document.getElementById('chat-history').innerHTML = '';
        applyLang();
    }
}
window.addEventListener('focus', checkLangChange);

// ── Tema ──────────────────────────────────────────────────────
function setTheme(th) { localStorage.setItem('peraTheme', th); applyTheme(th); }
function applyTheme(th) {
    document.documentElement.setAttribute('data-theme', th);
    document.querySelectorAll('.swatch').forEach(s => s.classList.toggle('active', s.dataset.theme === th));
}

// ── Sohbet ────────────────────────────────────────────────────
async function sendMessage(textOverride = null) {
    const field = document.getElementById('user-input');
    const msg   = textOverride || field.value.trim();
    if (!msg) return;

    field.value = '';
    appendMessage('user', msg);
    chatMessages.push({ role: 'user', content: msg });
    document.getElementById('loading').style.display = 'block';

    commandPending = false;
    srId++;
    killSR();
    setPill('process');

    try {
        const res = await fetch(window.location.origin + '/chat', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ messages: chatMessages, user_name: userName, lang: currentLang }),
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();

        if (data.reply) {
            appendMessage('assistant', data.reply);
            chatMessages.push({ role: 'assistant', content: data.reply });
        }
        if (data.cart != null) mergeCart(data.cart);

        if (data.audio_base64) {
            setPill('speaking');
            playAudioAndResume(data.audio_base64);
        } else {
            resumeWakeWord(500);
        }
    } catch(err) {
        console.error(err);
        appendMessage('assistant', t.errServer);
        chatMessages.pop();
        resumeWakeWord(1000);
    } finally {
        document.getElementById('loading').style.display = 'none';
    }
}

// ── Yardımcılar ───────────────────────────────────────────────
function appendMessage(role, text) {
    const box = document.getElementById('chat-history');
    const el  = document.createElement('div');
    el.className   = 'message ' + (role === 'user' ? 'user-msg' : 'bot-msg');
    el.textContent = text;
    box.appendChild(el);
    box.scrollTop = box.scrollHeight;
    while (box.children.length > 20) box.removeChild(box.firstChild);
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function setAttr(id, attr, val) {
    const el = document.getElementById(id);
    if (el) el.setAttribute(attr, val);
}

function handleKeyPress(e) { if (e.key === 'Enter') sendMessage(); }

function logout() {
    localStorage.removeItem('userName');
    window.location.href = 'perakafe_login.html';
}

// ── Mobil sidebar ─────────────────────────────────────────────
function toggleSidebar() {
    document.querySelector('.sidebar').classList.toggle('open');
}

document.addEventListener('click', e => {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;
    if (sidebar.classList.contains('open') &&
        !sidebar.contains(e.target) &&
        !e.target.closest('.menu-toggle')) {
        sidebar.classList.remove('open');
    }
});
