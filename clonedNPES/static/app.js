// Simple dashboard JS (reverted)
document.addEventListener('DOMContentLoaded', () => {
  let plates = [];
  let page = 0;
  const PAGE_SIZE = 8;

  async function loadPlates() {
    const plate = document.getElementById('plateFilter') ? document.getElementById('plateFilter').value : '';
    const date = document.getElementById('dateFilter') ? document.getElementById('dateFilter').value : '';
    const qs = new URLSearchParams({ plate, date });
    const res = await fetch('/api/plates?' + qs.toString());
    plates = await res.json();
    renderStats();
    renderTablePage();
  }

  function renderStats() {
    const statTotal = document.getElementById('statTotal');
    const statUnique = document.getElementById('statUnique');
    const statImages = document.getElementById('statImages');
    if (statTotal) statTotal.innerText = plates.length;
    const today = new Date().toISOString().slice(0,10);
    const uniqueToday = new Set(plates.filter(p => p.date === today).map(p => p.plate)).size;
    if (statUnique) statUnique.innerText = uniqueToday;
    const images = plates.filter(p => p.image).length;
    if (statImages) statImages.innerText = images;
  }

  function renderTablePage() {
    // now renders cards into #cardsGrid
    const grid = document.getElementById('cardsGrid');
    if (!grid) return;
    grid.innerHTML = '';
    const start = page * PAGE_SIZE;
    const pageItems = plates.slice(start, start + PAGE_SIZE);
    if (pageItems.length === 0) {
      grid.innerHTML = '<div class="col-12 text-center text-muted">No records</div>';
    }

    pageItems.forEach(r => {
      const col = document.createElement('div');
      col.className = 'col-12 col-sm-6 col-md-4 col-lg-3';
      const img = r.image ? `/snapshots/${encodeURIComponent(r.image)}` : '';
      col.innerHTML = `
        <div class="detection-card card h-100 shadow-sm">
          <div class="card-img-top card-thumb-wrap text-center">
            ${ img ? `<img src="${img}" class="thumb" data-img="${encodeURIComponent(r.image)}"/>` : '<div class="thumb placeholder">No image</div>' }
          </div>
          <div class="card-body p-2">
            <div class="d-flex justify-content-between align-items-start">
              <div>
                <div class="plate-text fw-bold">${r.plate}</div>
                <div class="text-muted small">${r.date} ${r.time}</div>
              </div>
            </div>
          </div>
        </div>
      `;
      grid.appendChild(col);
    });

    const pi = document.getElementById('paginationInfo');
    if (pi) pi.innerText = `Showing ${start+1}-${Math.min(start+PAGE_SIZE, plates.length)} of ${plates.length}`;

    // attach handlers to thumbnails
    grid.querySelectorAll('.thumb').forEach(img => {
      img.style.cursor = 'pointer';
      img.addEventListener('click', (e) => {
        const src = e.currentTarget.getAttribute('src');
        showPreview(src);
      });
    });
    // also populate compact table (if visible)
    const compact = document.querySelector('#platesCompact tbody');
    if (compact) {
      compact.innerHTML = '';
      pageItems.forEach(r => {
        const tr = document.createElement('tr');
        const imgCell = r.image ? `<img src="/snapshots/${encodeURIComponent(r.image)}" class="thumb" style="width:120px;height:70px;object-fit:cover;"/>` : '<div class="thumb placeholder" style="width:120px;height:70px;">No image</div>';
        tr.innerHTML = `
          <td class="fw-bold">${r.plate}</td>
          <td>${r.date}</td>
          <td>${r.time}</td>
          <td>${imgCell}</td>
        `;
        compact.appendChild(tr);
      });
      // attach click handlers inside compact table
      compact.querySelectorAll('img.thumb').forEach(img => img.addEventListener('click', (e)=> showPreview(e.currentTarget.getAttribute('src'))));
    }
  }

  function showPreview(src) {
    const preview = document.getElementById('previewImage');
    preview.src = src;
    const modal = new bootstrap.Modal(document.getElementById('previewModal'));
    modal.show();
  }

  const prevEl = document.getElementById('prevPage');
  const nextEl = document.getElementById('nextPage');
  if (prevEl) prevEl.addEventListener('click', () => { if (page > 0) { page--; renderTablePage(); } });
  if (nextEl) nextEl.addEventListener('click', () => { if ((page+1)*PAGE_SIZE < plates.length) { page++; renderTablePage(); } });

  const refreshEl = document.getElementById('refreshBtn');
  if (refreshEl) refreshEl.addEventListener('click', () => loadPlates());

  async function setStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      const el = document.getElementById('detectorStatus');
      if (data.running) {
        if (el) {
          el.innerText = 'Running';
          el.classList.remove('bg-secondary');
          el.classList.add('badge-running');
        }
      } else {
        if (el) {
          el.innerText = 'Stopped';
          el.classList.remove('badge-running');
          el.classList.add('badge-stopped');
        }
      }
    } catch (e) {
      const el = document.getElementById('detectorStatus');
      if (el) {
        el.innerText = 'Stopped';
        el.classList.remove('badge-running');
        el.classList.add('badge-stopped');
      }
    }
  }

  const startBtn = document.getElementById('startBtn');
  const stopBtn = document.getElementById('stopBtn');
  if (startBtn) startBtn.addEventListener('click', async () => {
    const token = (document.getElementById('apiToken') || {}).value?.trim?.() || '';
    const headers = token ? { 'X-API-KEY': token } : {};
    try {
      const res = await fetch('/api/start', { method: 'POST', headers });
      const data = await res.json();
      alert('Start: ' + data.status);
    } catch (e) { alert('Start request failed'); }
    setTimeout(() => { setStatus(); loadPlates(); }, 800);
  });
  if (stopBtn) stopBtn.addEventListener('click', async () => {
    const token = (document.getElementById('apiToken') || {}).value?.trim?.() || '';
    const headers = token ? { 'X-API-KEY': token } : {};
    try {
      const res = await fetch('/api/stop', { method: 'POST', headers });
      const data = await res.json();
      alert('Stop: ' + data.status);
    } catch (e) { alert('Stop request failed'); }
    setTimeout(() => { setStatus(); }, 400);
  });

  const exportBtn = document.getElementById('exportBtn');
  if (exportBtn) exportBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    const token = (document.getElementById('apiToken') || {}).value?.trim?.() || '';
    const headers = token ? { 'X-API-KEY': token } : {};
    try {
      const res = await fetch('/api/export', { headers });
      if (res.status === 200) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'detected_plates.csv';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } else {
        alert('Export failed: ' + res.status);
      }
    } catch (e) { alert('Export failed'); }
  });

  const logsBtn = document.getElementById('logsBtn');
  if (logsBtn) logsBtn.addEventListener('click', async () => {
    const modal = new bootstrap.Modal(document.getElementById('logsModal'));
    modal.show();
    try {
      const res = await fetch('/api/logs');
      const data = await res.json();
      const lc = document.getElementById('logsContent');
      if (lc) lc.innerText = (data.lines || []).join('\n');
    } catch (e) {
      const lc = document.getElementById('logsContent');
      if (lc) lc.innerText = 'Error fetching logs';
    }
  });

  // initial load + polling
  loadPlates();
  setInterval(() => { loadPlates(); setStatus(); }, 5000);

  // view toggle handlers
  const viewCards = document.getElementById('viewCards');
  const viewTable = document.getElementById('viewTable');
  const cardsGrid = document.getElementById('cardsGrid');
  const compactWrap = document.getElementById('compactTable');
  if (viewCards && viewTable) {
    viewCards.addEventListener('click', () => { viewCards.classList.add('active'); viewTable.classList.remove('active'); cardsGrid.classList.remove('d-none'); compactWrap.classList.add('d-none'); });
    viewTable.addEventListener('click', () => { viewTable.classList.add('active'); viewCards.classList.remove('active'); cardsGrid.classList.add('d-none'); compactWrap.classList.remove('d-none'); });
  }
});
