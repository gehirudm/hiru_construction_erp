frappe.ui.form.on('Construction Cost Plan', {
    setup(frm) {
        frm.set_query('account', 'items', () => ({filters: {
            company: frm.doc.company, root_type: 'Expense', is_group: 0, disabled: 0
        }}));
        frm.set_query('baseline', () => ({filters: {
            project: frm.doc.project, version_kind: 'Tender baseline', docstatus: 1
        }}));
    },
    refresh(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.status === 'Approved' && frm.perm[0]?.create) {
            frm.add_custom_button(__('Create Revision'), () => {
                frappe.new_doc('Construction Cost Plan', {}, doc => {
                    doc.project = frm.doc.project;
                    doc.company = frm.doc.company;
                    doc.currency = frm.doc.currency;
                    doc.version_kind = 'Approved revision';
                    doc.baseline = frm.doc.baseline || frm.doc.name;
                    doc.items = [];
                    for (const row of frm.doc.items) {
                        const item = frappe.model.add_child(doc, 'Construction Cost Plan Item', 'items');
                        Object.assign(item, {
                            category: row.category, account: row.account,
                            original_estimate: row.original_estimate,
                            approved_revision: frm.doc.version_kind === 'Tender baseline'
                                ? row.original_estimate : row.approved_revision,
                            contingency: row.contingency, notes: row.notes
                        });
                    }
                });
            });
        }
        if (frm.doc.project) {
            frm.add_custom_button(__('Project Cost Overview'), () =>
                frappe.set_route('query-report', 'Construction Project Costs', {project: frm.doc.project}));
        }
    }
});
