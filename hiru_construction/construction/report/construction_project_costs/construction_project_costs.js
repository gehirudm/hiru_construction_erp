frappe.query_reports['Construction Project Costs'] = {
    filters: [{fieldname: 'project', label: __('Project'), fieldtype: 'Link', options: 'Project', reqd: 1}],
    formatter(value, row, column, data, default_formatter) {
        if (data?.reconciliation && ['exposure', 'remaining_budget'].includes(column.fieldname)) {
            return __('Review receipts');
        }
        const text = default_formatter(value, row, column, data);
        if (data && column.fieldname === 'remaining_budget' && data.remaining_budget < 0) {
            return `<span class="text-danger">${text}</span>`;
        }
        return text;
    }
};
