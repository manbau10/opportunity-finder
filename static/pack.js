(() => {
  'use strict';
  const config = window.PACK_WORKSPACE;
  const $ = (selector) => document.querySelector(selector);
  let timer = null;
  let stopped = false;

  function toast(message) {
    const el = $('#toast');
    el.textContent = message; el.hidden = false;
    window.setTimeout(() => { el.hidden = true; }, 3200);
  }

  function bytes(value) {
    if (!value) return '0 KB';
    if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }

  function fileIcon(mime) {
    if ((mime || '').includes('pdf')) return 'PDF';
    if ((mime || '').includes('word')) return 'DOC';
    if ((mime || '').includes('json')) return 'JSON';
    return 'FILE';
  }

  function renderFiles(step) {
    const holder = document.querySelector(`[data-files="${step.key}"]`);
    holder.replaceChildren();
    if (!step.files.length) {
      const pending = document.createElement('p');
      pending.className = 'no-files';
      pending.textContent = step.status === 'active' ? 'Files will appear here as they are completed.' : 'No files ready yet.';
      holder.append(pending); return;
    }
    step.files.forEach((file) => {
      const row = document.createElement('div'); row.className = 'workspace-file';
      const icon = document.createElement('span'); icon.className = 'file-icon'; icon.textContent = fileIcon(file.mime_type);
      const copy = document.createElement('div'); copy.className = 'file-copy';
      const name = document.createElement('strong'); name.textContent = file.filename.split('/').pop();
      const meta = document.createElement('span'); meta.textContent = `${bytes(file.size_bytes)} · Ready to download`;
      copy.append(name, meta);
      const link = document.createElement('a'); link.className = 'btn tiny'; link.textContent = 'Download';
      link.href = `/api/packs/${encodeURIComponent(config.id)}/files/${encodeURIComponent(file.id)}`;
      row.append(icon, copy, link); holder.append(row);
    });
  }

  function render(data) {
    const progress = Math.max(0, Math.min(100, Number(data.progress) || 0));
    $('#progressBar').style.width = `${progress}%`;
    $('#progressPercent').textContent = `${progress}%`;
    $('#progressTrack').setAttribute('aria-valuenow', String(progress));
    $('#progressMessage').textContent = data.message || 'Working on your application.';
    $('#progressLabel').textContent = data.status === 'ready' ? 'Application workspace complete' :
      data.status === 'failed' ? 'Generation needs attention' :
      data.status === 'cancelled' ? 'Generation stopped' : 'Building your application workspace';

    const badge = $('#statusBadge');
    badge.className = `workspace-status status-${data.status}`;
    badge.textContent = data.status === 'working' ? 'In progress' : data.status.charAt(0).toUpperCase() + data.status.slice(1);

    data.steps.forEach((step) => {
      const card = document.querySelector(`[data-step="${step.key}"]`);
      card.className = `step-card ${step.status}`;
      card.querySelector('.step-state').textContent = {
        complete: 'Complete', active: 'In progress', waiting: 'Waiting',
        failed: 'Needs attention', cancelled: 'Stopped'
      }[step.status] || step.status;
      renderFiles(step);
    });

    $('#finishPanel').hidden = data.status !== 'ready';
    const hasError = data.status === 'failed' || data.status === 'cancelled';
    $('#errorPanel').hidden = !hasError;
    if (hasError) $('#errorText').textContent = data.error || data.message || 'This attempt stopped before every stage was completed.';
    $('#cancelBtn').hidden = data.status !== 'working';
    $('#cancelBtn').disabled = Boolean(data.cancel_requested);
    if (data.cancel_requested) $('#cancelBtn').textContent = 'Stopping…';
    $('#leaveNote').hidden = data.status !== 'working';
    if (data.updated_at) {
      const date = new Date(data.updated_at);
      $('#lastUpdated').textContent = Number.isNaN(date.getTime()) ? '' : `Updated ${date.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}`;
    }
    if (data.status !== 'working') {
      stopped = true;
      if (timer) window.clearTimeout(timer);
    }
  }

  async function poll() {
    try {
      const response = await fetch(`/api/packs/${encodeURIComponent(config.id)}`, {cache:'no-store'});
      if (!response.ok) throw new Error('Could not load this workspace.');
      render(await response.json());
    } catch (error) {
      $('#progressMessage').textContent = `${error.message} Retrying…`;
    }
    if (!stopped) timer = window.setTimeout(poll, 2500);
  }

  $('#cancelBtn').addEventListener('click', async () => {
    if (!window.confirm('Stop after the current operation? Files already completed will be kept.')) return;
    const response = await fetch(`/api/packs/${encodeURIComponent(config.id)}/cancel`, {
      method:'POST', headers:{'X-CSRF-Token':config.csrf}
    });
    const data = await response.json();
    if (!response.ok) return toast(data.error || 'Could not stop generation.');
    $('#cancelBtn').disabled = true; $('#cancelBtn').textContent = 'Stopping…';
    toast('Generation will stop after the current operation.');
  });

  $('#retryBtn').addEventListener('click', async () => {
    const button = $('#retryBtn'); button.disabled = true; button.textContent = 'Starting…';
    const response = await fetch(`/api/packs/${encodeURIComponent(config.id)}/retry`, {
      method:'POST', headers:{'X-CSRF-Token':config.csrf}
    });
    const data = await response.json();
    if (response.ok) window.location.href = data.workspace_url;
    else { button.disabled = false; button.textContent = 'Start a new attempt'; toast(data.error || 'Could not retry.'); }
  });

  poll();
})();
