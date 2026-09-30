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
  function lockSelection(locked) {
    if ($('site-project')) $('site-project').disabled = locked;
    if ($('add-supervisor')) $('add-supervisor').disabled = locked || !$('site-project').value;
    $('wallet').disabled = locked || !$('wallet').options.length || $('wallet').options.length === 1;
  }
  function submit(form, text, action) {
    const b = el('button', text, 'primary'); b.type = 'submit'; form.append(b);
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (busy) return;
      busy = true; b.disabled = true; lockSelection(true);
      try { await action(); } catch (error) { message(error.message, true); }
      finally { busy = false; b.disabled = false; lockSelection(false); }
    });
  }
  async function load(preferred) {
    const token = ++generation, result = await api('bootstrap');
    if (token !== generation) return;
    boot = result;
    const selected = preferred || $('wallet').value;
    if (boot.owner) {
      const project = boot.wallets.find(w => w.name === selected)?.project || $('site-project').value;
      options($('site-project'), boot.projects.map(p => [p.name, p.project_name + (p.status === 'Open' ? '' : ` (${p.status})`)]), 'Choose a project');
      $('site-project').value = boot.projects.some(p => p.name === project) ? project : boot.projects.find(p => p.status === 'Open')?.name || boot.projects[0]?.name || '';
    }
    chooseWallet(selected);
    await refresh();
  }
  function chooseWallet(preferred) {
    const wallets = boot.owner ? boot.wallets.filter(w => w.project === $('site-project').value) : boot.wallets;
    options($('wallet'), wallets.map(w => [w.name, `${boot.owner ? '' : w.project_name + ' · '}${w.supervisor_name}${w.enabled ? '' : ' (disabled)'}`]), wallets.length ? 'Choose a supervisor' : 'No supervisors assigned yet');
    $('wallet').value = wallets.some(w => w.name === preferred) ? preferred : wallets[0]?.name || '';
    lockSelection(busy);
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
    if (!data) {
      if (boot.owner) {
        const project = boot.projects.find(p => p.name === $('site-project').value);
        panel.append(el('h2', project?.project_name || 'Your sites'));
        if (project?.status === 'Open') {
          const assigned = boot.wallets.some(w => w.project === project.name);
          panel.append(el('p', assigned ? 'Choose a supervisor above to see their spending and site money, or add another supervisor.' : 'No supervisor has been assigned to this site yet. Add someone new or give an existing supervisor access.'));
          panel.append(button('Add a supervisor to this site', openAccess, 'primary'));
        } else panel.append(el('p', project ? 'This project is closed. Choose an open project to add a supervisor.' : 'Create a project first, then add a supervisor here.'));
        const link = el('a', 'Open project setup'); link.href = '/desk/project'; const help = el('p'); help.append(link); panel.append(help);
      } else panel.append(el('p', 'The owner has not assigned an active project yet.'));
      return;
    }
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
  async function run(action) { if (busy) return; busy = true; lockSelection(true); try { await action(); } catch (error) { message(error.message, true); } finally { busy = false; lockSelection(false); } }
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
    const f = form('Add a supervisor');
    f.append(el('p', 'Choose the site and person below. They can submit attendance, OT and expenses; changes still need your permission.', 'access-note wide'));
    const project = field(f, 'project', 'Give access to this site', 'select'); options(project, boot.projects.filter(p => p.status === 'Open').map(p => [p.name, p.project_name])); project.value = $('site-project').value;
    const mode = field(f, 'mode', 'Who needs access?', 'select'); options(mode, [['new', 'New supervisor — create a login'], ['existing', 'Existing supervisor']]); mode.value = 'new';
    const person = el('div', undefined, 'team-form wide'); f.append(person);
    let name, email, password, supervisor;
    const drawPerson = () => {
      person.replaceChildren();
      if (mode.value === 'new') {
        name = field(person, 'full_name', 'Supervisor name'); name.maxLength = 140;
        email = field(person, 'email', 'Email / login', 'email'); email.autocomplete = 'off';
        password = field(person, 'password', 'Initial password (12+ characters)', 'password'); password.minLength = 12; password.autocomplete = 'new-password';
        person.append(el('p', 'Share this login and password privately with the supervisor. No email is sent.', 'muted wide'));
      } else {
        supervisor = field(person, 'supervisor', 'Supervisor', 'select'); options(supervisor, boot.supervisors.map(u => [u.name, `${u.full_name} (${u.name})`]));
        person.append(el('p', 'Their existing password stays the same. Giving access again restores a disabled assignment.', 'muted wide'));
      }
    }; mode.addEventListener('change', drawPerson); drawPerson();
    submit(f, 'Give site access', async () => {
      const args = mode.value === 'new' ? { email: email.value, full_name: name.value, password: password.value } : { supervisor: supervisor.value };
      const result = await api('add_supervisor', { project: project.value, ...args }, true);
      if (password) password.value = '';
      tab = 'history'; await load(result.wallet);
      message(`Access is ready for ${result.user}. They can sign in at ${location.origin}/site-work. You can now record money given to them.`);
    });
    panel.append(el('h2', 'Who has access to this site?'));
    const assignments = boot.wallets.filter(w => w.project === $('site-project').value);
    if (!assignments.length) panel.append(el('p', 'No supervisors assigned yet.', 'muted'));
    assignments.forEach(w => {
      const row = el('div', undefined, 'work-toolbar'); row.append(el('span', `${w.project_name} · ${w.supervisor_name} · ${w.enabled ? 'Enabled' : 'Disabled'}`));
      row.append(button(w.enabled ? 'Disable access' : 'Enable access', () => run(async () => { await api('set_enabled', { wallet: w.name, enabled: w.enabled ? 0 : 1 }, true); await load(); message('Assignment updated.'); }))); panel.append(row);
    });
    const owners = el('details', undefined, 'owner-login'); owners.append(el('summary', 'Add another owner login'));
    const ownerForm = el('form', undefined, 'team-form'); owners.append(ownerForm); panel.append(owners);
    ownerForm.append(el('p', 'Owners have full business and administration access.', 'muted wide'));
    const ownerName = field(ownerForm, 'owner_name', 'Owner name'), ownerEmail = field(ownerForm, 'owner_email', 'Owner email / login', 'email');
    const ownerPassword = field(ownerForm, 'owner_password', 'Owner initial password (12+ characters)', 'password'); ownerPassword.minLength = 12; ownerPassword.autocomplete = 'new-password';
    submit(ownerForm, 'Create owner login', async () => { await api('create_user', { email: ownerEmail.value, full_name: ownerName.value, password: ownerPassword.value, access: 'Owner' }, true); ownerForm.reset(); message('Owner login created. Share the password privately.'); });
  }
  function openAccess() { if (!busy && boot) { tab = 'access'; correction = null; render(); panel.scrollIntoView({ block: 'start', behavior: 'instant' }); } }
  document.querySelectorAll('[data-tab]').forEach(b => {
    b.disabled = true;
    b.addEventListener('click', () => { if (!busy && boot) { tab = b.dataset.tab; correction = null; render(); } });
  });
  $('wallet').addEventListener('change', () => { correction = null; refresh().catch(e => message(e.message, true)); });
  if ($('site-project')) $('site-project').addEventListener('change', () => { correction = null; chooseWallet(); refresh().catch(e => message(e.message, true)); });
  if ($('add-supervisor')) $('add-supervisor').addEventListener('click', openAccess);
  $('sign-out').onclick = () => run(async () => { await api('logout', {}, true); location.href = '/login'; });
  load().catch(error => message(error.message, true));
})();
