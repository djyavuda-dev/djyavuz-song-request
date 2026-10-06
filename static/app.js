const input = document.getElementById('q');
const resultsEl = document.getElementById('results');
const statusEl = document.getElementById('status');

// Names are no longer collected; the server still receives a fixed placeholder.
const GUEST_NAME = 'Misafir / Guest';

let debounceTimer = null;

input.addEventListener('input', () => {
  clearTimeout(debounceTimer);
  const query = input.value.trim();
  if (!query) {
    resultsEl.innerHTML = '';
    return;
  }
  debounceTimer = setTimeout(() => runSearch(query), 350);
});

async function runSearch(query) {
  const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
  const tracks = await res.json();
  renderResults(tracks);
}

function renderResults(tracks) {
  resultsEl.innerHTML = '';
  for (const t of tracks) {
    const li = document.createElement('li');
    li.className = 'track';
    li.innerHTML = `
      <img class="track__art" src="${t.album_art || ''}" alt="" />
      <div class="track__meta">
        <div class="track__name">${escapeHtml(t.name)}</div>
        <div class="track__artist">${escapeHtml(t.artist)}</div>
      </div>
      <button class="track__button">Request / İste</button>
    `;
    li.querySelector('button').addEventListener('click', (e) => requestTrack(t, e.target));
    resultsEl.appendChild(li);
  }
}

async function requestTrack(track, button) {
  button.disabled = true;
  button.textContent = '...';
  setStatus('', '');

  try {
    const res = await fetch('/api/request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: track.id,
        uri: track.uri,
        name: track.name,
        artist: track.artist,
        requester_name: GUEST_NAME,
      }),
    });
    const data = await res.json();
    if (data.ok) {
      button.textContent = 'Added / Eklendi';
      setStatus(`"${track.name}" added to the list. / listeye eklendi.`, 'ok');
    } else {
      button.disabled = false;
      button.textContent = 'Request / İste';
      setStatus(data.error || 'Something went wrong. / Bir şeyler ters gitti.', 'error');
    }
  } catch (err) {
    button.disabled = false;
    button.textContent = 'Request / İste';
    setStatus('Connection error, try again. / Bağlantı hatası, tekrar dene.', 'error');
  }
}

function setStatus(message, kind) {
  statusEl.textContent = message;
  statusEl.className = 'status' + (kind ? ' ' + kind : '');
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
