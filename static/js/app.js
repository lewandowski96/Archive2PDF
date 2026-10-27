/**
 * ComicFlux - Frontend Client Application
 * Handles file drop, batch upload, live queue, modal inspection, and conversion.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const browseBtn = document.getElementById('browseBtn');
  const queueSection = document.getElementById('queueSection');
  const comicCardList = document.getElementById('comicCardList');
  const queueCountBadge = document.getElementById('queueCountBadge');
  const convertAllBtn = document.getElementById('convertAllBtn');
  const clearAllBtn = document.getElementById('clearAllBtn');
  const downloadAllBtn = document.getElementById('downloadAllBtn');

  // Modal elements
  const inspectorModal = document.getElementById('inspectorModal');
  const closeModalBtn = document.getElementById('closeModalBtn');
  const modalComicTitle = document.getElementById('modalComicTitle');
  const modalComicSub = document.getElementById('modalComicSub');
  const modalPageImg = document.getElementById('modalPageImg');
  const modalPrevPage = document.getElementById('modalPrevPage');
  const modalNextPage = document.getElementById('modalNextPage');
  const modalCurPage = document.getElementById('modalCurPage');
  const modalTotalPages = document.getElementById('modalTotalPages');
  const modalPageRes = document.getElementById('modalPageRes');
  const modalPageFmt = document.getElementById('modalPageFmt');
  const modalPageSize = document.getElementById('modalPageSize');

  // State
  let sessionId = localStorage.getItem('comicflux_session_id');
  if (!sessionId) {
    sessionId = 'sess_' + Math.random().toString(36).substring(2, 11) + Date.now();
    localStorage.setItem('comicflux_session_id', sessionId);
  }

  const itemsMap = new Map(); // itemId -> itemData
  let activeInspector = { itemId: null, pageIndex: 0 };

  // Utility: format bytes
  function formatBytes(bytes, decimals = 1) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  // Browse button trigger
  browseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropzone.addEventListener('click', () => {
    fileInput.click();
  });

  // Drag and Drop handlers
  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFiles(files);
  });

  fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
    fileInput.value = ''; // Reset so identical files can be re-added if desired
  });

  // Process incoming files
  function handleFiles(fileList) {
    if (!fileList || fileList.length === 0) return;
    const validExts = ['.cbz', '.cbr', '.zip', '.rar', '.cbt', '.cb7'];

    const filtered = Array.from(fileList).filter(f => {
      const ext = '.' + f.name.split('.').pop().toLowerCase();
      return validExts.includes(ext);
    });

    if (filtered.length === 0) {
      alert('Please upload comic archives in .cbz, .cbr, or .zip format.');
      return;
    }

    queueSection.classList.add('active');

    filtered.forEach(file => {
      uploadFile(file);
    });
  }

  // Upload and parse comic archive
  async function uploadFile(file) {
    const tempId = 'temp_' + Math.random().toString(36).substring(2, 9);
    
    // Add placeholder card
    const placeholderItem = {
      id: tempId,
      filename: file.name,
      format: file.name.split('.').pop().toUpperCase(),
      size: file.size,
      page_count: '...',
      status: 'extracting',
      progress: 0.15,
      status_message: 'Uploading & unpacking archive...'
    };
    itemsMap.set(tempId, placeholderItem);
    renderQueue();

    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId);

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const data = await response.json();
      const realItem = {
        ...data.item,
        status: 'ready',
        progress: 0.0,
        status_message: 'Ready for lossless conversion'
      };

      itemsMap.delete(tempId);
      itemsMap.set(realItem.id, realItem);
      renderQueue();

    } catch (err) {
      const failedItem = itemsMap.get(tempId);
      if (failedItem) {
        failedItem.status = 'failed';
        failedItem.status_message = err.message;
        renderQueue();
      }
    }
  }

  // Render Queue Cards
  function renderQueue() {
    comicCardList.innerHTML = '';
    const items = Array.from(itemsMap.values());
    
    queueCountBadge.textContent = `${items.length} ${items.length === 1 ? 'file' : 'files'}`;

    if (items.length === 0) {
      queueSection.classList.remove('active');
      downloadAllBtn.style.display = 'none';
      return;
    }

    let hasCompleted = false;

    items.forEach(item => {
      if (item.status === 'completed') hasCompleted = true;

      const card = document.createElement('div');
      card.className = 'comic-card';
      card.id = `card-${item.id}`;

      // Thumbnail
      const hasThumb = item.id && !item.id.startsWith('temp_') && item.page_count > 0;
      const thumbUrl = hasThumb ? `/api/page_image/${sessionId}/${item.id}/0` : '';

      // Format tag class
      let tagClass = 'tag-cbz';
      if (item.format === 'CBR' || item.format === 'RAR') tagClass = 'tag-cbr';
      else if (item.format === 'ZIP') tagClass = 'tag-zip';

      // Metadata info pills
      let metaHtml = '';
      if (item.metadata) {
        if (item.metadata.series) {
          metaHtml += `<span class="pill-detail">Series: <strong>${escapeHtml(item.metadata.series)}</strong></span>`;
        }
        if (item.metadata.number) {
          metaHtml += `<span class="pill-detail">#<strong>${escapeHtml(item.metadata.number)}</strong></span>`;
        }
        if (item.metadata.year) {
          metaHtml += `<span class="pill-detail">Year: <strong>${escapeHtml(item.metadata.year)}</strong></span>`;
        }
        if (item.metadata.writer) {
          metaHtml += `<span class="pill-detail">Writer: <strong>${escapeHtml(item.metadata.writer)}</strong></span>`;
        }
      }

      // Progress bar fill width
      const progPercent = Math.min(Math.round((item.progress || 0) * 100), 100);
      const isDone = item.status === 'completed';

      // Action button
      let actionBtnHtml = '';
      if (isDone) {
        actionBtnHtml = `
          <a href="/api/download/${sessionId}/${item.id}" class="btn-download-pdf" id="dl-${item.id}" download>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            Download PDF
          </a>
        `;
      } else if (item.status === 'converting') {
        actionBtnHtml = `
          <button type="button" class="btn-primary" disabled>
            Converting...
          </button>
        `;
      } else if (item.status === 'failed') {
        actionBtnHtml = `
          <span style="color: var(--danger); font-size: 0.85rem; font-weight: 600;">Failed</span>
        `;
      } else {
        actionBtnHtml = `
          <button type="button" class="btn-primary" onclick="window.convertSingle('${item.id}')">
            Convert
          </button>
        `;
      }

      card.innerHTML = `
        <div class="card-thumbnail-box">
          ${hasThumb ? `<img src="${thumbUrl}" alt="Cover thumbnail" loading="lazy">` : `<span class="card-thumbnail-placeholder">📚</span>`}
        </div>

        <div class="card-main-info">
          <div class="card-top-row">
            <span class="tag-badge ${tagClass}">.${item.format}</span>
            <span class="comic-name" title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</span>
          </div>

          <div class="card-metadata-pills">
            <span class="pill-detail">Pages: <strong>${item.page_count}</strong></span>
            <span class="pill-detail">Size: <strong>${formatBytes(item.size)}</strong></span>
            ${metaHtml}
          </div>

          <div class="card-progress-wrapper">
            <div class="progress-track">
              <div class="progress-bar-fill ${isDone ? 'complete' : ''}" style="width: ${progPercent}%;"></div>
            </div>
            <div class="progress-status-text">
              <span>${item.status_message || ''}</span>
              <span>${progPercent}%</span>
            </div>
          </div>
        </div>

        <div class="card-actions-col">
          ${hasThumb ? `
            <button type="button" class="btn-icon" title="Inspect Pages" onclick="window.openInspector('${item.id}')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            </button>
          ` : ''}

          ${actionBtnHtml}

          <button type="button" class="btn-icon" title="Remove" onclick="window.removeItem('${item.id}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      `;

      comicCardList.appendChild(card);
    });

    downloadAllBtn.style.display = hasCompleted ? 'inline-flex' : 'none';
  }

  // Convert Single Item
  window.convertSingle = async function(itemId) {
    const item = itemsMap.get(itemId);
    if (!item) return;

    item.status = 'converting';
    item.progress = 0.25;
    item.status_message = 'Extracting pages & packaging lossless PDF...';
    renderQueue();

    try {
      const response = await fetch(`/api/convert/${sessionId}/${itemId}`, {
        method: 'POST'
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Conversion failed');
      }

      const res = await response.json();
      item.status = 'completed';
      item.progress = 1.0;
      item.status_message = `Lossless PDF Ready (${res.stats.page_count} pages)`;
      renderQueue();

    } catch (err) {
      item.status = 'failed';
      item.status_message = err.message;
      renderQueue();
    }
  };

  // Convert All Queue Items
  convertAllBtn.addEventListener('click', async () => {
    const pending = Array.from(itemsMap.values()).filter(i => i.status === 'ready' || i.status === 'failed');
    if (pending.length === 0) return;

    for (const item of pending) {
      await window.convertSingle(item.id);
    }
  });

  // Download All as ZIP
  downloadAllBtn.addEventListener('click', () => {
    window.location.href = `/api/download_all/${sessionId}`;
  });

  // Remove item
  window.removeItem = function(itemId) {
    itemsMap.delete(itemId);
    renderQueue();
  };

  // Clear all
  clearAllBtn.addEventListener('click', () => {
    itemsMap.clear();
    renderQueue();
  });

  // Lightbox Page Inspector
  window.openInspector = function(itemId) {
    const item = itemsMap.get(itemId);
    if (!item || !item.page_count) return;

    activeInspector = { itemId: itemId, pageIndex: 0 };
    modalComicTitle.textContent = item.filename;
    modalComicSub.textContent = `Total pages: ${item.page_count} | 100% Lossless`;
    modalTotalPages.textContent = item.page_count;

    updateInspectorPage();
    inspectorModal.classList.add('active');
  };

  function updateInspectorPage() {
    const item = itemsMap.get(activeInspector.itemId);
    if (!item) return;

    const idx = activeInspector.pageIndex;
    modalCurPage.textContent = idx + 1;
    modalPageImg.src = `/api/page_image/${sessionId}/${item.id}/${idx}`;

    const info = item.pages && item.pages[idx];
    if (info) {
      modalPageRes.textContent = `${info.width} × ${info.height} px`;
      modalPageFmt.textContent = `${info.format} (Original Bitstream)`;
      modalPageSize.textContent = formatBytes(info.size_bytes);
    } else {
      modalPageRes.textContent = 'Original Res';
      modalPageFmt.textContent = 'Direct Stream';
      modalPageSize.textContent = '-';
    }
  }

  function closeModal() {
    inspectorModal.classList.remove('active');
    modalPageImg.src = '';
  }

  closeModalBtn.addEventListener('click', closeModal);
  inspectorModal.addEventListener('click', (e) => {
    if (e.target === inspectorModal) closeModal();
  });

  modalPrevPage.addEventListener('click', () => {
    const item = itemsMap.get(activeInspector.itemId);
    if (!item) return;
    if (activeInspector.pageIndex > 0) {
      activeInspector.pageIndex--;
      updateInspectorPage();
    }
  });

  modalNextPage.addEventListener('click', () => {
    const item = itemsMap.get(activeInspector.itemId);
    if (!item) return;
    if (activeInspector.pageIndex < item.page_count - 1) {
      activeInspector.pageIndex++;
      updateInspectorPage();
    }
  });

  // Keyboard navigation for modal
  document.addEventListener('keydown', (e) => {
    if (!inspectorModal.classList.contains('active')) return;
    if (e.key === 'Escape') closeModal();
    else if (e.key === 'ArrowLeft') modalPrevPage.click();
    else if (e.key === 'ArrowRight') modalNextPage.click();
  });

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
});
