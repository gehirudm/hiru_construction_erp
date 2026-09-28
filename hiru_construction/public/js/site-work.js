(() => {
  'use strict';
  const { $, state, node, api, money, dateLabel, options, showError, refresh, newExpense } = window.hiruDaily;
  let view = 'overview', generation = 0, sheet = null, equipment = null, fuelGeneration = 0, modalBusy = false;
  const work = (method, args = {}, post = false) => api('hiru_construction.site_work.' + method, args, post);
  const fuel = (method, args = {}) => api('hiru_construction.fuel.' + method, args);
  const panel = $('work-panel');
  function button(label, action, cls = 'secondary') {
    const el = node('button', label, cls); el.type = 'button'; el.addEventListener('click', action); return el;
  }
  function label(text, input) { const el = node('label', text); el.append(input); return el; }
  function heading(title, description) { panel.append(node('h2', title), node('p', description, 'muted')); }
  function modal(title) {
    $('work-dialog-title').textContent = title; $('work-dialog-body').replaceChildren();
    if (!$('work-dialog').open) $('work-dialog').showModal();
    return $('work-dialog-body');
  }
  function modalError(body, error) { body.append(node('p', error.message, 'alert error')); }
  $('close-work-dialog').addEventListener('click', () => { if (!modalBusy) $('work-dialog').close(); });
  $('work-dialog').addEventListener('cancel', event => { if (modalBusy) event.preventDefault(); });
  async function showView() {
    const token = ++generation;
    document.querySelector('.intro').hidden = view !== 'overview';
    document.querySelectorAll('[data-view]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === view)));
    $('content').hidden = view !== 'overview' || !state.overview;
    panel.hidden = view === 'overview';
    if (view === 'overview') return;
    panel.className = view === 'categories' ? '' : 'panel';
    panel.replaceChildren(node('p', 'Loading…', 'empty'));
    if (!state.project || state.overview?.project !== state.project) return;
    try {
      if (view === 'crew') {
        const date = sheet?.project === state.project ? sheet.date : state.today;
        const data = await work('crew', { project: state.project, date });
        if (token !== generation) return;
        sheet = { ...data, project: state.project }; renderCrew();
      } else if (view === 'categories') renderCategories();
      else if (view === 'meals') { await window.hiruMeals.render(panel, () => token === generation); }
      else {
        const records = await fuel('history', { project: state.project });
        if (token !== generation) return;
        renderFuel(records);
      }
    } catch (error) { if (token === generation) panel.replaceChildren(node('p', error.message, 'alert error')); }
  }
  document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => { view = b.dataset.view; showView(); }));
  document.addEventListener('hiru:project-ready', showView);

  function renderCrew() {
    panel.replaceChildren(); heading('Attendance & overtime', 'Mark the crew together. Keep a draft during the day; confirm when the day’s hours and OT are final.');
    const toolbar = node('div', undefined, 'work-toolbar');
    const date = node('input'); date.type = 'date'; date.value = sheet.date; date.max = state.today; date.id = 'crew-date';
    date.addEventListener('change', () => { sheet.date = date.value; showView(); });
    const shift = node('input'); shift.type = 'number'; shift.min = '.01'; shift.max = '24'; shift.step = '.01'; shift.value = '8'; shift.id = 'crew-shift';
    toolbar.append(label('Day', date), label('Regular hours for a full day', shift));
    const markAll = button('Mark all present', () => {
      panel.querySelectorAll('.crew-row').forEach(row => {
        const select = row.querySelector('select');
        if (!select.disabled) { select.value = 'Present'; row.querySelector('[data-regular]').value = shift.value; }
      });
    });
    markAll.disabled = !sheet.can_write; toolbar.append(markAll);
    if (sheet.can_assign) toolbar.append(button('Add workers to site', addWorkers));
    panel.append(toolbar, node('p', `Confirmed in the 7 days ending ${dateLabel(sheet.date)}: ${sheet.regular_total} regular hours · ${sheet.ot_total} OT hours`, 'work-summary'));
    if (!sheet.employees.length) panel.append(node('p', 'No workers assigned yet. Add workers to this site once, then mark their day here.', 'empty'));
    const otType = node('select'); otType.id = 'crew-ot-type';
    options(otType, sheet.overtime_types.map(name => [name, name]), 'Hours only — pay rule not selected');
    const settings = node('details', undefined, 'ot-settings');
    settings.append(node('summary', 'Overtime settings'), label('OT pay rule for new or edited marks', otType),
      node('p', 'OT hours are recorded separately. This screen does not calculate or pay wages. Half-day OT needs payroll review.', 'muted'));
    panel.append(settings);
    sheet.employees.forEach(employee => {
      const a = employee.attendance, locked = employee.conflict || a?.docstatus === 1 || !sheet.can_write;
      const row = node('div', undefined, 'crew-row'); row.dataset.employee = employee.name;
      const person = node('div'); person.append(node('strong', employee.employee_name), node('small', employee.name));
      person.append(node('small', employee.conflict ? 'Existing attendance needs review' : a?.docstatus === 1 ? 'Confirmed' : a ? 'Draft' : 'Not marked'));
      const status = node('select'); status.setAttribute('aria-label', 'Attendance for ' + employee.employee_name);
      options(status, [['Present', 'Present'], ['Half Day', 'Half day'], ['Absent', 'Absent']], 'Not marked'); status.value = a?.status || ''; status.disabled = locked;
      const regular = node('input'); regular.type = 'number'; regular.min = '0'; regular.max = '24'; regular.step = '.01'; regular.value = a?.custom_construction_regular_hours || 0; regular.dataset.regular = '';
      const ot = node('input'); ot.type = 'number'; ot.min = '0'; ot.max = '24'; ot.step = '.01'; ot.value = a?.actual_overtime_duration || 0; ot.dataset.ot = '';
      regular.disabled = ot.disabled = locked;
      status.addEventListener('change', () => {
        regular.value = status.value === 'Present' ? shift.value : status.value === 'Half Day' ? Number(shift.value) / 2 : 0;
        if (status.value === 'Absent' || !status.value) ot.value = 0;
      });
      row.append(person, label('Attendance', status), label('Regular hours', regular), label('OT hours', ot)); panel.append(row);
    });
    const actions = node('div', undefined, 'sheet-actions');
    const save = button('Save attendance draft', () => saveSheet(false)); save.disabled = !sheet.can_write;
    const review = button('Review & confirm attendance', reviewSheet, 'primary'); review.disabled = !sheet.can_write || !sheet.can_submit;
    actions.append(save, review); panel.append(actions);
  }
  function sheetRows() {
    return [...panel.querySelectorAll('.crew-row')].filter(row => row.querySelector('select').value && !row.querySelector('select').disabled).map(row => {
      const old = sheet.employees.find(e => e.name === row.dataset.employee).attendance;
      const regular = row.querySelector('[data-regular]'), ot = row.querySelector('[data-ot]');
      if (!regular.checkValidity() || !ot.checkValidity()) throw new Error('Check regular and OT hours: use values between 0 and 24.');
      return { employee: row.dataset.employee, name: old?.name, modified: old?.modified,
        status: row.querySelector('select').value, regular: regular.value, ot: ot.value,
        overtime_type: $('crew-ot-type').value || old?.overtime_type || '' };
    });
  }
  async function saveSheet(confirm, snapshot) {
    const body = modal(confirm ? 'Confirm attendance' : 'Save attendance');
    try {
      const rows = snapshot || sheetRows();
      if (!rows.length) throw new Error('Mark at least one unconfirmed worker first.');
      modalBusy = true; body.append(node('p', 'Saving the crew sheet…', 'muted'));
      const result = await work('save_attendance', { project: sheet.project, date: sheet.date, rows, confirm }, true);
      modalBusy = false; body.replaceChildren(node('p', `${result.saved} workers ${confirm ? 'confirmed' : 'saved as drafts'}.`, 'work-summary'));
      body.append(button('Done', () => $('work-dialog').close(), 'primary')); await showView();
    } catch (error) { body.replaceChildren(); modalError(body, error); }
    finally { modalBusy = false; }
  }
  function reviewSheet() {
    const body = modal('Review the crew’s day');
    try {
      const rows = sheetRows(); if (!rows.length) throw new Error('Mark at least one unconfirmed worker first.');
      const regular = rows.reduce((sum, row) => sum + Number(row.regular), 0), ot = rows.reduce((sum, row) => sum + Number(row.ot), 0);
      body.append(node('p', `${dateLabel(sheet.date)} · ${rows.length} workers · ${regular} regular hours · ${ot} OT hours`, 'work-summary'));
      rows.forEach(row => {
        const name = sheet.employees.find(e => e.name === row.employee).employee_name;
        body.append(node('p', `${name}: ${row.status}, ${row.regular} regular + ${row.ot} OT hours`, 'transaction-row'));
      });
      body.append(node('p', 'Confirmed attendance is locked. Corrections need the attendance cancellation/amendment workflow.', 'muted'));
      body.append(button('Confirm this attendance', () => saveSheet(true, rows), 'primary'));
    } catch (error) { modalError(body, error); }
  }
  async function addWorkers() {
    const body = modal('Add workers to this site'), project = state.project;
    try {
      const workers = await work('available_workers', { project });
      if (!workers.length) body.append(node('p', 'All active workers are already assigned. Create new employees in setup when needed.', 'empty'));
      workers.forEach(worker => { const input = node('input'); input.type = 'checkbox'; input.value = worker.name;
        const choice = label(worker.employee_name, input); choice.className = 'worker-choice'; body.append(choice); });
      const save = button('Add selected workers', async () => {
        save.disabled = true; modalBusy = true;
        try {
          const employees = [...body.querySelectorAll('input:checked')].map(el => el.value);
          await work('assign_workers', { project, employees }, true); $('work-dialog').close(); await showView();
        } catch (error) { modalError(body, error); }
        finally { save.disabled = false; modalBusy = false; }
      }, 'primary'); if (workers.length) body.append(save);
    } catch (error) { modalError(body, error); }
  }
  function renderCategories() {
    panel.replaceChildren(); heading('Expense categories', 'See what each part of the project costs. Open a category to see the entries behind its total.');
    const cards = node('div', undefined, 'category-cards');
    state.overview.groups.forEach(group => {
      const card = button('', () => categoryDetail(group), 'category-card');
      const category = state.overview.categories.find(c => c.category === group.id);
      card.append(node('span', category?.scope === 'Project' ? 'This project' : group.id ? 'Reusable category' : 'Needs setup', 'pill'), node('h3', group.label));
      const details = node('dl');
      [['Budget', money(group.budget)], ['Spent', money(group.spent)], ['Open orders', money(group.orders)],
        ['Budget left', group.review_receipts ? 'Review receipts' : money(group.budget - group.spent - group.orders)]].forEach(([k, v]) => {
        const row = node('div'); row.append(node('dt', k), node('dd', v)); details.append(row);
      });
      card.append(details, node('span', 'View spending →', 'inline-link')); cards.append(card);
    });
    if (!state.overview.groups.length) cards.append(node('p', 'Approve the project budget to see its categories here.', 'empty'));
    panel.append(cards);
  }
  async function categoryDetail(group) {
    const body = modal(group.label), project = state.project;
    try {
      if (!group.id) throw new Error('These expenses need a category mapping in project budget setup. They remain included in project totals.');
      const data = await work('category_detail', { project, category: group.id });
      body.append(node('p', data.description || (data.scope === 'Global' ? 'A reusable category across projects.' : 'A category defined for this project.'), 'muted'));
      body.append(node('p', `Tender ${money(data.original)} · Current budget ${money(data.budget)} · Spent ${money(data.spent)}`, 'work-summary'));
      if (!data.entries.length) body.append(node('p', 'No posted expenses in this category yet.', 'empty'));
      data.entries.forEach(entry => {
        const row = node('div', undefined, 'transaction-row'), detail = node('div');
        detail.append(node('span', entry.description || entry.voucher_type), node('small', dateLabel(entry.posting_date) + ' · ' + entry.voucher_no));
        if (entry.note) detail.append(node('small', entry.note));
        row.append(detail, node('strong', money(entry.debit - entry.credit))); body.append(row);
      });
      if (data.has_more) body.append(node('p', 'Showing the latest 50 ledger entries. All entries are included in the totals.', 'muted'));
      const category = state.overview.categories.find(c => c.category === group.id);
      if (category && state.overview.can_create) body.append(button('Add ' + group.label.toLowerCase() + ' expense', () => {
        $('work-dialog').close();
        if (category.entry_type === 'Meals') { view = 'meals'; showView(); } else newExpense(category.account);
      }, 'primary'));
    } catch (error) { modalError(body, error); }
  }
  function renderFuel(records) {
    panel.replaceChildren(); heading('Fuel & equipment', 'Fuel purchases linked to a vehicle or machine, with litres and meter readings.');
    const category = state.overview.categories.find(c => c.entry_type === 'Fuel');
    const add = button('Record fuel', () => newExpense(category.account), 'primary'); add.disabled = !category || !state.overview.can_create;
    panel.append(add);
    if (!category) panel.append(node('p', 'Add a fuel category to the approved project budget first.', 'alert'));
    if (!records.length) panel.append(node('p', 'No fuel entered through the daily screen yet. Record the next fill here.', 'empty'));
    records.forEach(record => {
      const row = node('div', undefined, 'transaction-row'), detail = node('div');
      detail.append(node('span', record.custom_construction_vehicle || record.custom_construction_machine),
        node('small', `${dateLabel(record.posting_date)} · ${record.custom_construction_litres} litres · ${record.custom_construction_meter_recorded ? record.custom_construction_meter + (record.custom_construction_vehicle ? ' km' : ' engine hours') : 'No meter reading'}`));
      row.append(detail, node('strong', money(record.grand_total))); panel.append(row);
    });
    panel.append(node('p', 'Latest 20 recorded fills. Litres purchased are not measured consumption; efficiency needs a reliable full-tank or usage history. Earlier vehicle logs remain in the fleet workspace.', 'muted'));
  }
  async function fuelFields() {
    const token = ++fuelGeneration;
    const selected = state.overview?.categories.find(c => c.account === $('category').value);
    const active = selected?.entry_type === 'Fuel'; $('fuel-fields').hidden = !active;
    ['fuel-equipment', 'fuel-litres', 'fuel-meter'].forEach(id => $(id).required = active);
    if (!active) return;
    options($('fuel-equipment'), [], 'Loading equipment…');
    try {
      equipment = await fuel('equipment', { project: state.project });
      if (token !== fuelGeneration) return;
      equipmentOptions();
    } catch (error) { if (token === fuelGeneration) showError('expense-error', error); }
  }
  function equipmentOptions() {
    if (!equipment) return;
    const vehicle = $('fuel-kind').value === 'vehicle';
    options($('fuel-equipment'), (vehicle ? equipment.vehicles : equipment.machines).map(e =>
      [e.name, vehicle ? `${e.name} · ${e.make} ${e.model}` : `${e.asset_name} · ${e.name}`]), 'Choose equipment');
    $('fuel-meter-label').textContent = vehicle ? 'Odometer (km)' : 'Engine hours (optional)';
    $('fuel-meter').required = vehicle;
  }
  $('category').addEventListener('change', fuelFields);
  document.addEventListener('hiru:expense-open', fuelFields);
  $('fuel-kind').addEventListener('change', equipmentOptions);
  $('fuel-equipment').addEventListener('change', () => {
    if (!$('description').value || $('description').value.startsWith('Fuel for ')) $('description').value = 'Fuel for ' + $('fuel-equipment').value;
  });
  const updateRate = () => { const litres = Number($('fuel-litres').value), amount = Number($('amount').value);
    $('fuel-rate').textContent = litres > 0 && amount > 0 ? money(amount / litres) + ' per litre' : 'Enter litres and the total amount from the fuel receipt.'; };
  $('fuel-litres').addEventListener('input', updateRate); $('amount').addEventListener('input', updateRate);
})();
