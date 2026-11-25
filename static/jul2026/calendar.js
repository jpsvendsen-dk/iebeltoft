'use strict';
(() => {
  const $ = (id) => document.getElementById(id);
  const preview = location.pathname.startsWith('/admin/');
  const api = location.pathname.startsWith('/admin/') ? '/admin/jul2026/api' : '/Jul2026/api';
  const openedKey = location.pathname.startsWith('/admin/') ? 'jul2026-preview-opened' : 'jul2026-opened';
  const openingMs = 4800;
  document.documentElement.style.setProperty('--door-opening-duration', `${openingMs}ms`);
  const order = [7,18,3,12,21,6,15,1,23,9,4,17,11,20,8,24,14,2,22,5,16,10,19,13];
  let state = null, sound = true, busy = false, timer, audio, creakBuffer, activeCreak;
  let audioReady = Promise.resolve(false);
  let popupVideoId = null;
  let videoPlayer = null, videoReady = false, videoGeneration = 0, videoTimer, youtubeApi;
  function loadYouTubeApi() {
    if (window.YT && window.YT.Player) return Promise.resolve(window.YT);
    if (youtubeApi) return youtubeApi;
    youtubeApi = new Promise((resolve, reject) => {
      const previous = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        try { if (previous) previous(); } catch (_) {}
        resolve(window.YT);
      };
      const script = document.createElement('script');
      script.src = 'https://www.youtube.com/iframe_api'; script.async = true;
      script.onerror = () => { youtubeApi = null; reject(Error('Videoafspilleren kunne ikke indlæses.')); };
      document.head.append(script);
    });
    return youtubeApi;
  }
  function showPicture() {
    try { if (videoReady && videoPlayer) videoPlayer.pauseVideo(); } catch (_) {}
    $('video-container').classList.remove('video-visible');
    $('video-container').setAttribute('aria-hidden', 'true');
    $('video-container').inert = true;
    $('video-help').hidden = true;
    $('animal-art').hidden = false;
    $('play-inline').setAttribute('aria-pressed', 'false');
    if (videoReady) $('play-inline').textContent = '▶ Afspil video her';
  }
  function disposeVideo() {
    videoGeneration++; clearTimeout(videoTimer);
    try { if (videoPlayer) videoPlayer.destroy(); } catch (_) {}
    videoPlayer = null; videoReady = false; popupVideoId = null;
    $('video-container').replaceChildren(); showPicture();
  }
  function prepareVideo() {
    const generation = ++videoGeneration;
    $('play-inline').disabled = true;
    $('play-inline').textContent = 'Klargør video …';
    if (!popupVideoId) { $('play-inline').textContent = 'Brug YouTube-linket'; return; }
    const failed = () => {
      if (generation !== videoGeneration) return;
      videoReady = false; $('play-inline').disabled = true;
      $('play-inline').textContent = 'Brug YouTube-linket';
      $('video-help').textContent = 'Videoen kunne ikke klargøres her. Vælg “Åbn på YouTube”.';
      $('video-help').hidden = false;
    };
    const frame = document.createElement('iframe');
    frame.title = `${$('song-title').textContent} – ${$('song-artist').textContent}`;
    frame.allow = 'autoplay; encrypted-media; fullscreen; picture-in-picture; web-share';
    frame.allowFullscreen = true;
    frame.referrerPolicy = 'strict-origin-when-cross-origin';
    frame.src = `https://www.youtube-nocookie.com/embed/${popupVideoId}?enablejsapi=1&autoplay=0&playsinline=1&rel=0&hl=da&origin=${encodeURIComponent(location.origin)}`;
    $('video-container').replaceChildren();
    $('video-container').append(frame);
    videoTimer = setTimeout(failed, 12000);
    loadYouTubeApi().then(YT => {
      if (generation !== videoGeneration || !$('surprise').open) return;
      videoPlayer = new YT.Player(frame, {events: {
        onReady: event => {
          if (generation !== videoGeneration) return;
          clearTimeout(videoTimer); videoPlayer = event.target; videoReady = true;
          $('play-inline').disabled = false; $('play-inline').textContent = '▶ Afspil video her';
        },
        onAutoplayBlocked: () => {
          if (generation !== videoGeneration) return;
          $('video-help').textContent = 'Tryk på afspilningsknappen i videoen, hvis din browser kræver det. Du kan også vælge “Åbn på YouTube”.';
          $('video-help').hidden = false;
        },
        onError: failed,
      }});
    }).catch(failed);
  }
  $('play-inline').addEventListener('click', () => {
    if ($('video-container').classList.contains('video-visible')) { showPicture(); return; }
    if (!videoReady || !videoPlayer) return;
    stopCreak();
    $('video-container').classList.add('video-visible');
    $('video-container').setAttribute('aria-hidden', 'false');
    $('video-container').inert = false;
    $('video-help').textContent = 'Kan videoen ikke afspilles her? Vælg “Åbn på YouTube”.';
    $('video-help').hidden = false;
    $('animal-art').hidden = true;
    $('play-inline').setAttribute('aria-pressed', 'true');
    $('play-inline').textContent = 'Vis billedet';
    // The ready player's play command runs synchronously in the mobile tap.
    // Do not await loading or create a new iframe here: Safari loses the gesture.
    try { videoPlayer.unMute(); videoPlayer.playVideo(); } catch (_) { notice('Brug afspilningsknappen i videoen eller “Åbn på YouTube”.'); }
  });
  $('surprise').addEventListener('close', disposeVideo);
  $('surprise').addEventListener('cancel', disposeVideo);
  let opened = new Set();
  let account = null, refreshing = false, syncing = false, syncAgain = false;
  const storageDays = (key) => {
    try { const days = JSON.parse(localStorage.getItem(key) || '[]'); return Array.isArray(days) ? days.filter(n => Number.isInteger(n) && n >= 1 && n <= 24) : []; }
    catch (_) { return []; }
  };
  const profileKey = (id) => `jul2026-account-${id}`;
  function rememberOpened() {
    try { localStorage.setItem(account ? profileKey(account.id) : openedKey, JSON.stringify([...opened])); return true; } catch (_) { return false; }
  }
  function accountDisplay(message = '') {
    $('account-open').hidden = preview; $('account-status').hidden = preview;
    $('account-open').textContent = account ? 'Min kalender' : 'Gem min kalender';
    $('account-guest').hidden = Boolean(account); $('account-signed-in').hidden = !account;
    $('account-email').textContent = account ? `Du er logget ind som ${account.email}` : '';
    $('account-status').textContent = message || (account ? `Din kalender gemmes på din profil · ${account.email}` : 'Gem med din e-mail, og tag dine låger med på alle enheder.');
    $('account-status').toggleAttribute('data-error', Boolean(message));
  }
  async function syncOpened() {
    if (!account || preview) return;
    if (syncing) { syncAgain = true; return; }
    syncing = true;
    try {
      do {
        syncAgain = false;
        const id = account.id;
        const response = await fetch('/Jul2026/api/account/opened', {method:'POST', headers:{'Content-Type':'application/json','X-Calendar-Request':'1'}, body:JSON.stringify({account_id:id,days:[...opened].filter(day => day <= state.available || account.opened.includes(day))})});
        if (!response.ok) throw Error(response.status === 401 ? 'Dit login er udløbet. Log ind igen for at synkronisere dine låger.' : response.status === 409 ? 'En anden kalender er logget ind i denne browser. Opdatér siden.' : 'Dine låger venter på at blive gemt på profilen. Vi prøver igen automatisk.');
        const result = await response.json();
        if (!account || account.id !== id) return;
        for (const day of result.opened) opened.add(day);
        rememberOpened(); accountDisplay();
        if (!busy) render();
      } while (syncAgain && account);
    } catch (error) { accountDisplay(error.message || 'Forbindelsen driller. Dine låger venter på at blive gemt.'); }
    finally { syncing = false; }
  }
  try {
    const saved = JSON.parse(localStorage.getItem(openedKey) || '[]');
    if (Array.isArray(saved)) opened = new Set(saved.filter(n => Number.isInteger(n) && n >= 1 && n <= 24));
    sound = localStorage.getItem('jul2026-sound') !== 'off';
  } catch (_) { /* Browser privacy settings may disable local storage. */ }
  const lock = '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="4" y="9" width="12" height="9" rx="2"/><path d="M6 9V6a4 4 0 0 1 8 0v3"/></svg>';
  function notice(message) {
    $('toast').textContent = message; $('toast').hidden = false;
    clearTimeout(timer); timer = setTimeout(() => { $('toast').hidden = true; }, 4500);
  }
  function photo(day) {
    const x = ((day - 1) % 6) * 256, y = Math.floor((day - 1) / 6) * 256;
    return `<svg class="photo-crop" xmlns="http://www.w3.org/2000/svg" viewBox="${x} ${y} 256 256" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false"><image href="/static/jul2026/animals-fotorealistisk.png" width="1536" height="1024"/></svg>`;
  }
  function updateSound() { $('sound').setAttribute('aria-pressed', String(sound)); $('sound-label').textContent = sound ? 'Lyd til' : 'Lyd fra'; }
  function stopCreak() {
    if (!activeCreak) return;
    try { activeCreak.stop(); } catch (_) {}
    activeCreak = null;
  }
  $('sound').addEventListener('click', () => {
    sound = !sound;
    if (sound) prepareAudio(); else stopCreak();
    updateSound(); try { localStorage.setItem('jul2026-sound', sound ? 'on' : 'off'); } catch (_) {}
  });
  $('sound-test').addEventListener('click', () => {
    if (busy) return;
    sound = true; updateSound();
    try { localStorage.setItem('jul2026-sound', 'on'); } catch (_) {}
    prepareAudio(); void creak();
  });
  updateSound();
  function prepareAudio() {
    if (!sound) return Promise.resolve(false);
    try {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) return Promise.resolve(false);
      // iPhone uses an ambient session by default. Request media playback only
      // when the visitor has sound enabled and taps a door or a sound control.
      try { if (navigator.audioSession) navigator.audioSession.type = 'playback'; } catch (_) {}
      if (!audio || audio.state === 'closed') { audio = new Audio(); creakBuffer = null; }
      // Both resume and the silent warm-up must start inside the original tap,
      // before fetch/await consumes Safari's transient user activation.
      const resumed = audio.state === 'running' ? Promise.resolve() : audio.resume();
      audioReady = Promise.resolve(resumed).then(() => audio.state === 'running', () => false);
      const warmup = audio.createBufferSource();
      warmup.buffer = audio.createBuffer(1, 1, audio.sampleRate);
      warmup.connect(audio.destination); warmup.onended = () => warmup.disconnect(); warmup.start(0);
      if (!creakBuffer) creakBuffer = createCreakBuffer();
    } catch (_) { audioReady = Promise.resolve(false); }
    return audioReady;
  }
  function createCreakBuffer() {
    // Friction on old hinges: uneven low groans, metallic squeals and dry wood.
    // Render once, locally, so all layers share the exact animation duration.
    const seconds = openingMs / 1000, rate = audio.sampleRate;
    const buffer = audio.createBuffer(1, Math.ceil(rate * seconds), rate);
    const samples = buffer.getChannelData(0);
    let phase = 0, wood = 0, seed = 2026;
    for (let i = 0; i < samples.length; i++) {
      const t = i / rate, progress = t / seconds;
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      const noise = seed / 2147483648 - 1;
      wood = wood * .96 + noise * .04;
      const strain = Math.sin(t * 2.1) * Math.sin(t * 6.7);
      const pitch = 70 + 28 * Math.sin(progress * Math.PI) + 13 * strain + 2 * Math.sin(t * 45);
      phase += 2 * Math.PI * pitch / rate;
      const stiction = .42 + .58 * Math.pow(.5 + .5 * Math.sin(t * (17 + 8 * progress)), 3);
      const groan = Math.sin(phase) * .34 + Math.sin(phase * 2) * .16 + Math.sin(phase * 3) * .10;
      const squeal = Math.sin(phase * 8 + Math.sin(t * 11) * 1.4) * .10 + Math.sin(phase * 13) * .035;
      const crackle = noise * Math.pow(.5 + .5 * Math.sin(t * 31), 16) * .10;
      const fade = Math.min(1, t / .18) * Math.min(1, (seconds - t) / .55);
      samples[i] = Math.tanh((groan * stiction + squeal * (.4 + .6 * Math.sin(progress * Math.PI)) + wood * .65 + crackle) * 1.3) * fade * .78;
    }
    return buffer;
  }
  async function creak() {
    if (!sound) return false;
    try {
      const ready = await Promise.race([audioReady, new Promise(resolve => setTimeout(() => resolve(false), 800))]);
      if (!sound) return false;
      if (!ready || !audio || audio.state !== 'running') {
        notice('Tryk på “Prøv lågelyden” for at starte lyden.');
        return false;
      }
      stopCreak();
      const source = audio.createBufferSource(); source.buffer = creakBuffer;
      const filter = audio.createBiquadFilter(); filter.type = 'lowpass'; filter.frequency.value = 3400;
      source.connect(filter); filter.connect(audio.destination);
      activeCreak = source;
      source.onended = () => { source.disconnect(); filter.disconnect(); if (activeCreak === source) activeCreak = null; };
      source.start();
      return true;
    } catch (_) { notice('Lyden kunne ikke starte. Prøv knappen “Prøv lågelyden”.'); return false; }
  }
  function updateCount() { $('opened-count').textContent = `${opened.size} af 24 juleøjeblikke åbnet`; }
  function render() {
    if (!state) return;
    const root = $('calendar'); root.replaceChildren(); root.setAttribute('aria-busy', 'false');
    order.forEach(day => {
      const available = day <= state.available, seen = opened.has(day);
      const el = document.createElement('button'); el.type = 'button'; el.className = `door${available ? ' available' : ''}${seen ? ' opened' : ''}${!state.preview && state.today === `2026-12-${String(day).padStart(2,'0')}` ? ' today' : ''}`;
      el.dataset.day = day; el.setAttribute('aria-label', `${day}. december${seen ? ', allerede åbnet' : available ? ', åbn lågen' : ', låst indtil denne dato'}`);
      el.setAttribute('aria-disabled', String(!available));
      el.innerHTML = `<span class="door-scene" aria-hidden="true"><span class="door-back">✦</span><span class="flap"><span class="door-decoration">✧</span><span class="door-number">${day}</span><span class="door-status">${available ? '' : lock}</span></span></span>`;
      if (seen) { const back = el.querySelector('.door-back'); back.classList.add('has-art'); back.innerHTML = photo(day); }
      el.addEventListener('click', () => openDoor(day, el)); root.append(el);
    });
    $('preview-note').hidden = !state.preview;
    if (state.preview) $('calendar-status').textContent = 'Tag et smugkig på decemberens små overraskelser.';
    else if (state.early_access) $('calendar-status').textContent = 'Du har fået tidlig adgang til alle 24 låger.';
    else if (!state.available) $('calendar-status').textContent = 'Vi åbner den første låge den 1. december. Glæd dig!';
    else if (state.available === 24) $('calendar-status').textContent = 'Alle låger er åbne. Rigtig glædelig jul!';
    else $('calendar-status').textContent = `December er her · Du kan åbne låge 1–${state.available}`;
    updateCount();
  }
  async function refresh() {
    if (refreshing || busy) return;
    refreshing = true;
    try {
      const r = await fetch(`${api}/state`, {cache:'no-store'}); if (!r.ok) throw Error();
      const nextState = await r.json();
      if (!preview) {
        const response = await fetch('/Jul2026/api/account', {cache:'no-store'}); if (!response.ok) throw Error();
        const nextAccount = (await response.json()).account;
        if (nextAccount) {
          const cached = storageDays(profileKey(nextAccount.id));
          const previous = account && account.id === nextAccount.id ? [...opened] : [];
          let guest = [];
          try { if (sessionStorage.getItem('jul2026-merge-guest') === 'yes') guest = storageDays('jul2026-opened'); } catch (_) {}
          opened = new Set([...nextAccount.opened, ...cached, ...previous, ...guest].filter(day => Number.isInteger(day) && day >= 1 && day <= 24 && (day <= nextState.available || nextAccount.opened.includes(day))));
          account = nextAccount;
          const cachedSafely = rememberOpened();
          try { if (cachedSafely && sessionStorage.getItem('jul2026-merge-guest') === 'yes') { sessionStorage.removeItem('jul2026-merge-guest'); localStorage.removeItem('jul2026-opened'); } } catch (_) {}
        } else {
          // A different person using this browser must never inherit account progress.
          if (account) opened = new Set(storageDays(openedKey));
          account = null;
        }
      }
      state = nextState; accountDisplay();
      if (!busy) render();
      if (account && [...opened].some(day => !account.opened.includes(day))) await syncOpened();
    } catch (_) {
      if (!state) { $('calendar-status').textContent = 'Lysene driller lidt. Tryk her for at prøve igen.'; $('calendar-status').style.cursor = 'pointer'; $('calendar-status').onclick = refresh; }
      else if (account) accountDisplay('Forbindelsen driller. Dine låger synkroniseres, når du er online igen.');
    } finally { refreshing = false; }
  }
  async function openDoor(day, el) {
    if (busy) return;
    if (!state) return;
    prepareAudio(); busy = true; el.disabled = true;
    let refreshAccess = false;
    const clickAccountId = account ? account.id : null;
    try {
      const options = {method:'POST', cache:'no-store', headers:{'Content-Type':'application/json','X-Calendar-Request':'1'}, body:JSON.stringify({event_id:crypto.randomUUID(), account_id:clickAccountId})};
      let r;
      // Reuse this click's ID if the response is lost; the server logs it once.
      try { r = await fetch(`${api}/doors/${day}/open`, options); }
      catch (_) { r = await fetch(`${api}/doors/${day}/open`, options); }
      const data = await r.json();
      if (!r.ok) { refreshAccess = [401,403,409].includes(r.status); throw Error(typeof data.detail === 'string' ? data.detail : 'Lågen kunne ikke åbnes. Prøv igen.'); }
      if ((account ? account.id : null) !== clickAccountId) throw Error('Dit login er ændret. Opdatér kalenderen, og prøv igen.');
      const back = el.querySelector('.door-back'); back.classList.add('has-art'); back.innerHTML = photo(day);
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      await creak();
      el.classList.add('opening');
      await new Promise(resolve => setTimeout(resolve, reducedMotion ? 0 : openingMs));
      $('animal-art').innerHTML = photo(day); $('animal-art').setAttribute('aria-label', data.animal);
      const bounds = el.getBoundingClientRect();
      if (bounds.width > 0 && bounds.height > 0) $('surprise-media').style.setProperty('--photo-aspect', `${bounds.width} / ${bounds.height}`);
      $('day-label').textContent = `${day}. DECEMBER · 2026`;
      $('surprise-title').textContent = day === 24 ? 'Rigtig glædelig jul' : 'Et lille juleøjeblik';
      $('animal-caption').textContent = `${data.animal}. ${day === 24 ? 'Her er julens største hit til din juleaften.' : 'En stille stund og en sang, der varmer.'}`;
      $('song-title').textContent = data.title; $('song-artist').textContent = data.artist; $('youtube').href = data.youtube;
      disposeVideo();
      const videoId = new URL(data.youtube).searchParams.get('v');
      popupVideoId = videoId && /^[A-Za-z0-9_-]{11}$/.test(videoId) ? videoId : null;
      $('surprise').showModal();
      prepareVideo();
      opened.add(day); rememberOpened();
      el.classList.remove('opening'); el.classList.add('opened'); el.setAttribute('aria-label', `${day}. december, allerede åbnet`); updateCount();
      if (account && !account.opened.includes(day)) account.opened.push(day);
    } catch (error) { el.classList.remove('opening'); notice(error.message || 'Forbindelsen driller. Prøv igen om lidt.'); }
    finally { busy = false; el.disabled = false; if (refreshAccess) void refresh(); }
  }
  $('surprise-close').onclick = () => { disposeVideo(); $('surprise').close(); };
  $('youtube').addEventListener('click', () => { disposeVideo(); $('surprise').close(); });
  $('account-open').onclick = () => { accountDisplay(); $('account-dialog').showModal(); };
  $('account-close').onclick = () => $('account-dialog').close();
  $('login-form').addEventListener('submit', async event => {
    event.preventDefault(); $('login-submit').disabled = true; $('login-status').textContent = 'Vi sender dit personlige link …';
    try {
      const response = await fetch('/Jul2026/api/login/request', {method:'POST', headers:{'Content-Type':'application/json','X-Calendar-Request':'1'}, body:JSON.stringify({email:$('login-email').value.trim()})});
      const result = await response.json();
      if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : 'Skriv en gyldig e-mailadresse, og prøv igen.');
      $('login-status').textContent = result.message;
    } catch (error) { $('login-status').textContent = error.message || 'Mailen kunne ikke sendes. Prøv igen.'; }
    finally { $('login-submit').disabled = false; }
  });
  $('logout').onclick = async () => {
    if (busy || refreshing || syncing) { notice('Vent et øjeblik, mens din kalender gemmes.'); return; }
    $('logout').disabled = true;
    try {
      const response = await fetch('/Jul2026/api/logout', {method:'POST',headers:{'X-Calendar-Request':'1'}});
      if (!response.ok) throw Error();
      location.assign('/Jul2026');
    } catch (_) { notice('Du kunne ikke logges ud. Tjek forbindelsen, og prøv igen.'); $('logout').disabled = false; }
  };
  $('about-open').onclick = () => $('about').showModal();
  $('about-close').onclick = $('about-done').onclick = () => $('about').close();
  for (const d of [$('surprise'), $('about'), $('account-dialog')]) d.addEventListener('click', e => { const b = d.getBoundingClientRect(); if (e.target === d && (e.clientX < b.left || e.clientX > b.right || e.clientY < b.top || e.clientY > b.bottom)) d.close(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  accountDisplay(); setInterval(refresh, 60000); refresh();
})();
