'use strict';
(() => {
  const token = new URLSearchParams(location.hash.slice(1)).get('token');
  // Remove the secret from the address bar before any network requests.
  history.replaceState(null, '', '/Jul2026/login');
  const button = document.getElementById('confirm-login');
  const status = document.getElementById('login-result');
  if (!token || !/^[A-Za-z0-9_-]{43}$/.test(token)) {
    button.hidden = true;
    status.textContent = 'Loginlinket mangler eller er ugyldigt. Gå tilbage til kalenderen og bestil et nyt link.';
    return;
  }
  button.addEventListener('click', async () => {
    button.disabled = true; status.textContent = 'Vi henter din kalender …';
    try {
      const response = await fetch('/Jul2026/api/login/consume', {method:'POST', headers:{'Content-Type':'application/json','X-Calendar-Request':'1'}, body:JSON.stringify({token})});
      const result = await response.json();
      if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : 'Login kunne ikke gennemføres. Bestil et nyt link.');
      const account = await fetch('/Jul2026/api/account', {cache:'no-store'});
      if (!account.ok || !(await account.json()).account) throw Error('Browseren skal tillade nødvendige cookies for at huske dit login. Bestil et nyt link, når cookies er tilladt.');
      try { sessionStorage.setItem('jul2026-merge-guest', 'yes'); } catch (_) {}
      location.replace('/Jul2026');
    } catch (error) {
      status.textContent = error.message || 'Forbindelsen driller. Prøv igen.';
      button.disabled = false;
    }
  });
})();
