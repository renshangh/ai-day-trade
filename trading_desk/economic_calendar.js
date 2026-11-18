/* Schedule only: elapsed release times never imply actual results were fetched. */
(() => {
  const box = document.getElementById('economic-calendar-content');
  const button = document.getElementById('economic-refresh');
  if (!box || !button) return;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const date = value => new Intl.DateTimeFormat('en-US', {timeZone:'America/New_York', month:'short',day:'numeric',weekday:'short'}).format(new Date(value + 'T12:00:00-05:00'));
  const time = value => value ? new Intl.DateTimeFormat('en-US', {timeZone:'America/New_York',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(value)) : 'Time not published';
  let busy = false;
  async function load(force = false) {
    if (busy) return;
    busy = true; button.disabled = true;
    try {
      const response = await fetch('/api/economic-calendar' + (force ? '?force=1' : ''), {cache:'no-store'});
      if (!response.ok) throw new Error('Calendar refresh failed');
      const data = await response.json();
      const sources = data.sources.map(s => `<li>${esc(s.agency)}: ${esc(s.status)}${s.via ? ` · via ${esc(s.via)}` : ''}${s.last_verified ? ` · last verified ${esc(s.last_verified)}` : ''} · <a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Official schedule ↗</a></li>`).join('');
      const rows = data.events.map(e => `<tr><td>${e.date === data.day ? '<b>Today</b> · ' : ''}${esc(date(e.date))}</td><td>${esc(time(e.at))}</td><td><a href="${esc(e.source)}" target="_blank" rel="noopener noreferrer">${esc(e.title)}</a></td><td>${esc(e.agency)}</td><td>${esc(e.status)}${e.stale ? ' · STALE verification' : ''}${e.verified_date ? ` · verified ${esc(e.verified_date)}` : ''}</td></tr>`).join('');
      box.innerHTML = `<p>${data.partial ? '<b>Partial coverage — some sources could not refresh.</b> ' : ''}Last check: ${esc(new Date(data.checked_at).toLocaleString('en-US', {timeZone:'America/New_York'}))} ET.</p><div style="overflow-x:auto"><table><thead><tr><th>Date</th><th>Release time</th><th>Release</th><th>Source</th><th>Status</th></tr></thead><tbody>${rows || '<tr><td colspan="5">No verified events available in this window; this does not establish that no releases are scheduled.</td></tr>'}</tbody></table></div><p class="muted">${esc(data.coverage)}</p><details><summary>Source freshness and coverage</summary><ul>${sources}</ul></details>`;
    } catch (_) {
      box.textContent = 'Economic schedule unavailable. Refresh failed; no dates or times inferred. Try Refresh schedule.';
    } finally { busy = false; button.disabled = false; }
  }
  button.addEventListener('click', () => void load(true));
  document.addEventListener('visibilitychange', () => { if (!document.hidden) void load(); });
  // Re-evaluates Eastern date, even if the page stays open across midnight.
  setInterval(() => { if (!document.hidden) void load(); }, 60_000);
  void load();
})();
