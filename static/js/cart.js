// ── Sepet state ───────────────────────────────────────────────
let cart = [];
let trackingInterval = null;

// ── Sepet güncelleme ─────────────────────────────────────────
function mergeCart(aiCart) {
    // AI bazen qty alanı gönderiyor, bazen aynı ürünü tekrarlıyor
    // Her iki formatı da destekle; fiyat 0 veya eksik olan öğeleri at
    const grouped = {};
    aiCart.forEach(item => {
        const key = item.ad;
        if (!item.ad) return;
        const fiyat = parseFloat(item.fiyat) || 0;

        // Eğer AI qty gönderdiyse onu kullan, yoksa tekrar sayım yöntemi
        if (item.qty !== undefined) {
            const qty = parseInt(item.qty) || 0;
            if (qty <= 0) return; // qty=0 → ürün çıkarılmış, ekleme
            if (!grouped[key]) grouped[key] = { ad: item.ad, fiyat, qty: 0 };
            grouped[key].qty += qty;
        } else {
            // Eski format: aynı ürün birden fazla satırda tekrar eder
            if (!grouped[key]) grouped[key] = { ad: item.ad, fiyat, qty: 0 };
            grouped[key].qty++;
        }
    });

    // qty > 0 olanları al, sıfır veya negatif olanları düşür
    cart = Object.values(grouped).filter(i => i.qty > 0);
    renderCart();
}

function changeQty(index, delta) {
    cart[index].qty += delta;
    if (cart[index].qty <= 0) cart.splice(index, 1);
    renderCart();
}

function clearCart() { cart = []; renderCart(); }

// ── İndirim hesabı ────────────────────────────────────────────
function applyDiscounts(cartItems, campaigns) {
    let discounts = [];

    campaigns.forEach(camp => {
        if (!camp) return;
        if (camp.type === 'buy_x_get_y') {
            const buy = camp.config.buy || 2;
            const get = camp.config.get || 1;
            cartItems.forEach(item => {
                const sets      = Math.floor(item.qty / (buy + get));
                const remainder = item.qty % (buy + get);
                const freeCount = sets * get + (remainder > buy ? remainder - buy : 0);
                if (freeCount > 0) {
                    const saving = freeCount * item.fiyat;
                    discounts.push({ label: `${camp.title} — ${item.ad} (${freeCount} bedava)`, amount: saving });
                }
            });
        } else if (camp.type === 'percentage') {
            const rawTotal = cartItems.reduce((s, i) => s + i.fiyat * i.qty, 0);
            const saving   = rawTotal * (camp.config.percent / 100);
            if (saving > 0) discounts.push({ label: `${camp.title} (%${camp.config.percent})`, amount: saving });
        } else if (camp.type === 'fixed') {
            const rawTotal = cartItems.reduce((s, i) => s + i.fiyat * i.qty, 0);
            const saving   = Math.min(camp.config.amount, rawTotal);
            if (saving > 0) discounts.push({ label: `${camp.title} (-${camp.config.amount}₺)`, amount: saving });
        }
    });

    return discounts;
}

