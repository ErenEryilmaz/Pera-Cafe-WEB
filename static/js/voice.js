// ── Ses sistemi state ────────────────────────────────────────
let srId           = 0;
let commandPending = false;
let recognition    = null;
let currentAudio   = null;
let voiceEnabled   = false;
window.isPeraSpeaking = false;

// ── Pill UI ──────────────────────────────────────────────────
function setPill(mode) {
    voiceMode = mode;
    const textMap = {
        wake:     t.pillWake,
        listen:   t.pillListen,
        process:  t.pillProcess,
        speaking: t.pillSpeak,
        off:      t.pillOff,
    };
    document.getElementById('pill-text').textContent  = textMap[mode] || t.pillWake;
    document.getElementById('pill-dot').className     = 'voice-pill-dot ' + mode;
    const wave = document.getElementById('pill-wave');
    wave.className = 'voice-wave ' + (['listen','speaking'].includes(mode) ? 'active' : 'idle');
    updatePillText();
}

function updatePillText() {
    const pillTextEl = document.getElementById('pill-text');
    const map = { wake:t.pillWake, listen:t.pillListen, process:t.pillProcess, speaking:t.pillSpeak, off:t.pillOff };
    if (pillTextEl) pillTextEl.textContent = map[voiceMode] || t.pillWake;

    const pillBtn = document.getElementById('pill-btn');
    if (pillBtn) {
        pillBtn.textContent = voiceEnabled ? t.pillStop : t.pillStart;
        voiceEnabled ? pillBtn.classList.add('stop') : pillBtn.classList.remove('stop');
    }
}

// ── Beep ─────────────────────────────────────────────────────
function playBeep() {
    try {
        const ctx  = new (window.AudioContext || window.webkitAudioContext)();
        const osc  = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        osc.frequency.value = 880; osc.type = 'sine';
        gain.gain.setValueAtTime(0.25, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.22);
        osc.start(); osc.stop(ctx.currentTime + 0.22);
    } catch(e) {}
}

// ── Speech Recognition ───────────────────────────────────────
function killSR() {
    if (!recognition) return;
    const old = recognition;
    recognition  = null;
    old.onresult = null;
    old.onerror  = null;
    old.onend    = null;
    try { old.abort(); } catch(e) {}
}

function startSR() {
    if (!voiceEnabled) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setPill('off'); return; }

    killSR();
    const myId = ++srId;
    const sr   = new SR();
    sr.lang           = t.speechLang;
    sr.continuous     = false;
    sr.interimResults = false;
    recognition = sr;

    sr.onresult = (e) => {
        if (myId !== srId) return;
        srId++;
        const tx = e.results[0][0].transcript.toLowerCase().trim();
        handleTranscript(tx);
    };

    sr.onerror = (e) => {
        if (myId !== srId) return;
        if (e.error === 'not-allowed') {
            voiceEnabled = false; setPill('off'); updatePillText(); return;
        }
        if (e.error === 'aborted') return;
        setTimeout(() => { if (voiceEnabled && myId === srId) startSR(); }, 400);
    };

    sr.onend = () => {
        if (myId !== srId) return;
        setTimeout(() => { if (voiceEnabled && myId === srId) startSR(); }, 150);
    };

    try { sr.start(); } catch(e) {
        setTimeout(() => { if (voiceEnabled) startSR(); }, 500);
    }
}

function handleTranscript(tx) {
    if (commandPending) {
        commandPending = false;
        if (tx.length > 1) {
            sendMessage(tx);
        } else {
            setPill('wake');
            setTimeout(() => { if (voiceEnabled) startSR(); }, 300);
        }
    } else {
        if (t.wakeWords.some(w => tx.includes(w))) {
            playBeep();
            commandPending = true;
            setPill('listen');
            setTimeout(() => { if (voiceEnabled) startSR(); }, 500);
        } else {
            setTimeout(() => { if (voiceEnabled) startSR(); }, 100);
        }
    }
}

// ── Sistem başlat / durdur ───────────────────────────────────
function initRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setPill('off'); updatePillText(); }
}

function startVoiceSystem() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setPill('off'); updatePillText(); return; }
    voiceEnabled   = true;
    commandPending = false;
    setPill('wake');
    updatePillText();
    startSR();
}

function stopVoiceSystem() {
    voiceEnabled   = false;
    commandPending = false;
    srId++;
    killSR();
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    setPill('off');
    updatePillText();
}

function toggleVoiceSystem() { voiceEnabled ? stopVoiceSystem() : startVoiceSystem(); }

// ── Ses çalma ─────────────────────────────────────────────────
function playAudioAndResume(b64) {
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    currentAudio = new Audio('data:audio/mp3;base64,' + b64);

    currentAudio.onplay = () => { window.isPeraSpeaking = true; };
    currentAudio.onended = currentAudio.onerror = () => {
        window.isPeraSpeaking = false;
        currentAudio = null;
        resumeWakeWord(400);
    };
    currentAudio.play().catch(() => {
        window.isPeraSpeaking = false;
        resumeWakeWord(400);
    });
}

function resumeWakeWord(delay) {
    if (!voiceEnabled) return;
    setTimeout(() => {
        if (!voiceEnabled) return;
        commandPending = false;
        setPill('wake');
        startSR();
    }, delay);
}
