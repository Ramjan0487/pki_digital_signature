/* upload.js — drag-drop upload, AI detection display, NID flow */
(function () {
  const zone       = document.getElementById('uploadZone');
  const input      = document.getElementById('photoInput');
  const preview    = document.getElementById('previewImg');
  const detectRow  = document.getElementById('detectRow');
  const resultArea = document.getElementById('resultArea');
  const scoreGrid  = document.getElementById('scoreGrid');
  const actionRow  = document.getElementById('actionRow');
  const retryBtn   = document.getElementById('retryBtn');
  const proceedBtn = document.getElementById('proceedBtn');
  const cancelBtn  = document.getElementById('cancelBtn');

  let currentAppRef = APP_REF || null;
  let lastFile      = null;

  // ── Drag & drop ────────────────────────────────────────────────────────
  zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  });
  zone.addEventListener('click', () => input.click());
  input.addEventListener('change', () => { if (input.files[0]) handleFile(input.files[0]); });

  retryBtn.addEventListener('click', resetUpload);
  proceedBtn.addEventListener('click', () => {
    if (currentAppRef) window.location.href = `/nid/update?app_ref=${currentAppRef}`;
  });
  cancelBtn.addEventListener('click', async () => {
    if (!currentAppRef) return;
    if (!confirm('Cancel this application? You can start a new one at any time.')) return;
    await fetch(`/nid/cancel/${currentAppRef}`, { method: 'POST', credentials: 'same-origin' });
    window.location.href = '/upload/';
  });

  // ── Handle file ────────────────────────────────────────────────────────
  function handleFile(file) {
    if (!file.type.match(/image\/(jpeg|png|bmp|webp)/)) {
      alert('Invalid file type. Please upload JPG, PNG, BMP, or WebP.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      alert('File too large. Maximum size is 5 MB.');
      return;
    }
    lastFile = file;
    const reader = new FileReader();
    reader.onload = e => {
      preview.src = e.target.result;
      detectRow.classList.remove('hidden');
      scoreGrid.classList.add('hidden');
      actionRow.classList.add('hidden');
      resultArea.innerHTML = '<div class="spinner-large"></div>';
      submitFile(file);
    };
    reader.readAsDataURL(file);
  }

  // ── Submit to backend ──────────────────────────────────────────────────
  async function submitFile(file) {
    const fd = new FormData();
    fd.append('photo', file);
    if (currentAppRef) fd.append('app_ref', currentAppRef);
    fd.append('cert_type', typeof CERT_TYPE !== 'undefined' ? CERT_TYPE : 'LOCAL_INDIVIDUAL');

    try {
      const res  = await fetch('/upload/submit', {
        method: 'POST', body: fd, credentials: 'same-origin'
      });
      const data = await res.json();
      currentAppRef = data.app_ref || currentAppRef;

      if (data.status === 'accepted') {
        renderAccepted(data);
      } else {
        renderRejected(data);
      }
    } catch (err) {
      resultArea.innerHTML = `<div class="result-rejected">
        <div class="result-icon">⚠️</div>
        <div class="result-title">Upload failed</div>
        <div class="result-msg">Network error — please check your connection and try again.</div>
      </div>`;
      showActions(false);
    }
  }

  // ── Render accepted ────────────────────────────────────────────────────
  function renderAccepted(data) {
    const imgSrc = data.annotated_img
      ? `data:image/jpeg;base64,${data.annotated_img}`
      : preview.src;
    preview.src = imgSrc;

    resultArea.innerHTML = `
      <div class="result-accepted">
        <div class="result-icon">✅</div>
        <div class="result-title">Photo accepted!</div>
        <div class="result-msg">${data.message}</div>
      </div>`;

    if (data.scores) {
      scoreGrid.classList.remove('hidden');
      setBar('blurBar',   'blurVal',   data.scores.blur    / 400 * 100, data.scores.blur + ' var');
      setBar('brightBar', 'brightVal', data.scores.brightness / 255 * 100, data.scores.brightness?.toFixed(0));
      setBar('faceBar',   'faceVal',   (data.scores.face_conf || 0) * 100, ((data.scores.face_conf || 0)*100).toFixed(0) + '%');
      const eyeAvg = ((data.scores.eye_left || 0) + (data.scores.eye_right || 0)) / 2;
      setBar('eyeBar', 'eyeVal', eyeAvg / 0.5 * 100, eyeAvg.toFixed(3));
    }
    showActions(true);
    proceedBtn.classList.remove('hidden');
    cancelBtn.classList.add('hidden');
  }

  // ── Render rejected ────────────────────────────────────────────────────
  function renderRejected(data) {
    resultArea.innerHTML = `
      <div class="result-rejected">
        <div class="result-icon">❌</div>
        <div class="result-title">Photo not accepted</div>
        <div class="result-msg">${data.message}</div>
        <div class="defect-tag">${data.defect_code}</div>
      </div>`;

    if (data.scores) {
      scoreGrid.classList.remove('hidden');
      setBar('blurBar',   'blurVal',   data.scores.blur / 400 * 100, data.scores.blur + ' var');
      setBar('brightBar', 'brightVal', data.scores.brightness / 255 * 100, data.scores.brightness?.toFixed(0));
      setBar('faceBar',   'faceVal',   0, '—');
      setBar('eyeBar',    'eyeVal',    0, '—');
    }
    showActions(false);
    proceedBtn.classList.add('hidden');
    cancelBtn.classList.remove('hidden');
  }

  function setBar(barId, valId, pct, label) {
    const bar = document.getElementById(barId);
    const val = document.getElementById(valId);
    if (bar) bar.style.width = Math.min(100, Math.max(0, pct)) + '%';
    if (val) val.textContent = label ?? '—';
  }

  function showActions(accepted) {
    actionRow.classList.remove('hidden');
    if (accepted) {
      proceedBtn.classList.remove('hidden');
    } else {
      cancelBtn.classList.remove('hidden');
    }
  }

  function resetUpload() {
    detectRow.classList.add('hidden');
    scoreGrid.classList.add('hidden');
    actionRow.classList.add('hidden');
    proceedBtn.classList.add('hidden');
    cancelBtn.classList.add('hidden');
    resultArea.innerHTML = '';
    preview.src = '';
    input.value = '';
    lastFile = null;
  }
})();
