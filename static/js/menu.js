// ── Menü ──────────────────────────────────────────────────────
async function fetchMenu() {
    try {
        const r = await fetch(window.location.origin + '/menu');
        const d = await r.json();
        renderMenu(d.menu);
    } catch(e) {
        document.getElementById('menu-container').innerHTML =
            `<p style="color:red;font-size:12px;">${t.menuFailed}</p>`;
    }
}

function renderMenu(menuDb) {
    const cont = document.getElementById('menu-container');
    cont.innerHTML = '';

    for (const [kategori, urunler] of Object.entries(menuDb)) {
        const header = document.createElement('div');
        header.className = 'category-header';
        header.innerText = kategori + ' ▾';

        const list = document.createElement('div');
        list.className = 'menu-items';

        urunler.forEach(item => {
            const sicaklik = item.fiyat_gorunum.includes('Cold') ||
                             item.fiyat_gorunum.includes('Soğuk') ||
                             item.fiyat_gorunum.includes('بارد')
                ? t.cold : t.hot;
            list.innerHTML += `
                <div class="menu-item-card">
                    <div class="item-title">
                        <span>${item.urun}</span>
                        <span>${item.taban_fiyat}₺</span>
                    </div>
                    <div class="item-desc">${sicaklik}</div>
                </div>`;
        });

        header.onclick = () => {
            document.querySelector('.sidebar').classList.remove('open');
            const open = list.classList.contains('active');
            document.querySelectorAll('.menu-items').forEach(el => el.classList.remove('active'));
            if (!open) list.classList.add('active');
        };

        cont.appendChild(header);
        cont.appendChild(list);
    }

    const first = cont.querySelector('.menu-items');
    if (first) first.classList.add('active');
}

// ── Kampanyalar ───────────────────────────────────────────────
async function fetchCampaigns() {
    try {
        const r = await fetch(window.location.origin + '/campaigns');
        if (!r.ok) throw new Error('HTTP ' + r.status);
        window._activeCampaigns = await r.json();
        renderCampaigns(window._activeCampaigns);
    } catch(e) {
        const box = document.getElementById('campaigns-container');
        if (box) box.innerHTML = '<div class="campaign-empty">Kampanyalar yüklenemedi.</div>';
        window._activeCampaigns = [];
    }
}

function renderCampaigns(list) {
    const box = document.getElementById('campaigns-container');
    if (!box) return;
    if (!list || !list.length) {
        box.innerHTML = '<div class="campaign-empty">Şu an aktif kampanya yok.</div>';
        return;
    }
    box.innerHTML = list.map(c => {
        const labels = {
            buy_x_get_y: `${c.config.buy} ALANA ${c.config.get} BEDAVA`,
            percentage:  `%${c.config.percent} İNDİRİM`,
            fixed:       `${c.config.amount}₺ İNDİRİM`,
        };
        const badgeText = labels[c.type] || c.type.toUpperCase();
        const color     = c.badge_color || '#E67E22';
        const dates     = (c.start_date || c.end_date)
            ? `<div class="campaign-dates">📅 ${c.start_date||'—'} → ${c.end_date||'—'}</div>` : '';
        return `
            <div class="campaign-card" style="border-left-color:${color}">
                <span class="campaign-badge" style="background:${color}">${badgeText}</span>
                <div class="campaign-title">${c.title}</div>
                ${c.description ? `<div class="campaign-desc">${c.description}</div>` : ''}
                ${dates}
            </div>`;
    }).join('');
}
