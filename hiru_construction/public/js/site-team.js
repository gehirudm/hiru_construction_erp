(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
  let boot, data, tab = 'history', generation = 0, busy = false, correction = null;
  const panel = $('team-content');
  const amount = value => new Intl.NumberFormat('en-LK', { style: 'currency', currency: data?.currency || 'LKR' }).format(value);
  function message(text, error = false) { $('message').textContent = text; $('message').hidden = false; $('message').className = error ? 'error' : ''; }
  async function api(method, args = {}, post = false) {
    const url = new URL('/api/method/' + (method === 'logout' || method.includes('.') ? method : 'hiru_construction.site_team.' + method), location.origin);
    const init = { credentials: 'same-origin', headers: { 'X-Frappe-CSRF-Token': document.querySelector('meta[name=csrf-token]').content } };
    if (post) { init.method = 'POST'; init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(args); }
    else Object.entries(args).forEach(([key, value]) => url.searchParams.set(key, value));
    const response = await fetch(url, init), result = await response.json();
    if (!response.ok || result.exc) {
      let text = 'Unable to save. Check your connection and retry.';
      try { text = JSON.parse(JSON.parse(result._server_messages)[0]).message; } catch (_) { /* fallback */ }
      throw new Error(new DOMParser().parseFromString(text, 'text/html').body.textContent);
    }
    return result.message;
  }
  function options(select, rows, placeholder = 'Choose…') {
    select.replaceChildren(); const empty = el('option', placeholder); empty.value = ''; select.append(empty);
    rows.forEach(([value, label]) => { const option = el('option', label); option.value = value; select.append(option); });
  }
  function field(form, name, title, type = 'text', value = '', required = true) {
    const input = el(type === 'select' ? 'select' : type === 'textarea' ? 'textarea' : 'input');
    if (input.tagName === 'INPUT') input.type = type;
    input.name = name; input.value = value ?? ''; input.required = required;
    if (type === 'number') { input.step = '.01'; input.min = '0'; }
    if (type === 'date') input.max = boot.today;
    const label = el('label', title); label.append(input); form.append(label); return input;
  }
  function button(text, action, cls = 'secondary') {
    const b = el('button', text, cls); b.type = 'button'; b.addEventListener('click', action); return b;
  }
  function form(title) { panel.append(el('h2', title)); const f = el('form', undefined, 'team-form'); panel.append(f); return f; }
  function submit(form, text, action) {
    const b = el('button', text, 'primary'); b.type = 'submit'; form.append(b);
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (busy) return;
      busy = true; b.disabled = true; $('wallet').disabled = true;
      try { await action(); } catch (error) { message(error.message, true); }
      finally { busy = false; b.disabled = false; $('wallet').disabled = false; }
    });
  }
  async function load(preferred) {
    const token = ++generation; boot = await api('bootstrap');
    if (token !== generation) return;
    const selected = preferred || $('wallet').value;
    options($('wallet'), boot.wallets.map(w => [w.name, `${w.project_name} · ${w.supervisor_name}${w.enabled ? '' : ' (disabled)'}`]), 'Choose a site');
    $('wallet').value = boot.wallets.some(w => w.name === selected) ? selected : boot.wallets[0]?.name || '';
    await refresh();
  }
  async function refresh() {
    const token = ++generation, wallet = $('wallet').value;
    data = null;
    $('balances').replaceChildren(); panel.replaceChildren(el('p', 'Loading…'));
    document.querySelectorAll('[data-tab]').forEach(b => { b.disabled = true; });
    let result;
    try { result = wallet ? await api('details', { wallet }) : null; }
    catch (error) {
      if (token === generation) { render(); message(error.message, true); }
      return;
    }
    if (token !== generation) return;
    data = result;
    render();
  }
  function render() {
    document.querySelectorAll('[data-tab]').forEach(b => { b.disabled = false; b.setAttribute('aria-pressed', String(b.dataset.tab === tab)); });
    $('balances').replaceChildren(); panel.replaceChildren();
    if (data) {
      for (const [label, value, note] of [
        ['Balance after reported spending', data.reported, data.reported < 0 ? 'Negative: money owed back to the supervisor.' : 'Money still held for the site.'],
        ['Spending awaiting approval', data.pending, 'Included in the reported balance; not yet in project accounts.'],
        ['Approved cash balance', data.posted, 'Money received minus approved spending and money returned.']]) {
        const card = el('article'); card.append(el('span', label), el('strong', amount(value), value < 0 ? 'red' : ''), el('small', note)); $('balances').append(card);
      }
    }
    if (tab === 'access' && boot.owner) return access();
    if (!data) { panel.append(el('p', boot.owner ? 'Create a supervisor and assign a project in People & access.' : 'The owner has not assigned an active project yet.')); return; }
    if (!data.enabled) panel.append(el('p', 'This assignment is disabled. History remains available to the owner.', 'alert'));
    if (tab === 'expense') expenseForm();
    else if (tab === 'attendance') attendanceForm();
    else if (tab === 'money' && boot.owner) moneyForm();
    else history();
  }
  function history() {
    panel.append(el('h2', 'History & review'), el('p', 'Submitted records stay locked. A correction preserves the original until the owner approves its replacement.', 'muted'));
    const filter = el('select'); filter.setAttribute('aria-label', 'Filter history'); options(filter, [['Pending', 'Awaiting approval'], ['Requested', 'Correction requests'], ['Expense', 'Expenses'], ['Attendance', 'Attendance'], ['Funding', 'Money given'], ['Return', 'Money returned']], 'All history'); panel.append(filter);
    const list = el('div'); panel.append(list);
    const draw = () => {
      list.replaceChildren();
      const rows = data.records.filter(r => !filter.value || r.kind === filter.value || r.state === filter.value || r.correction_state === filter.value);
      if (!rows.length) list.append(el('p', 'No entries to show.', 'empty'));
      rows.forEach(row => {
        const card = el('article', undefined, 'team-record'); card.dataset.entry = row.name;
        const title = { Funding: 'Money given', Return: 'Money returned' }[row.kind] || row.kind;
        card.append(el('h3', `${title} · ${row.entry_date} · ${row.state}`), el('p', row.description));
        if (row.kind === 'Expense') {
          const category = data.categories.find(c => c.value === JSON.parse(row.payload).category);
          if (category) card.append(el('p', category.label, 'muted'));
        }
        if (row.kind !== 'Attendance') card.append(el('strong', amount(row.amount)));
        const detail = el('details'); detail.append(el('summary', 'Details and audit trail'));
        const dl = el('dl');
        const values = { Reference: row.name, 'Entered by': row.owner, 'Reviewed by': row.reviewed_by,
          'Review note': row.review_reason, 'Corrects entry': row.revision_of, 'Correction permission': row.correction_state,
          'Correction reason': row.correction_reason, 'Permission granted by': row.granted_by, ...JSON.parse(row.payload) };
        Object.entries(values).forEach(([key, value]) => { if (value !== '' && value != null) dl.append(el('dt', key.replaceAll('_', ' ')), el('dd', String(value))); });
        detail.append(dl); card.append(detail);
        if (row.revision_of && row.state === 'Pending') card.append(el('p', 'Correction awaiting approval. The original still determines the balance.', 'muted'));
        if (boot.owner && row.voucher) { const link = el('a', 'Open accounting / attendance record'); link.href = '/desk/' + encodeURIComponent(row.voucher_type.toLowerCase().replaceAll(' ', '-')) + '/' + encodeURIComponent(row.voucher); link.target = '_blank'; link.rel = 'noopener'; card.append(link); }
        const actions = el('div', undefined, 'work-toolbar');
        if (boot.owner && row.state === 'Pending') {
          actions.append(button('Approve', () => explain('Approve this submission', explanation => api('review', { name: row.name, decision: 'Approve', explanation }, true)), 'primary'));
          actions.append(button('Reject', () => explain('Reject this submission', explanation => api('review', { name: row.name, decision: 'Reject', explanation }, true))));
        }
        if (boot.owner && row.correction_state === 'Requested' && ['Pending', 'Approved'].includes(row.state)) {
          actions.append(button('Allow one correction', async () => run(async () => { await api('grant_correction', { name: row.name }, true); await refresh(); message('One correction allowed for this entry.'); })));
        }
        if (boot.owner && ['Requested', 'Granted'].includes(row.correction_state)) actions.append(button('Decline / revoke correction', () => explain('Decline or revoke correction permission', explanation => api('decline_correction', { name: row.name, explanation }, true))));
        if (boot.owner && ['Expense', 'Attendance'].includes(row.kind) && row.state === 'Approved') actions.append(button('Void approved entry', () => explain('Void this approved entry', explanation => api('void_entry', { name: row.name, explanation }, true))));
        if (['Expense', 'Attendance'].includes(row.kind) && ['Pending', 'Approved'].includes(row.state)) {
          if (!row.correction_state && !(row.revision_of && row.state === 'Pending')) actions.append(button('Request correction', () => explain('Explain the correction needed', explanation => api('request_correction', { name: row.name, explanation }, true))));
          if (row.correction_state === 'Granted') actions.append(button('Enter correction', () => { correction = row; tab = row.kind === 'Expense' ? 'expense' : 'attendance'; render(); }));
        }
        if (boot.owner && ['Funding', 'Return'].includes(row.kind) && row.state === 'Approved') actions.append(button('Reverse transfer', () => explain('Reverse this money transfer', explanation => api('reverse_transfer', { name: row.name, explanation }, true))));
        card.append(actions); list.append(card);
      });
    }; filter.addEventListener('change', draw); draw();
  }
  async function run(action) { if (busy) return; busy = true; try { await action(); } catch (error) { message(error.message, true); } finally { busy = false; } }
  function explain(title, action) {
    $('action-title').textContent = title; $('action-reason').value = ''; $('action-dialog').showModal();
    $('action-form').onsubmit = async event => {
      event.preventDefault(); await run(async () => { await action($('action-reason').value); $('action-dialog').close(); await refresh(); message('Saved.'); });
    };
  }
  $('action-cancel').onclick = () => { if (!busy) $('action-dialog').close(); };
  $('action-dialog').addEventListener('cancel', event => { if (busy) event.preventDefault(); });
  function expenseForm() {
    const old = correction?.kind === 'Expense' ? correction : null, values = old ? JSON.parse(old.payload) : {};
    const f = form(old ? 'Correct an expense' : 'Record site spending');
    f.append(el('p', 'Record money actually spent, including your own money if the site balance runs out. Saving submits a locked record for owner approval.', 'muted wide'));
    const inputs = {};
    inputs.date = field(f, 'date', 'Date', 'date', values.date || boot.today);
    inputs.category = field(f, 'category', 'Expense category', 'select'); options(inputs.category, data.categories.map(c => [c.value, c.label])); inputs.category.value = values.category || '';
    inputs.supplier = field(f, 'supplier', 'Supplier / shop', 'select'); options(inputs.supplier, data.suppliers.map(s => [s.name, s.supplier_name])); inputs.supplier.value = values.supplier || '';
    inputs.amount = field(f, 'amount', `Amount (${data.currency})`, 'number', values.amount); inputs.amount.min = '.01';
    inputs.description = field(f, 'description', 'What was bought / paid for?', 'textarea', values.description); inputs.description.maxLength = 500;
    inputs.bill_no = field(f, 'bill_no', 'Receipt number (optional)', 'text', values.bill_no, false); inputs.bill_no.maxLength = 140;
    const extras = el('div', undefined, 'team-form wide'); f.append(extras);
    function extraFields() {
      extras.replaceChildren(); for (const k of ['vehicle', 'machine', 'litres', 'meter', 'meal']) delete inputs[k];
      const type = data.categories.find(c => c.value === inputs.category.value)?.entry_type;
      if (type === 'Fuel') {
        inputs.vehicle = field(extras, 'vehicle', 'Vehicle (or select a machine)', 'select', '', false); options(inputs.vehicle, data.vehicles.map(v => [v.name, v.name]), 'No vehicle'); inputs.vehicle.value = values.vehicle || '';
        inputs.machine = field(extras, 'machine', 'Machine (or select a vehicle)', 'select', '', false); options(inputs.machine, data.machines.map(v => [v.name, v.asset_name]), 'No machine'); inputs.machine.value = values.machine || '';
        inputs.litres = field(extras, 'litres', 'Litres', 'number', values.litres); inputs.litres.step = '.001'; inputs.litres.min = '.001';
        inputs.meter = field(extras, 'meter', 'Odometer / engine hours', 'number', values.meter, false); inputs.meter.step = '.001';
      } else if (type === 'Meals') {
        inputs.meal = field(extras, 'meal', 'Meal for this day', 'select'); options(inputs.meal, data.meals.filter(m => m.meal_date === inputs.date.value).map(m => [m.name, m.meal_label])); inputs.meal.value = values.meal || '';
        extras.append(el('p', 'If the meal is missing, ask the owner to set it up with the diner count first.', 'muted'));
      }
    }
    inputs.category.addEventListener('change', extraFields); inputs.date.addEventListener('change', extraFields); extraFields();
    const key = crypto.randomUUID();
    submit(f, old ? 'Submit correction' : 'Submit expense', async () => {
      const payload = Object.fromEntries(Object.entries(inputs).map(([key, input]) => [key, input.value]));
      await api('submit_entry', { wallet: data.wallet, kind: 'Expense', payload, request_key: key, revision_of: old?.name }, true);
      correction = null; tab = 'history'; await refresh(); message('Expense submitted and locked. The owner will review it.');
    });
  }
  function attendanceForm() {
    const old = correction?.kind === 'Attendance' ? correction : null, values = old ? JSON.parse(old.payload) : {};
    const f = form(old ? 'Correct attendance' : 'Attendance & overtime');
    const date = field(f, 'date', 'Day', 'date', values.date || boot.today); date.disabled = !!old;
    const crew = el('div', undefined, 'wide'); f.append(crew);
    let marks = [];
    const draw = () => {
      crew.replaceChildren(); marks = [];
      data.workers.filter(w => !old || w.name === values.employee).forEach(w => {
        const existing = data.records.find(r => r.kind === 'Attendance' && r.entry_date === date.value && ['Pending', 'Approved'].includes(r.state) && JSON.parse(r.payload).employee === w.name);
        const card = el('section', undefined, 'team-crew'); card.append(el('h3', w.employee_name)); crew.append(card);
        if (existing && !old) { card.append(el('p', `Already submitted (${existing.state}). Request a correction from History.`)); return; }
        const checkLabel = el('label', undefined, 'team-check'), check = el('input'); check.type = 'checkbox'; check.checked = !!old; check.disabled = !!old; checkLabel.append(check, el('span', 'Include this worker')); card.append(checkLabel);
        const fields = el('div', undefined, 'team-form'); card.append(fields);
        const status = field(fields, 'status', 'Status', 'select'); options(status, ['Present', 'Absent', 'Half Day'].map(s => [s, s])); status.value = values.status || 'Present';
        const regular = field(fields, 'regular', 'Regular hours', 'number', values.regular ?? 8), ot = field(fields, 'ot', 'OT hours', 'number', values.ot ?? 0); regular.max = ot.max = '24';
        status.addEventListener('change', () => { regular.value = status.value === 'Absent' ? 0 : status.value === 'Half Day' ? 4 : 8; if (status.value === 'Absent') ot.value = 0; });
        marks.push({ employee: w.name, check, status, regular, ot, request_key: crypto.randomUUID() });
      });
      if (!data.workers.length) crew.append(el('p', 'Ask the owner to assign workers to this project.'));
    }; date.addEventListener('change', draw); draw();
    f.append(el('p', 'Check the selected workers before submitting. Entries lock immediately and become confirmed attendance after owner approval.', 'muted wide'));
    submit(f, old ? 'Submit attendance correction' : 'Submit selected attendance', async () => {
      const rows = marks.filter(m => m.check.checked).map(m => ({ employee: m.employee, status: m.status.value, regular: m.regular.value, ot: m.ot.value, request_key: m.request_key }));
      if (!rows.length) throw new Error('Select at least one worker.');
      if (old) await api('submit_entry', { wallet: data.wallet, kind: 'Attendance', payload: { ...rows[0], date: date.value }, request_key: rows[0].request_key, revision_of: old.name }, true);
      else await api('submit_crew', { wallet: data.wallet, date: date.value, rows }, true);
      correction = null; tab = 'history'; await refresh(); message('Attendance submitted and locked.');
    });
  }
  function moneyForm() {
    const f = form('Money given / returned');
    f.append(el('p', 'Record money already handed over or returned. This records a transfer between company accounts; it does not send money or add an expense.', 'muted wide'));
    const kind = field(f, 'kind', 'Movement', 'select'); options(kind, [['Funding', 'Money given to supervisor / reimbursement'], ['Return', 'Money returned by supervisor']]);
    const value = field(f, 'amount', `Amount (${data.currency})`, 'number'); value.min = '.01';
    const date = field(f, 'date', 'Date', 'date', boot.today);
    const account = field(f, 'account', 'Company cash / bank account', 'select'); options(account, data.cash_accounts.map(a => [a.name, a.account_name]));
    const explanation = field(f, 'explanation', 'Note / reference', 'textarea'); explanation.maxLength = 500;
    const key = crypto.randomUUID();
    submit(f, 'Record money transfer', async () => {
      await api('transfer', { wallet: data.wallet, kind: kind.value, amount: value.value, date: date.value, account: account.value, explanation: explanation.value, request_key: key }, true);
      tab = 'history'; await refresh(); message('Money transfer recorded.');
    });
  }
  function access() {
    const f = form('Create a login');
    f.append(el('p', 'Owner accounts have business and administration access. Supervisors only see assigned sites. Share the initial password privately; no email is sent.', 'muted wide'));
    const name = field(f, 'full_name', 'Name'), email = field(f, 'email', 'Email / login', 'email');
    const password = field(f, 'password', 'Initial password (12+ characters)', 'password'); password.minLength = 12; password.autocomplete = 'new-password';
    const access = field(f, 'access', 'Access level', 'select'); options(access, [['Supervisor', 'Supervisor'], ['Owner', 'Owner — full access']]); access.value = 'Supervisor';
    submit(f, 'Create login', async () => { await api('create_user', { email: email.value, full_name: name.value, password: password.value, access: access.value }, true); password.value = ''; await load(); message('Login created. Assign a supervisor to a project below.'); });
    const assign = form('Assign a supervisor to a project');
    const project = field(assign, 'project', 'Project', 'select'); options(project, boot.projects.map(p => [p.name, p.project_name]));
    const supervisor = field(assign, 'supervisor', 'Supervisor', 'select'); options(supervisor, boot.supervisors.map(u => [u.name, u.full_name]));
    submit(assign, 'Assign project', async () => { const result = await api('assign', { project: project.value, supervisor: supervisor.value }, true); await load(result.wallet); message('Project assigned with a separate site-money balance.'); });
    panel.append(el('h2', 'Current assignments'));
    boot.wallets.forEach(w => {
      const row = el('div', undefined, 'work-toolbar'); row.append(el('span', `${w.project_name} · ${w.supervisor_name} · ${w.enabled ? 'Enabled' : 'Disabled'}`));
      row.append(button(w.enabled ? 'Disable access' : 'Enable access', () => run(async () => { await api('set_enabled', { wallet: w.name, enabled: w.enabled ? 0 : 1 }, true); await load(); message('Assignment updated.'); }))); panel.append(row);
    });
  }
  document.querySelectorAll('[data-tab]').forEach(b => {
    b.disabled = true;
    b.addEventListener('click', () => { if (!busy && boot) { tab = b.dataset.tab; correction = null; render(); } });
  });
  $('wallet').addEventListener('change', () => { correction = null; refresh().catch(e => message(e.message, true)); });
  $('sign-out').onclick = () => run(async () => { await api('logout', {}, true); location.href = '/login'; });
  load().catch(error => message(error.message, true));
})();
