/* login.js — mTLS badge, form validation, submit */
(function () {
  const form    = document.getElementById('loginForm');
  const nidIn   = document.getElementById('national_id');
  const pwIn    = document.getElementById('password');
  const pwTog   = document.getElementById('pwToggle');
  const nidHint = document.getElementById('nidHint');
  const btn     = document.getElementById('loginBtn');
  const btnTxt  = document.getElementById('btnText');
  const spinner = document.getElementById('btnSpinner');
  const badge   = document.getElementById('mtlsBadge');
  const lbl     = document.getElementById('mtlsLabel');
  const certDiv = document.getElementById('certInfo');

  // ── mTLS detection (cert info forwarded by Nginx) ──────────────────────
  async function checkMTLS() {
    try {
      const res  = await fetch('/auth/cert-status', { credentials: 'same-origin' });
      const data = await res.json();
      if (data.verified) {
        badge.style.background = '#f0fdf4';
        lbl.textContent = 'mTLS certificate verified';
        certDiv.textContent = `Certificate: ${data.subject || 'GovCA Client Cert'}`;
      } else {
        badge.style.background = '#fef9c3';
        badge.style.borderColor = '#fde68a';
        badge.querySelector('.badge-dot').style.background = '#d97706';
        lbl.style.color = '#b45309';
        lbl.textContent = 'No client certificate (password only)';
      }
    } catch {
      lbl.textContent = 'mTLS status unavailable';
    }
  }
  checkMTLS();

  // ── NID live validation ──────────────────────────────────────────────────
  nidIn.addEventListener('input', () => {
    const v = nidIn.value.replace(/\D/g, '');
    nidIn.value = v;
    nidHint.textContent = v.length > 0 && v.length !== 16
      ? `${v.length}/16 digits` : '';
  });

  // ── Password toggle ──────────────────────────────────────────────────────
  pwTog.addEventListener('click', () => {
    const show = pwIn.type === 'password';
    pwIn.type      = show ? 'text' : 'password';
    pwTog.textContent = show ? 'Hide' : 'Show';
  });

  // ── Submit ───────────────────────────────────────────────────────────────
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    nidHint.textContent = '';

    const nid = nidIn.value.trim();
    const pw  = pwIn.value;

    if (!/^\d{16}$/.test(nid)) {
      nidHint.textContent = 'Must be exactly 16 digits.';
      nidIn.focus();
      return;
    }
    if (pw.length < 8) {
      nidHint.textContent = 'Password too short.';
      pwIn.focus();
      return;
    }

    btnTxt.textContent = 'Signing in…';
    spinner.classList.remove('hidden');
    btn.disabled = true;

    try {
      const res = await fetch('/auth/login', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body:    JSON.stringify({ national_id: nid, password: pw }),
        credentials: 'same-origin',
      });
      const data = await res.json();

      if (res.ok && data.redirect) {
        window.location.href = data.redirect;
      } else {
        showError(data.message || 'Login failed. Please try again.');
      }
    } catch {
      showError('Network error. Please check your connection.');
    } finally {
      btnTxt.textContent = 'Sign In Securely';
      spinner.classList.add('hidden');
      btn.disabled = false;
    }
  });

  function showError(msg) {
    let alert = document.querySelector('.alert-error');
    if (!alert) {
      alert = document.createElement('div');
      alert.className = 'alert alert-error';
      form.prepend(alert);
    }
    alert.textContent = msg;
  }
})();
