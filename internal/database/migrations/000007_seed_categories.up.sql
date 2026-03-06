-- Default expense categories (PRD C-1)
INSERT INTO categories (name, type, is_system, display_order) VALUES
    ('Household',        'expense', true, 1),
    ('Food & Groceries', 'expense', true, 2),
    ('Transport',        'expense', true, 3),
    ('Health',           'expense', true, 4),
    ('Education',        'expense', true, 5),
    ('Mobile',           'expense', true, 6),
    ('Electricity',      'expense', true, 7),
    ('Gas',              'expense', true, 8),
    ('Internet',         'expense', true, 9),
    ('Gifts',            'expense', true, 10),
    ('Entertainment',    'expense', true, 11),
    ('Shopping',         'expense', true, 12),
    ('Subscriptions',    'expense', true, 13),
    ('Building Fund',    'expense', true, 14),
    ('Insurance',        'expense', true, 15),
    ('Fees & Charges',   'expense', true, 16),
    ('Debt Payment',     'expense', true, 17),
    ('Other',            'expense', true, 18);

-- Default income categories (PRD C-2)
INSERT INTO categories (name, type, is_system, display_order) VALUES
    ('Salary',                    'income', true, 1),
    ('Freelance',                 'income', true, 2),
    ('Investment Returns',        'income', true, 3),
    ('Refund',                    'income', true, 4),
    ('Building Fund Collection',  'income', true, 5),
    ('Loan Repayment Received',   'income', true, 6),
    ('Other',                     'income', true, 7);
