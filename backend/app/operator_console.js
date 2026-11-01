'use strict';
const element = (id) => document.getElementById(id);
let csrf = null;
let busy = false;

function message(text, error = false) {
  element('message').textContent = text;
  element('message').className = error ? 'error' : '';
}
function clearOverview() {
  csrf = null;
  element('families').replaceChildren();
  element('signed-in').textContent = '';
  element('count').textContent = '';
  element('overview').hidden = true;
  element('login-panel').hidden = false;
}
async function api(path, options = {}) {
  const response = await fetch('/operator/api/' + path, { credentials: 'same-origin', cache: 'no-store', ...options });
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) clearOverview();
    const text = response.status === 429 ? 'Zu viele Anmeldeversuche. Bitte später erneut versuchen.'
      : response.status === 401 ? 'Anmeldung erforderlich oder Zugangsdaten ungültig.'
      : response.status === 403 ? 'Dieser Zugriff ist nicht erlaubt. Bitte erneut anmelden.'
      : 'Die Anfrage ist fehlgeschlagen. Bitte erneut versuchen.';
    throw new Error(text);
  }
  return response.status === 204 ? null : response.json();
}
function renderFamily(family) {
  const li = document.createElement('li');
  const title = document.createElement('h3');
  title.textContent = family.name;
  const status = document.createElement('p');
  const labels = {active: 'Aktiv', disabled: 'Gesperrt', provisioning: 'In Einrichtung'};
  status.textContent = labels[family.status] || 'Unbekannter Status';
  status.className = 'state ' + (family.status === 'active' ? 'active' : 'disabled');
  const accounts = document.createElement('p');
  accounts.textContent = `${family.accounts} verknüpfte Konten`;
  li.append(title, status, accounts);
  return li;
}
async function refresh() {
  const session = await api('session');
  const families = await api('families');
  csrf = session.csrf_token;
  element('signed-in').textContent = 'Angemeldet als ' + session.email;
  element('families').replaceChildren(...families.map(renderFamily));
  element('count').textContent = `${families.length} registrierte Familien`;
  element('login-panel').hidden = true;
  element('overview').hidden = false;
  message('Übersicht aktualisiert.');
}
async function run(action) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('button').forEach((button) => { button.disabled = true; });
  try { await action(); }
  catch (error) { clearOverview(); message(error instanceof Error ? error.message : 'Verbindung fehlgeschlagen.', true); }
  finally { busy = false; document.querySelectorAll('button').forEach((button) => { button.disabled = false; }); }
}
element('login-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const password = element('password').value;
  element('password').value = '';
  void run(async () => {
    await api('login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email:element('email').value, password})});
    await refresh();
  });
});
element('refresh').addEventListener('click', () => { void run(refresh); });
element('logout').addEventListener('click', () => { void run(async () => {
  await api('logout', {method:'POST', headers:{'x-csrf-token':csrf || ''}});
  clearOverview();
  message('Abgemeldet.');
}); });
void run(async () => {
  try { await refresh(); }
  catch { clearOverview(); message('Bitte mit deinem Betreiberzugang anmelden.'); }
});
