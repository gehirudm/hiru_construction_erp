(() => {
  'use strict';
  const { state, node, api, money, dateLabel, options } = window.hiruDaily;
  let project, filters = {}, currentPage = 1, request = 0;
  async function render(panel, current = () => true) {
    const token = ++request;
    if (project !== state.project) { project = state.project; filters = {}; currentPage = 1; }
    const data = await api('hiru_construction.expenses.listing', { project, filters: JSON.stringify(filters), page: currentPage });
    if (token !== request || !current()) return;
    currentPage = data.page;
    panel.replaceChildren(node('h2', 'All expenses'), node('p', 'Posted project costs, oldest first. Running totals start at zero for the selected filters and continue across pages.', 'muted'));
    const form = node('form', undefined, 'expense-filters'), inputs = {};
    const field = (key, text, input) => {
      input.name = key; input.value = filters[key] || ''; inputs[key] = input;
      const label = node('label', text); label.append(input); form.append(label);
    };
    for (const [key, text, type] of [['from_date', 'From date', 'date'], ['to_date', 'To date', 'date'],
      ['search', 'Supplier, description or reference', 'search'], ['minimum', 'Minimum amount', 'number'], ['maximum', 'Maximum amount', 'number']]) {
      const input = node('input'); input.type = type; if (type === 'number') input.step = '.01';
      if (type === 'search') input.maxLength = 150; field(key, text, input);
    }
    const category = node('select'); options(category, data.categories.map(row => [row.value, row.label]), 'All categories'); field('category', 'Category', category);
    const source = node('select'); options(source, data.sources.map(value => [value, value]), 'All sources'); field('source', 'Expense source', source);
    const apply = node('button', 'Apply filters', 'primary'); apply.type = 'submit';
    const reset = node('button', 'Clear filters', 'secondary'); reset.type = 'button'; form.append(apply, reset);
    const reload = async () => {
      apply.disabled = reset.disabled = true;
      try { await render(panel, current); }
      catch (error) { if (current()) panel.append(node('p', error.message, 'alert error')); }
      finally { apply.disabled = reset.disabled = false; }
    };
    form.addEventListener('submit', event => {
      event.preventDefault(); filters = Object.fromEntries(Object.entries(inputs).map(([key, input]) => [key, input.value])); currentPage = 1; reload();
    });
    reset.addEventListener('click', () => { filters = {}; currentPage = 1; reload(); }); panel.append(form);
    const summary = node('p', `${data.count} entries · Filtered total ${money(data.total, data.currency)}`, 'work-summary'); summary.id = 'expenses-summary'; panel.append(summary);
    panel.append(node('p', 'One row per document and category. Credits reduce the total. Drafts and open orders are not included.', 'muted'));
    if (!data.rows.length) panel.append(node('p', 'No expenses match these filters.', 'empty'));
    else {
      const wrap = node('div', undefined, 'expense-table-wrap'); wrap.tabIndex = 0; wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', 'Expense list');
      const table = node('table', undefined, 'expense-table'); const caption = node('caption', `Expenses in ${data.currency} — page ${data.page}`); table.append(caption);
      const head = node('thead'), tr = node('tr');
      ['Date', 'Category', 'Description / supplier', 'Source / reference', 'Amount', 'Running total'].forEach(text => { const th = node('th', text); th.scope = 'col'; tr.append(th); }); head.append(tr); table.append(head);
      const body = node('tbody');
      data.rows.forEach(row => {
        const tr = node('tr'); tr.append(node('td', dateLabel(row.date)), node('td', row.category_label));
        const detail = node('td'); detail.append(node('span', row.party || row.description || 'Project expense'));
        if (row.party && row.description) detail.append(node('small', row.description)); tr.append(detail);
        const ref = node('td'); ref.append(node('span', row.source));
        const link = node('a', row.reference); link.href = '/desk/' + encodeURIComponent(row.source.toLowerCase().replaceAll(' ', '-')) + '/' + encodeURIComponent(row.reference);
        link.target = '_blank'; link.rel = 'noopener'; ref.append(link); tr.append(ref);
        tr.append(node('td', money(row.amount, data.currency), 'expense-number'), node('td', money(row.running_total, data.currency), 'expense-number')); body.append(tr);
      }); table.append(body); wrap.append(table); panel.append(wrap);
    }
    const pages = node('div', undefined, 'work-toolbar');
    const prev = node('button', 'Previous', 'secondary'), next = node('button', 'Next', 'secondary');
    prev.disabled = data.page <= 1; next.disabled = !data.has_more;
    prev.addEventListener('click', () => { currentPage--; prev.disabled = next.disabled = true; reload(); });
    next.addEventListener('click', () => { currentPage++; prev.disabled = next.disabled = true; reload(); });
    pages.append(prev, node('span', `Page ${data.page} of ${Math.max(1, Math.ceil(data.count / data.page_size))} · ${money(data.opening_total, data.currency)} carried forward`), next); panel.append(pages);
  }
  window.hiruExpenses = { render };
})();
