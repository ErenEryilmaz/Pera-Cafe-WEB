// ── Ses sistemi state ────────────────────────────────────────
let srId         = 0;
let recognition  = null;
let currentAudio = null;
let voiceEnabled = false;
window.isPeraSpeaking = false;

// Kullanıcı konuşurken kısa duraklamalarda kesilmesin: ses geldikçe sıfırlanan
// bir sayaç tutarız. SILENCE_MS kadar (2 sn) yeni ses gelmezse cümle bitti sayılır.
let silenceTimer = null;
const SILENCE_MS = 2000;   // ← bekleme süresi (ms). 2 sn sessizlik = konuşma bitti

// ── Pill UI ──────────────────────────────────────────────────
function getPillText(mode) {
    // pillListen fonksiyon — kullanıcı adıyla kişiselleştirilmiş
    const listenText = typeof t.pillListen === 'function' ? t.pillListen(userName) : t.pillListen;
    return {
        listen:   listenText,
        process:  t.pillProcess,
        speaking: t.pillSpeak,
        off:      t.pillOff,
    }[mode] || listenText;
}

function setPill(mode) {
    voiceMode = mode;
    document.getElementById('pill-text').textContent = getPillText(mode);
    document.getElementById('pill-dot').className    = 'voice-pill-dot ' + mode;
    const wave = document.getElementById('pill-wave');
    wave.className = 'voice-wave ' + (['listen','speaking'].includes(mode) ? 'active' : 'idle');
    updatePillText();
}

function updatePillText() {
    const pillTextEl = document.getElementById('pill-text');
    if (pillTextEl) pillTextEl.textContent = getPillText(voiceMode);

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
    clearTimeout(silenceTimer);
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
    sr.continuous     = true;    // kısa duraklamada kesme — sürekli dinle
    sr.interimResults = true;    // ara sonuçlarla sessizliği anında takip et
    recognition = sr;

    // 2 sn boyunca yeni ses gelmezse cümle tamamlandı say ve gönder.
    const finalize = (text) => {
        if (myId !== srId) return;
        clearTimeout(silenceTimer);
        const tx = (text || '').trim();
        if (tx.length <= 1) return;   // anlamlı bir şey yok → dinlemeye devam
        srId++;                       // bu örneği geçersiz kıl (onend/onresult yok sayılır)
        killSR();
        playBeep();
        sendMessage(tx);              // sendMessage işi bitince dinlemeyi sürdürür
    };

    sr.onresult = (e) => {
        if (myId !== srId) return;
        // Oturumdaki tüm parçaları (kesinleşmiş + ara) birleştir
        let txt = '';
        for (let i = 0; i < e.results.length; i++) txt += e.results[i][0].transcript;
        setPill('listen');
        // Her ses parçasında 2 sn sayacı baştan başlar
        clearTimeout(silenceTimer);
        silenceTimer = setTimeout(() => finalize(txt), SILENCE_MS);
    };

    sr.onerror = (e) => {
        if (myId !== srId) return;
        clearTimeout(silenceTimer);
        if (e.error === 'not-allowed') {
            voiceEnabled = false; setPill('off'); updatePillText(); return;
        }
        if (e.error === 'aborted') return;
        setTimeout(() => { if (voiceEnabled && myId === srId) startSR(); }, 400);
    };

    sr.onend = () => {
        if (myId !== srId) return;
        clearTimeout(silenceTimer);
        setTimeout(() => { if (voiceEnabled && myId === srId) startSR(); }, 150);
    };

    try { sr.start(); } catch(e) {
        setTimeout(() => { if (voiceEnabled) startSR(); }, 500);
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
    voiceEnabled = true;
    setPill('listen');
    updatePillText();
    startSR();
}

function stopVoiceSystem() {
    voiceEnabled = false;
    srId++;
    killSR();
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    window.isPeraSpeaking = false;
    setPill('off');
    updatePillText();
}

function toggleVoiceSystem() { voiceEnabled ? stopVoiceSystem() : startVoiceSystem(); }

// ── Lip-sync: gerçek ses genliği analizi ─────────────────────
let lipCtx = null, lipAnalyser = null, lipData = null;

function setupLipSync(audio) {
    try {
        if (!lipCtx) {
            lipCtx = new (window.AudioContext || window.webkitAudioContext)();
            lipAnalyser = lipCtx.createAnalyser();
            lipAnalyser.fftSize = 256;
            lipAnalyser.smoothingTimeConstant = 0.5;
            lipData = new Uint8Array(lipAnalyser.frequencyBinCount);
            lipAnalyser.connect(lipCtx.destination);
        }
        if (lipCtx.state === 'suspended') lipCtx.resume();
        // Her Audio elementi yalnız bir kez source olabilir
        const src = lipCtx.createMediaElementSource(audio);
        src.connect(lipAnalyser);
        return true;
    } catch(e) {
        console.warn('Lip-sync analyser kurulamadı, sinüs moduna düşülüyor:', e);
        return false;
    }
}

// Animasyon döngüsü her frame bunu çağırır: 0..1 arası anlık ses seviyesi.
// Analyser yoksa null döner (çağıran sinüs fallback kullanır).
window.getPeraAudioLevel = function() {
    if (!lipAnalyser || !window.isPeraSpeaking) return null;
    // Zaman alanında RMS: dalga formunun gerçek anlık genliği
    lipAnalyser.getByteTimeDomainData(lipData);
    let sum = 0;
    for (let i = 0; i < lipData.length; i++) {
        const d = (lipData[i] - 128) / 128;
        sum += d * d;
    }
    const rms = Math.sqrt(sum / lipData.length);
    // 0.02 altı = sessizlik (gürültü tabanı); konuşma tipik 0.05-0.3 RMS
    return Math.min(1, Math.max(0, (rms - 0.02) * 4));
};

// ── Ses çalma ────────────────────────────────────────────────
function playAudioAndResume(b64) {
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    const audio = new Audio('data:audio/mp3;base64,' + b64);
    currentAudio = audio;
    setupLipSync(audio);

    // Ses GERÇEKTEN duyulmaya başlayınca kasları oynat
    audio.onplaying = () => {
        window.isPeraSpeaking = true;
        setPill('speaking');
    };
    // Bitince / hata / pause: kaslar 0'a dönsün
    const stopSpeaking = () => {
        window.isPeraSpeaking = false;
        if (currentAudio === audio) {
            currentAudio = null;
            resumeListening(400);
        }
    };
    audio.onended = audio.onerror = stopSpeaking;
    audio.onpause = () => {
        // pause() çağrısı 'ended' ateşlemez — ağız açık kalmasın
        if (!audio.ended) window.isPeraSpeaking = false;
    };
    audio.play().catch(() => {
        window.isPeraSpeaking = false;
        resumeListening(400);
    });
}

function resumeListening(delay) {
    if (!voiceEnabled) return;
    setTimeout(() => {
        if (!voiceEnabled) return;
        setPill('listen');
        startSR();
    }, delay);
}
