# Smart Milk Delivery Management System

## Demo logins
- Admin: `admin` / `Admin@123`
- Customer: `asha` / `Customer@123`
- Customers `rahul` and `priya` also use `Customer@123`.

These are demo credentials. Change them and the Flask secret key before using real data.

## Windows setup
1. Install Python 3.11 or newer from https://www.python.org/downloads/ and select **Add Python to PATH**.
2. Extract this ZIP.
3. Open the extracted folder in File Explorer, click the address bar, type `cmd`, and press Enter.
4. Run:
   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
   ```
   Or double-click `run_windows.bat`.
5. Open http://127.0.0.1:5000.

## Features
- Admin and customer login, password hashes, SQLite database.
- Add customers, daily delivery entry (one entry per customer/date; resaving updates it).
- Custom, weekly, and monthly billing; payment history and period balance.
- Admin dashboard, payment tracking, customer portal.
- scikit-learn Linear Regression forecast for future total milk demand.
- Seeds sample accounts and 90 days of sample deliveries on first run.

## Notes
- Deleting `milk.db` resets the demo and deletes all saved records.
- Payments are subtracted from the selected billing date range. A production system should allocate payments to invoice IDs.
- This educational version does not include CSRF protection, password reset, SMS/email, audit logs, or production deployment hardening.
- Forecasts are estimates, not billing records. Validate model accuracy before business use.
