'use strict';
const element = (id) => document.getElementById(id);
let csrf = null;
let busy = false;
let creationCapacity = 0;
let creationKey = null;

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
  element('create-family-form').reset();
  element('create-family-form').hidden = true;
  element('creation-jobs').replaceChildren();
  creationCapacity = 0;
}
async function api(path, options = {}) {
  const response = await fetch('/operator/api/' + path, { credentials: 'same-origin', cache: 'no-store', ...options });
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) clearOverview();
    const text = response.status === 429 ? 'Zu viele Anmeldeversuche. Bitte später erneut versuchen.'
      : response.status === 401 ? 'Anmeldung erforderlich oder Zugangsdaten ungültig.'
      : response.status === 403 ? 'Dieser Zugriff ist nicht erlaubt. Bitte erneut anmelden.'
      : response.status === 409 ? 'Der Status, die Bestätigung oder dieser Auftrag passt nicht mehr. Bitte aktualisieren und prüfen.'
      : response.status === 422 ? 'Bitte alle Pflichtfelder und die Bestätigung prüfen.'
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
  const labels = {active: 'Aktiv', disabled: 'Gesperrt', provisioning: 'In Einrichtung', provisioning_failed: 'Einrichtung fehlgeschlagen – manuell prüfen'};
  status.textContent = labels[family.status] || 'Unbekannter Status';
  status.className = 'state ' + (family.status === 'active' ? 'active' : 'disabled');
  const accounts = document.createElement('p');
  accounts.textContent = `${family.accounts} verknüpfte Konten`;
  li.append(title, status, accounts);
  if (family.status === 'active' || family.status === 'disabled') {
    const change = document.createElement('button');
    change.type = 'button';
    change.textContent = family.status === 'active' ? 'Familie sperren' : 'Wieder freigeben';
    change.addEventListener('click', () => showChange(li, family));
    li.append(change);
  }
  const history = document.createElement('button');
  history.type = 'button';
  history.textContent = 'Statusverlauf';
  const historyArea = document.createElement('div');
  historyArea.setAttribute('aria-live', 'polite');
  history.addEventListener('click', () => { void run(() => loadHistory(historyArea, family.id)); });
  li.append(history, historyArea);
  return li;
}
function showChange(card, family) {
  card.querySelector('.confirmation')?.remove();
  const form = document.createElement('form');
  form.className = 'confirmation';
  const target = family.status === 'active' ? 'disabled' : 'active';
  const key = crypto.randomUUID();
  const title = document.createElement('h4');
  title.textContent = target === 'disabled' ? 'Sperrung bestätigen' : 'Wiederfreigabe bestätigen';
  const info = document.createElement('p');
  info.textContent = target === 'disabled'
    ? 'Alle Familienzugänge werden gesperrt. Bestehende Anmeldungen und MCP-Freigaben werden widerrufen. Die Familiendaten bleiben erhalten.'
    : 'Die Familie darf sich wieder neu anmelden. Alte Sitzungen und MCP-Freigaben bleiben ungültig.';
  const reasonLabel = document.createElement('label');
  reasonLabel.textContent = 'Begründung';
  const reason = document.createElement('textarea');
  reason.required = true;
  reason.maxLength = 500;
  reasonLabel.append(reason);
  const nameLabel = document.createElement('label');
  nameLabel.textContent = 'Zur Bestätigung den Familiennamen eingeben: ' + family.name;
  const name = document.createElement('input');
  name.required = true;
  name.maxLength = 100;
  name.autocomplete = 'off';
  nameLabel.append(name);
  const checkLabel = document.createElement('label');
  checkLabel.className = 'check-label';
  const check = document.createElement('input');
  check.type = 'checkbox';
  check.required = true;
  checkLabel.append(check, document.createTextNode('Ich bestätige diese Statusänderung.'));
  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.textContent = target === 'disabled' ? 'Jetzt sperren' : 'Jetzt wieder freigeben';
  const cancel = document.createElement('button');
  cancel.type = 'button';
  cancel.textContent = 'Abbrechen';
  cancel.addEventListener('click', () => form.remove());
  form.append(title, info, reasonLabel, nameLabel, checkLabel, submit, cancel);
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const body = {expected_status:family.status, status:target, family_name:name.value,
      reason:reason.value, confirmed:check.checked, request_key:key};
    void run(async () => {
      await api(`families/${family.id}/status`, {method:'POST',
        headers:{'Content-Type':'application/json','x-csrf-token':csrf || ''}, body:JSON.stringify(body)});
      await refresh();
      message('Statusänderung gespeichert und im Verlauf dokumentiert.');
    });
  });
  card.append(form);
  reason.focus();
}
async function loadHistory(area, familyId, before = null) {
  const data = await api(`families/${familyId}/history` + (before ? `?before=${before}` : ''));
  if (!before) area.replaceChildren();
  else area.querySelector('.more-history')?.remove();
  if (!data.items.length && !before) area.textContent = 'Noch keine Statusänderungen.';
  for (const entry of data.items) {
    const p = document.createElement('p');
    p.className = 'history-entry';
    const state = entry.to_status === 'disabled' ? 'Gesperrt' : 'Wieder freigegeben';
    p.textContent = `${state} · ${new Date(entry.created_at).toLocaleString('de-DE')} · ${entry.actor_email}\n${entry.reason}`;
    area.append(p);
  }
  if (data.next_before) {
    const more = document.createElement('button');
    more.type = 'button';
    more.className = 'more-history';
    more.textContent = 'Ältere Änderungen laden';
    more.addEventListener('click', () => { void run(() => loadHistory(area, familyId, data.next_before)); });
    area.append(more);
  }
}
async function refresh() {
  const session = await api('session');
  const families = await api('families');
  const capabilities = await api('capabilities');
  const jobs = await api('family-creations');
  creationCapacity = capabilities.family_creation_capacity;
  element('creation-capacity').textContent = creationCapacity > 0
    ? `${creationCapacity} freie Familienplätze verfügbar.` : 'Derzeit ist kein vorbereiteter Familienplatz frei.';
  element('show-create').disabled = creationCapacity === 0;
  element('creation-jobs').replaceChildren(...jobs.map((job) => {
    const li = document.createElement('li');
    const labels = {ready:'Eingerichtet', failed:'Fehlgeschlagen – Platz reserviert, manuell prüfen', provisioning:'In Einrichtung oder unterbrochen – nicht erneut anlegen'};
    li.textContent = `${job.family_name} · ${labels[job.status] || job.status}\n${job.parent_email} · ${job.actor_email}`;
    return li;
  }));
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
  catch (error) { message(error instanceof Error ? error.message : 'Verbindung fehlgeschlagen. Bitte aktualisieren und den Status prüfen.', true); }
  finally { busy = false; document.querySelectorAll('button').forEach((button) => { button.disabled = false; }); element('show-create').disabled = creationCapacity === 0; }
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
element('show-create').addEventListener('click', () => {
  creationKey = crypto.randomUUID();
  element('create-family-form').hidden = false;
  element('new-family-name').focus();
});
element('cancel-create').addEventListener('click', () => {
  element('create-family-form').reset();
  element('create-family-form').hidden = true;
  creationKey = null;
});
element('create-family-form').addEventListener('submit', (event) => {
  event.preventDefault();
  if (element('new-parent-password').value !== element('new-parent-password-repeat').value) {
    message('Die beiden Passwörter stimmen nicht überein.', true);
    return;
  }
  const body = {request_key:creationKey, family_name:element('new-family-name').value,
    parent_name:element('new-parent-name').value, parent_email:element('new-parent-email').value,
    password:element('new-parent-password').value, language:element('new-family-language').value,
    timezone:element('new-family-timezone').value, confirmed:element('create-confirm').checked};
  element('new-parent-password').value = '';
  element('new-parent-password-repeat').value = '';
  void run(async () => {
    const job = await api('family-creations', {method:'POST', headers:{'Content-Type':'application/json','x-csrf-token':csrf || ''},body:JSON.stringify(body)});
    element('create-family-form').reset();
    element('create-family-form').hidden = true;
    await refresh();
    message(job.status === 'ready' ? 'Familie eingerichtet. Der neue Elternzugang kann sich jetzt anmelden.'
      : 'Die Einrichtung ist nicht abgeschlossen. Den reservierten Platz manuell prüfen; nicht erneut anlegen.', job.status !== 'ready');
  });
});
element('logout').addEventListener('click', () => { void run(async () => {
  await api('logout', {method:'POST', headers:{'x-csrf-token':csrf || ''}});
  clearOverview();
  message('Abgemeldet.');
}); });
void run(async () => {
  try { await refresh(); }
  catch { clearOverview(); message('Bitte mit deinem Betreiberzugang anmelden.'); }
});