// ── Sepet render ──────────────────────────────────────────────
function renderCart() {
    const container = document.getElementById('receipt-container');
    const summary   = document.getElementById('receipt-summary');
    container.innerHTML = '';

    if (!cart.length) {
        container.innerHTML = `<p style="color:var(--text-muted);text-align:center;font-size:13px;">${t.cartEmpty}</p>`;
        summary.innerHTML = '';
        return;
    }

    let rawTotal = 0;
    cart.forEach((item, i) => {
        const rowTotal = item.fiyat * item.qty;
        rawTotal += rowTotal;
        const row = document.createElement('div');
        row.className = 'receipt-item';
        row.innerHTML = `
            <span class="receipt-item-name">${item.ad}</span>
            <div class="qty-ctrl">
                <button class="qty-btn" onclick="changeQty(${i},-1)">−</button>
                <span class="qty-num">${item.qty}</span>
                <button class="qty-btn" onclick="changeQty(${i},+1)">+</button>
            </div>
            <span class="receipt-price">${rowTotal}₺</span>`;
        container.appendChild(row);
    });

    const activeCamps = window._activeCampaigns || [];
    const discounts   = applyDiscounts(cart, activeCamps);
    let totalDiscount = 0;

    discounts.forEach(d => {
        totalDiscount += d.amount;
        const row = document.createElement('div');
        row.className = 'discount-row';
        row.innerHTML = `
            <span>🎁 ${d.label}</span>
            <span class="discount-badge">-${d.amount.toFixed(2)}₺</span>`;
        container.appendChild(row);
    });

    const finalTotal = Math.max(0, rawTotal - totalDiscount);
    let summaryHtml = '';
    if (totalDiscount > 0) {
        summaryHtml += `
            <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--text-sub);margin-top:8px">
                <span>Ara Toplam</span><span>${rawTotal.toFixed(2)} ₺</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:12px;color:#27AE60;font-weight:600">
                <span>İndirim</span><span>-${totalDiscount.toFixed(2)} ₺</span>
            </div>`;
    }
    summaryHtml += `<div class="receipt-total">${t.total}: ${finalTotal.toFixed(2)} ₺</div>`;
    summary.innerHTML = summaryHtml;

    document.getElementById('btn-pay').onclick = () => placeOrder(finalTotal);
}

// ── Sipariş gönder ────────────────────────────────────────────
async function placeOrder(finalTotal) {
    if (!cart.length) return;

    const memberPhone = localStorage.getItem('userPhone') || null;
    const items = cart.map(i => ({ name: i.ad, qty: i.qty, price: i.fiyat }));

    try {
        const r = await fetch(window.location.origin + '/order', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ table_no: 'Kiosk', member_phone: memberPhone, items, notes: null }),
        });
        if (!r.ok) {
            const err = await r.json();
            appendMessage('assistant', '⚠️ ' + (err.detail || 'Sipariş gönderilemedi.'));
            return;
        }
        const data = await r.json();
        cart = [];
        renderCart();
        startOrderTracking(data.order_id);
    } catch(e) {
        appendMessage('assistant', '⚠️ Sipariş gönderilemedi: ' + e.message);
    }
}

// ── Sipariş takip ─────────────────────────────────────────────
function startOrderTracking(orderId) {
    document.getElementById('track-order-id').textContent = orderId;
    document.getElementById('track-overlay').classList.add('show');
    updateTrackSteps('pending');

    if (trackingInterval) clearInterval(trackingInterval);
    trackingInterval = setInterval(async () => {
        try {
            const r = await fetch(window.location.origin + '/order/' + orderId + '/status');
            if (!r.ok) return;
            const data = await r.json();
            updateTrackSteps(data.Status);
            if (data.Status === 'completed' || data.Status === 'cancelled') {
                clearInterval(trackingInterval);
                trackingInterval = null;
            }
        } catch(e) {}
    }, 5000);
}

function updateTrackSteps(status) {
    const order = ['pending','preparing','ready','completed'];
    const cur   = order.indexOf(status);
    order.forEach((s, i) => {
        const el = document.getElementById('step-' + s);
        if (!el) return;
        el.classList.remove('done','active');
        if (i < cur)        el.classList.add('done');
        else if (i === cur) el.classList.add('active');
    });
    if (status === 'cancelled') {
        document.getElementById('track-sub').textContent = '❌ Sipariş iptal edildi.';
    }
}

function closeOrderTracking() {
    document.getElementById('track-overlay').classList.remove('show');
    if (trackingInterval) { clearInterval(trackingInterval); trackingInterval = null; }
}

    document.getElementById('track-overlay').classList.remove('show');
    if (trackingInterval) { clearInterval(trackingInterval); trackingInterval = null; }

