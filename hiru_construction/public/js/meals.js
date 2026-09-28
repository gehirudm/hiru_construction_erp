(() => {
  'use strict';
  const { $, state, node, api, money, dateLabel, newExpense } = window.hiruDaily;
  const call = (method, args, post = false) => api('hiru_construction.meals.' + method, args, post);
  let selectedDate, project, latest, panel, busy = false, alertGeneration = 0;
  const types = ['Breakfast', 'Lunch', 'Dinner'];
  const button = (text, fn, cls = 'secondary') => { const b = node('button', text, cls); b.type = 'button'; b.addEventListener('click', fn); return b; };
  const label = (text, input) => { const l = node('label', text); l.append(input); return l; };
  function open(title) {
    $('work-dialog-title').textContent = title;
    const body = $('work-dialog-body'); body.replaceChildren(); $('work-dialog').showModal(); return body;
  }
  function error(body, e) { body.append(node('p', e.message, 'alert error')); }
  async function alerts() {
    const generation = ++alertGeneration;
    $('meal-alert').hidden = true;
    try {
      const rows = await call('alerts', { project: state.project });
      if (generation !== alertGeneration || !rows.length) return;
      $('meal-alert').replaceChildren(node('span', `${rows.length === 50 ? '50+' : rows.length} meals have exceeded the expected cost per person. `),
        button('View meals', () => document.querySelector('[data-view="meals"]').click()));
      $('meal-alert').hidden = false;
    } catch (_) { /* A user without meal permissions can continue other work. */ }
  }
  document.addEventListener('hiru:project-ready', alerts);
  async function render(target, current = () => true) {
    panel = target;
    if (project !== state.project) { selectedDate = state.today; project = state.project; }
    const data = await call('board', { project, date: selectedDate });
    if (!current()) return;
    latest = data; panel.replaceChildren(node('h2', 'Meals'), node('p', 'Track each meal’s cost and the people who actually ate. Bills for the same meal share one headcount.', 'muted'));
    const toolbar = node('div', undefined, 'work-toolbar');
    const date = node('input'); date.type = 'date'; date.value = selectedDate; date.max = state.today; date.id = 'meal-date';
    date.addEventListener('change', () => { selectedDate = date.value; render(panel).catch(e => error(panel, e)); });
    toolbar.append(label('Meal date', date));
    if (data.can_settings) toolbar.append(button('Expected costs per person', settings));
    panel.append(toolbar, node('p', `${data.suggested_diners} people suggested from confirmed present/half-day attendance. Adjust separately for each meal.`, 'work-summary'));
    if (!data.suggested_diners) panel.append(node('p', 'No confirmed attendance found for this date. Confirm attendance first, or enter a manual diner count and explain it.', 'alert'));
    if (!data.categories.length) panel.append(node('p', 'Meals is available as a category. Add it to the approved project budget before recording meal expenses.', 'alert'));
    const cards = node('div', undefined, 'category-cards');
    types.forEach(type => {
      const meal = data.meals.find(m => m.type === type);
      const card = node('article', undefined, 'category-card'); card.append(node('h3', type));
      if (meal) {
        card.append(node('p', `${meal.diners} diners · ${meal.attendance_headcount} suggested from attendance`, 'muted'));
        if (meal.reason) card.append(node('p', meal.reason, 'muted'));
        card.append(node('p', `Spent ${money(meal.total)} · ${meal.bill_count} posted bills`, 'work-summary'));
        card.append(node('p', `${money(meal.per_head)} per person · Expected ${money(meal.expected)}`, meal.over_limit ? 'alert error' : 'muted'));
        if (meal.over_limit) card.append(node('p', `${money(meal.excess)} over this meal’s allowance`, 'red'));
        card.append(button('Adjust diners', () => edit(type, meal)));
        const add = button('Add ' + type.toLowerCase() + ' expense', () => newExpense(data.categories[0].account, meal), 'primary');
        add.disabled = !data.categories.length || !state.overview.can_create; card.append(add);
      } else {
        card.append(node('p', data.rates[type] ? `Expected ${money(data.rates[type])} per person` : 'Set an expected cost first.', 'muted'));
        const start = button('Set up ' + type.toLowerCase(), () => edit(type), 'primary'); start.disabled = !data.can_create || !data.rates[type]; card.append(start);
      }
      cards.append(card);
    }); panel.append(cards, node('h3', 'Recent meals'));
    data.recent.forEach(meal => {
      const row = node('div', undefined, 'transaction-row');
      row.append(button(`${dateLabel(meal.date)} · ${meal.type}`, () => { selectedDate = meal.date; render(panel).catch(e => error(panel, e)); }, 'text-button'),
        node('span', `${meal.diners} diners · ${money(meal.total)} total · ${money(meal.per_head)}/person${meal.over_limit ? ' · OVER LIMIT' : ''}`, meal.over_limit ? 'red' : ''));
      panel.append(row);
    });
    panel.append(node('p', 'Latest 30 meals. Draft bills do not count. Expected costs and attendance suggestions are saved with each meal; future attendance or rate changes do not rewrite them.', 'muted'));
  }
  function settings() {
    const body = open('Expected meal cost per person'), form = node('form'); form.className = 'form-grid';
    types.forEach(type => {
      const input = node('input'); input.type = 'number'; input.min = '.01'; input.max = '99999999'; input.step = '.01'; input.value = latest.rates[type] || ''; input.dataset.mealType = type;
      form.append(label(type + ' (' + state.overview.currency + ')', input));
    });
    form.append(node('p', 'These defaults apply to new meals only. Existing meals retain their expected cost.', 'muted full'));
    const save = node('button', 'Save expected costs', 'primary'); save.type = 'submit'; form.append(save); body.append(form);
    form.addEventListener('submit', async e => {
      e.preventDefault(); if (busy) return; busy = true; save.disabled = true;
      try {
        const rates = Object.fromEntries([...form.querySelectorAll('input')].filter(i => i.value).map(i => [i.dataset.mealType, i.value]));
        await call('save_rates', { project, rates }, true); $('work-dialog').close(); await render(panel);
      } catch (e) { error(body, e); } finally { busy = false; save.disabled = false; }
    });
  }
  function edit(type, meal) {
    const body = open(type + ' diners'), form = node('form'); form.className = 'form-grid';
    const suggested = meal ? meal.attendance_headcount : latest.suggested_diners;
    body.append(node('p', `${suggested} diners suggested from confirmed attendance${meal ? ' when this meal was created' : ''}.`, 'work-summary'));
    const count = node('input'); count.type = 'number'; count.min = '1'; count.max = '10000'; count.step = '1'; count.required = true; count.value = meal?.diners || suggested || ''; count.id = 'meal-diners';
    const reason = node('input'); reason.value = meal?.reason || ''; reason.maxLength = 500; reason.id = 'meal-reason';
    form.append(label('People who actually ate', count), label('Reason if adjusted', reason));
    const save = node('button', 'Save meal headcount', 'primary'); save.type = 'submit'; form.append(save); body.append(form);
    form.addEventListener('submit', async e => {
      e.preventDefault(); if (busy) return; busy = true; save.disabled = true;
      try {
        await call('save_meal', { project, date: selectedDate, meal_type: type, diners: count.value,
          reason: reason.value, name: meal?.name, modified: meal?.modified }, true);
        $('work-dialog').close(); await render(panel); await alerts();
      } catch (e) { error(body, e); } finally { busy = false; save.disabled = false; }
    });
  }
  function expenseNote() {
    const selected = state.overview?.categories.find(c => c.account === $('category').value);
    const active = selected?.entry_type === 'Meals'; $('meal-expense-note').hidden = !active;
    if (active) $('meal-expense-note').textContent = state.meal
      ? `${state.meal.type} on ${dateLabel(state.meal.date)} · ${state.meal.diners} diners · Expected ${money(state.meal.expected)} each. Additional bills share this headcount.`
      : 'Set up this meal in the Meals tab first, then use its Add expense button so bills share the correct headcount.';
    if (active && !state.meal) $('meal-expense-note').append(button('Go to Meals', () => {
      $('close-expense').click(); document.querySelector('[data-view="meals"]').click();
    }));
  }
  $('category').addEventListener('change', expenseNote); document.addEventListener('hiru:expense-open', expenseNote);
  window.hiruMeals = { render };
})();
