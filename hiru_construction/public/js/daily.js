(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const state = { overview: null, project: null, generation: 0, today: null, requestId: null,
    snapshot: null, receipt: null, expense: null, uploadPending: false, busy: false, supplierGeneration: 0 };
  const node = (tag, text, cls) => {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  };
  const money = (value, currency = state.overview?.currency || 'LKR') =>
    new Intl.NumberFormat('en-LK', { style: 'currency', currency, maximumFractionDigits: 2 }).format(value);
  const dateLabel = value => new Date(String(value).slice(0, 10) + 'T12:00:00')
    .toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  function errorText(data) {
    let text = data.message || 'The request could not be completed. Please retry.';
    try { text = JSON.parse(JSON.parse(data._server_messages)[0]).message || text; } catch (_) { /* no server message */ }
    return new DOMParser().parseFromString(String(text), 'text/html').body.textContent;
  }
  async function api(method, args = {}, post = false) {
    const url = new URL('/api/method/hiru_construction.daily.' + method, location.origin);
    const init = { credentials: 'same-origin', headers: { 'X-Frappe-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content } };
    if (post) {
      init.method = 'POST'; init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(args);
    } else Object.entries(args).forEach(([key, value]) => url.searchParams.set(key, value));
    const response = await fetch(url, init);
    let data;
    try { data = await response.json(); } catch (_) { throw new Error('The connection was interrupted. Retry this action.'); }
    if (!response.ok || data.exc) {
      const error = new Error(errorText(data)); error.status = response.status; throw error;
    }
    return data.message;
  }
  function showError(id, error) { $(id).textContent = error.message || String(error); $(id).hidden = false; }
  function options(select, rows, placeholder) {
    select.replaceChildren();
    if (placeholder) { const option = node('option', placeholder); option.value = ''; select.append(option); }
    rows.forEach(([value, label]) => { const option = node('option', label); option.value = value; select.append(option); });
  }
  async function refresh() {
    if (!state.project) return;
    const generation = ++state.generation;
    $('page-error').hidden = true; $('content').hidden = true; $('loading').hidden = false;
    $('loading').textContent = 'Updating project overview…'; $('new-expense').disabled = true;
    try {
      const data = await api('overview', { project: state.project });
      if (generation !== state.generation) return;
      state.overview = data;
      $('project-title').textContent = data.title;
      ['budget', 'spent', 'orders', 'remaining'].forEach(key => {
        $(key).textContent = !data.has_budget ? 'Not set up' : data[key] === null ? 'Review receipts' : money(data[key]);
      });
      $('remaining').parentElement.classList.toggle('over-budget', data.has_budget && data.remaining !== null && data.remaining < 0);
      $('budget-warning').hidden = data.has_budget;
      $('budget-warning').textContent = 'This project needs an approved budget and expense categories before daily expenses can be recorded. Set these up in the advanced workspace.';
      $('new-expense').disabled = !data.can_create || !data.categories.length;
      $('categories').replaceChildren();
      if (!data.groups.length) $('categories').append(node('p', 'Your cost categories will appear here once the project budget is approved.', 'empty'));
      for (const group of data.groups) {
        const row = node('div', undefined, 'category-row');
        const heading = node('div', undefined, 'category-title');
        heading.append(node('span', group.label), node('span', money(group.budget) + ' budget'));
        const track = node('div', undefined, 'track'); track.setAttribute('aria-hidden', 'true');
        const scale = Math.max(group.budget, group.spent + group.orders, 1);
        for (const [amount, cls] of [[group.spent, 'actual'], [group.orders, 'orders']]) {
          const segment = node('span', undefined, cls); segment.style.width = Math.max(0, amount / scale * 100) + '%'; track.append(segment);
        }
        const values = node('div', undefined, 'category-values');
        values.append(node('span', money(group.spent) + ' recorded'), node('span', money(group.orders) + ' in open orders'));
        row.append(heading, track, values);
        if (group.review_receipts) row.append(node('p', 'Received purchases need checking before the remaining budget can be calculated.', 'muted'));
        else if (group.spent + group.orders > group.budget) row.append(node('p', money(group.spent + group.orders - group.budget) + ' over budget', 'red muted'));
        $('categories').append(row);
      }
      $('cost-detail').href = '/desk/query-report/Construction%20Project%20Costs?project=' + encodeURIComponent(state.project);
      const completed = data.tasks.filter(task => task.status === 'Completed').length;
      $('task-count').textContent = completed + ' of ' + data.tasks.length + ' work items completed';
      $('tasks').replaceChildren();
      const active = data.tasks.filter(task => task.status !== 'Completed').slice(0, 5);
      if (!active.length) $('tasks').append(node('p', data.tasks.length ? 'All listed work items are complete.' : 'No work items have been planned yet.', 'empty'));
      active.forEach(task => {
        const row = node('div', undefined, 'task-row'), detail = node('div');
        detail.append(node('strong', task.subject), node('small', task.exp_end_date ? 'Due ' + dateLabel(task.exp_end_date) : 'No end date set'));
        row.append(detail, node('span', task.status, 'pill')); $('tasks').append(row);
      });
      $('recent').replaceChildren();
      if (!data.recent.length) $('recent').append(node('p', 'No expenses entered here yet. Record your first expense when you’re ready.', 'empty'));
      data.recent.forEach(expense => {
        const row = node('button', undefined, 'expense-row'); row.type = 'button';
        const detail = node('span'); detail.append(node('strong', expense.supplier_name), node('small', dateLabel(expense.posting_date) + ' · ' + expense.name));
        row.append(detail, node('span', expense.docstatus === 1 ? 'Recorded' : 'Draft', 'pill ' + (expense.docstatus ? '' : 'draft')),
          node('span', money(expense.grand_total, expense.currency), 'amount'));
        row.addEventListener('click', () => openReview(expense.name)); $('recent').append(row);
      });
      $('content').hidden = false;
    } catch (error) { if (generation === state.generation) showError('page-error', error); }
    finally { if (generation === state.generation) $('loading').hidden = true; }
  }
  async function loadSuppliers(search = '', selected = '') {
    const generation = ++state.supplierGeneration;
    const rows = await api('suppliers', { search });
    if (generation !== state.supplierGeneration) return;
    options($('supplier'), rows.map(row => [row.name, row.supplier_name]), rows.length ? 'Choose supplier' : 'No suppliers found');
    if (selected) $('supplier').value = selected;
  }
  function setBusy(busy) {
    state.busy = busy;
    ['save-draft', 'post-expense', 'close-expense', 'cancel-entry', 'finish-review', 'retry-upload'].forEach(id => $(id).disabled = busy);
    if (!busy) $('post-expense').disabled = state.uploadPending || !state.expense?.can_submit;
  }
  function closeExpense() {
    if (state.busy) return;
    if (state.snapshot && !state.expense && !confirm('Saving has not been confirmed. Closing now may leave a saved draft. Check recent expenses before entering it again. Close?')) return;
    $('expense-dialog').close(); refresh();
  }
  async function newExpense() {
    state.requestId = crypto.randomUUID(); state.snapshot = null; state.receipt = null; state.expense = null; state.uploadPending = false;
    $('expense-form').reset(); $('expense-form').querySelectorAll('input, select, button').forEach(el => el.disabled = false);
    $('expense-form').hidden = false; $('review').hidden = true; $('expense-error').hidden = true;
    $('paid-from-label').hidden = true; $('paid-from').required = false;
    $('expense-date').value = state.today; $('expense-date').max = state.today;
    $('amount-label').textContent = 'Total amount (' + state.overview.currency + ')';
    const counts = {};
    state.overview.categories.forEach(row => counts[row.label] = (counts[row.label] || 0) + 1);
    options($('category'), state.overview.categories.map(row => [row.account, row.label + (counts[row.label] > 1 ? ' · ' + row.detail : '')]), 'Choose category');
    options($('paid-from'), state.overview.payment_accounts.map(row => [row.name, row.account_name]), 'Choose cash or bank');
    $('add-supplier').hidden = !state.overview.can_add_supplier;
    $('expense-title').textContent = 'Record an expense'; $('save-draft').textContent = 'Save draft & review';
    setBusy(false); $('expense-dialog').showModal(); $('category').focus();
    try { await loadSuppliers(); } catch (error) { showError('expense-error', error); }
  }
  function renderReview() {
    const data = state.expense;
    $('expense-form').hidden = true; $('review').hidden = false;
    $('expense-title').textContent = data.docstatus === 1 ? 'Expense recorded' : 'Review your expense';
    $('review-status').textContent = data.docstatus === 1 ? 'Recorded in project costs. ' + data.name : 'Draft saved. Check the details below before recording this cost.';
    $('review-details').replaceChildren();
    [['Supplier', data.supplier], ['Category', data.category], ['Description', data.description],
      ['Total', money(data.amount, data.currency)], ['Date', dateLabel(data.date)], ['Payment', data.payment ? 'Already paid · ' + data.payment : 'Not paid yet'],
      ['Receipt no.', data.bill_no || 'Not provided']].forEach(([label, value]) => {
      const row = node('div'); row.append(node('dt', label), node('dd', value || '—')); $('review-details').append(row);
    });
    $('receipt-links').replaceChildren();
    data.files.forEach(file => {
      if (!/^\/(private\/)?files\//.test(file.file_url)) return;
      const link = node('a', 'View receipt: ' + file.file_name); link.href = file.file_url; link.target = '_blank'; link.rel = 'noopener'; $('receipt-links').append(link);
    });
    $('receipt-retry').hidden = !state.uploadPending;
    $('post-expense').hidden = data.docstatus !== 0;
    $('finish-review').textContent = data.docstatus === 0 ? 'Keep as draft' : 'Done';
    setBusy(false);
  }
  async function uploadReceipt() {
    const body = new FormData(); body.append('file', state.receipt); body.append('is_private', '1');
    body.append('doctype', 'Purchase Invoice'); body.append('docname', state.expense.name);
    const response = await fetch('/api/method/upload_file', { method: 'POST', credentials: 'same-origin', body,
      headers: { 'X-Frappe-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content } });
    const data = await response.json();
    if (!response.ok || data.exc) throw new Error(errorText(data));
    state.uploadPending = false;
    state.expense = await api('expense', { name: state.expense.name });
  }
  async function saveDraft(event) {
    event.preventDefault(); if (state.busy) return;
    $('expense-error').hidden = true;
    if (!state.snapshot) {
      state.receipt = $('receipt').files[0] || null;
      if (state.receipt && (state.receipt.size > 10 * 1024 * 1024 || !/^(image\/|application\/pdf$)/.test(state.receipt.type))) {
        showError('expense-error', new Error('Choose an image or PDF smaller than 10 MB.')); return;
      }
      state.snapshot = { request_id: state.requestId, project: state.project, account: $('category').value,
        description: $('description').value, supplier: $('supplier').value, amount: $('amount').value,
        date: $('expense-date').value, paid_from: $('payment').value === 'paid' ? $('paid-from').value : '', bill_no: $('bill-no').value };
    }
    setBusy(true); $('save-draft').textContent = 'Saving…';
    $('expense-form').querySelectorAll('input, select, #add-supplier').forEach(el => el.disabled = true);
    try {
      state.expense = await api('save_expense', { payload: state.snapshot }, true);
      if (state.receipt) { state.uploadPending = true; await uploadReceipt(); }
      renderReview();
    } catch (error) {
      showError('expense-error', error);
      if (state.expense) renderReview();
      else if ([400, 403, 404, 409, 417, 422].includes(error.status)) {
        state.snapshot = null;
        $('expense-form').querySelectorAll('input, select, #add-supplier').forEach(el => el.disabled = false);
      }
    } finally { setBusy(false); $('save-draft').textContent = state.snapshot ? 'Retry saving draft' : 'Save draft & review'; }
  }
  async function openReview(name) {
    state.expense = null; state.receipt = null; state.uploadPending = false; state.snapshot = null;
    $('expense-error').hidden = true; $('expense-form').hidden = true; $('review').hidden = true;
    $('expense-title').textContent = 'Loading expense…'; $('expense-dialog').showModal(); setBusy(true);
    try { state.expense = await api('expense', { name }); renderReview(); }
    catch (error) { showError('expense-error', error); }
    finally { setBusy(false); }
  }
  $('expense-form').addEventListener('submit', saveDraft);
  $('new-expense').addEventListener('click', newExpense);
  ['close-expense', 'cancel-entry', 'finish-review'].forEach(id => $(id).addEventListener('click', closeExpense));
  $('expense-dialog').addEventListener('cancel', event => { event.preventDefault(); closeExpense(); });
  $('payment').addEventListener('change', () => {
    const paid = $('payment').value === 'paid'; $('paid-from-label').hidden = !paid; $('paid-from').required = paid;
  });
  let searchTimer;
  $('supplier-search').addEventListener('input', () => {
    clearTimeout(searchTimer); ++state.supplierGeneration;
    searchTimer = setTimeout(() => loadSuppliers($('supplier-search').value).catch(error => showError('expense-error', error)), 250);
  });
  $('retry-upload').addEventListener('click', async () => {
    setBusy(true); $('expense-error').hidden = true;
    try { await uploadReceipt(); renderReview(); } catch (error) { showError('expense-error', error); }
    finally { setBusy(false); }
  });
  $('post-expense').addEventListener('click', async () => {
    if (state.busy || state.uploadPending) return;
    setBusy(true); $('expense-error').hidden = true;
    try {
      state.expense = await api('post_expense', { name: state.expense.name, modified: state.expense.modified }, true);
      renderReview(); $('notice').textContent = 'Expense recorded. Project costs have been updated.'; $('notice').hidden = false;
    } catch (error) { showError('expense-error', error); } finally { setBusy(false); }
  });
  $('add-supplier').addEventListener('click', () => {
    $('supplier-form').reset(); $('supplier-error').hidden = true; $('supplier-dialog').showModal(); $('supplier-name').focus();
  });
  $('cancel-supplier').addEventListener('click', () => $('supplier-dialog').close());
  $('supplier-form').addEventListener('submit', async event => {
    event.preventDefault(); $('save-supplier').disabled = true;
    try {
      const supplier = await api('add_supplier', { name: $('supplier-name').value }, true);
      $('supplier-search').value = supplier.supplier_name;
      await loadSuppliers(supplier.supplier_name, supplier.name); $('supplier-dialog').close();
    } catch (error) { showError('supplier-error', error); } finally { $('save-supplier').disabled = false; }
  });
  $('project').addEventListener('change', () => { state.project = $('project').value; $('notice').hidden = true; refresh(); });
  $('refresh').addEventListener('click', refresh);
  $('logout').addEventListener('click', async () => {
    try {
      const response = await fetch('/api/method/logout', { method: 'POST', headers: { 'X-Frappe-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content } });
      if (!response.ok) throw new Error('Sign out failed. Please retry.'); location.assign('/login');
    } catch (error) { showError('page-error', error); }
  });
  (async () => {
    try {
      const result = await api('projects'); state.today = result.today;
      $('today').textContent = new Date(result.today + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
      if (!result.projects.length) { $('loading').textContent = 'No projects are available yet. Add your first project in the advanced workspace.'; options($('project'), [], 'No projects'); return; }
      options($('project'), result.projects.map(project => [project.name, project.project_name]));
      const requested = new URLSearchParams(location.search).get('project');
      state.project = result.projects.some(p => p.name === requested) ? requested : result.projects[0].name;
      $('project').value = state.project; $('project').disabled = false; $('refresh').disabled = false; await refresh();
    } catch (error) { $('loading').hidden = true; showError('page-error', error); }
  })();
})();
