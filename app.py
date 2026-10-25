from datetime import date, timedelta, datetime
from functools import wraps
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "replace-this-secret-before-deployment")
DB_PATH = os.path.join(os.path.dirname(__file__), "milk.db")


def db_conn():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
      username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('admin','customer')),
      phone TEXT DEFAULT '', address TEXT DEFAULT '',
      price_per_litre REAL NOT NULL DEFAULT 60, active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS deliveries(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      customer_id INTEGER NOT NULL REFERENCES users(id),
      delivery_date TEXT NOT NULL, litres REAL NOT NULL CHECK(litres>=0),
      price_per_litre REAL NOT NULL CHECK(price_per_litre>=0), note TEXT DEFAULT '',
      UNIQUE(customer_id, delivery_date)
    );
    CREATE TABLE IF NOT EXISTS payments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      customer_id INTEGER NOT NULL REFERENCES users(id),
      amount REAL NOT NULL CHECK(amount>0), payment_date TEXT NOT NULL,
      method TEXT NOT NULL DEFAULT 'Cash', note TEXT DEFAULT ''
    );
    """)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        db.execute("INSERT INTO users(name,username,password_hash,role,address,price_per_litre) VALUES(?,?,?,?,?,?)",
                   ("Milk Vendor", "admin", generate_password_hash("Admin@123"), "admin", "Vendor office", 60))
        samples = [
            ("Asha Patil", "asha", "9000000001", "Shivaji Nagar", 60, 1.0),
            ("Rahul More", "rahul", "9000000002", "Ganesh Colony", 58, 1.5),
            ("Priya Joshi", "priya", "9000000003", "Market Road", 62, 2.0),
        ]
        for name, username, phone, address, rate, base_litres in samples:
            db.execute("INSERT INTO users(name,username,password_hash,role,phone,address,price_per_litre) VALUES(?,?,?,?,?,?,?)",
                       (name, username, generate_password_hash("Customer@123"), "customer", phone, address, rate))
            customer_id = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()[0]
            for offset in range(89, -1, -1):
                day = date.today() - timedelta(days=offset)
                if (offset + customer_id) % (13 + customer_id) == 0:
                    continue
                litres = base_litres + (0.25 if (offset + customer_id) % 7 == 0 else 0)
                db.execute("INSERT OR IGNORE INTO deliveries(customer_id,delivery_date,litres,price_per_litre,note) VALUES(?,?,?,?,?)",
                           (customer_id, day.isoformat(), litres, rate, "Sample data"))
    db.commit()
    db.close()


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access is required.", "error")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapper


def current_user():
    if not session.get("user_id"):
        return None
    return db_conn().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()


def bill_summary(customer_id, start, end):
    db = db_conn()
    row = db.execute("""SELECT COALESCE(SUM(litres),0) litres,
      COALESCE(SUM(litres*price_per_litre),0) amount, COUNT(*) days
      FROM deliveries WHERE customer_id=? AND delivery_date BETWEEN ? AND ?""",
      (customer_id, start, end)).fetchone()
    paid = db.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE customer_id=? AND payment_date BETWEEN ? AND ?",
                      (customer_id, start, end)).fetchone()[0]
    return {"litres": row["litres"], "amount": row["amount"], "days": row["days"],
            "paid": paid, "balance": row["amount"] - paid}


@app.route("/")
def index():
    return redirect(url_for("dashboard" if session.get("user_id") else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = db_conn().execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"], session["name"], session["role"] = user["id"], user["name"], user["role"]
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@require_login
def dashboard():
    db, today = db_conn(), date.today().isoformat()
    user = current_user()
    month_start = date.today().replace(day=1).isoformat()
    if user["role"] == "admin":
        stats = db.execute("""SELECT COUNT(DISTINCT customer_id) customers,
          COALESCE(SUM(litres),0) litres, COALESCE(SUM(litres*price_per_litre),0) sales
          FROM deliveries WHERE delivery_date=?""", (today,)).fetchone()
        monthly = db.execute("SELECT COALESCE(SUM(litres*price_per_litre),0) FROM deliveries WHERE delivery_date>=?", (month_start,)).fetchone()[0]
        received = db.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE payment_date>=?", (month_start,)).fetchone()[0]
        recent = db.execute("""SELECT d.*,u.name customer_name FROM deliveries d JOIN users u ON u.id=d.customer_id
          ORDER BY delivery_date DESC,d.id DESC LIMIT 10""").fetchall()
        return render_template("admin_dashboard.html", stats=stats, monthly=monthly, received=received, recent=recent, today=today)
    summary = bill_summary(user["id"], month_start, today)
    recent = db.execute("SELECT * FROM deliveries WHERE customer_id=? ORDER BY delivery_date DESC LIMIT 10", (user["id"],)).fetchall()
    return render_template("customer_dashboard.html", user=user, summary=summary, recent=recent, start=month_start, end=today)


@app.route("/customers")
@require_login
@require_admin
def customers():
    rows = db_conn().execute("SELECT * FROM users WHERE role='customer' ORDER BY name").fetchall()
    return render_template("customers.html", customers=rows)


@app.route("/customers/add", methods=["POST"])
@require_login
@require_admin
def add_customer():
    name = request.form.get("name", "").strip()
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    try:
        rate = float(request.form.get("price_per_litre", "60"))
        if not name or len(username) < 3 or len(password) < 8 or rate < 0:
            raise ValueError
        db_conn().execute("""INSERT INTO users(name,username,password_hash,role,phone,address,price_per_litre)
          VALUES(?,?,?,?,?,?,?)""", (name, username, generate_password_hash(password), "customer",
          request.form.get("phone", "").strip(), request.form.get("address", "").strip(), rate))
        db_conn().commit()
        flash("Customer account created.", "success")
    except sqlite3.IntegrityError:
        flash("That username already exists.", "error")
    except (ValueError, TypeError):
        flash("Enter valid details. Password must be at least 8 characters.", "error")
    return redirect(url_for("customers"))


@app.route("/deliveries", methods=["GET", "POST"])
@require_login
@require_admin
def deliveries():
    db = db_conn()
    if request.method == "POST":
        try:
            customer_id = int(request.form["customer_id"])
            day = request.form["delivery_date"]
            litres = float(request.form["litres"])
            datetime.strptime(day, "%Y-%m-%d")
            customer = db.execute("SELECT * FROM users WHERE id=? AND role='customer' AND active=1", (customer_id,)).fetchone()
            price = float(request.form.get("price_per_litre") or (customer["price_per_litre"] if customer else 0))
            if not customer or litres < 0 or price < 0:
                raise ValueError
            db.execute("""INSERT INTO deliveries(customer_id,delivery_date,litres,price_per_litre,note)
              VALUES(?,?,?,?,?) ON CONFLICT(customer_id,delivery_date) DO UPDATE SET
              litres=excluded.litres,price_per_litre=excluded.price_per_litre,note=excluded.note""",
              (customer_id, day, litres, price, request.form.get("note", "").strip()))
            db.commit()
            flash("Delivery saved. An existing entry for that customer/date was updated.", "success")
        except (ValueError, KeyError, TypeError):
            flash("Please enter a valid customer, date, quantity and price.", "error")
        return redirect(url_for("deliveries"))
    customers = db.execute("SELECT id,name,price_per_litre FROM users WHERE role='customer' AND active=1 ORDER BY name").fetchall()
    rows = db.execute("""SELECT d.*,u.name customer_name FROM deliveries d JOIN users u ON u.id=d.customer_id
      ORDER BY delivery_date DESC,d.id DESC LIMIT 100""").fetchall()
    return render_template("deliveries.html", customers=customers, deliveries=rows, today=date.today().isoformat())


@app.route("/billing")
@require_login
def billing():
    db, user = db_conn(), current_user()
    start_default, end_default = date.today().replace(day=1).isoformat(), date.today().isoformat()
    is_admin = user["role"] == "admin"
    customers = db.execute("SELECT id,name FROM users WHERE role='customer' AND active=1 ORDER BY name").fetchall() if is_admin else []
    try:
        customer_id = int(request.args.get("customer_id") or user["id"]) if is_admin else user["id"]
        start, end = request.args.get("start", start_default), request.args.get("end", end_default)
        datetime.strptime(start, "%Y-%m-%d"); datetime.strptime(end, "%Y-%m-%d")
        if start > end: raise ValueError
    except (ValueError, TypeError):
        flash("Choose a valid date range.", "error")
        customer_id, start, end = user["id"], start_default, end_default
    customer = db.execute("SELECT * FROM users WHERE id=? AND role='customer'", (customer_id,)).fetchone()
    if not customer:
        flash("Customer not found.", "error")
        return redirect(url_for("dashboard"))
    summary = bill_summary(customer_id, start, end)
    records = db.execute("SELECT * FROM deliveries WHERE customer_id=? AND delivery_date BETWEEN ? AND ? ORDER BY delivery_date",
                         (customer_id, start, end)).fetchall()
    payments = db.execute("SELECT * FROM payments WHERE customer_id=? AND payment_date BETWEEN ? AND ? ORDER BY payment_date DESC",
                          (customer_id, start, end)).fetchall()
    return render_template("billing.html", customer=customer, customers=customers, summary=summary, records=records,
                           payments=payments, start=start, end=end, is_admin=is_admin)


@app.route("/payments", methods=["GET", "POST"])
@require_login
@require_admin
def payments():
    db = db_conn()
    if request.method == "POST":
        try:
            customer_id, amount = int(request.form["customer_id"]), float(request.form["amount"])
            day, method = request.form["payment_date"], request.form.get("method", "Cash")
            datetime.strptime(day, "%Y-%m-%d")
            exists = db.execute("SELECT id FROM users WHERE id=? AND role='customer'", (customer_id,)).fetchone()
            if amount <= 0 or not exists: raise ValueError
            db.execute("INSERT INTO payments(customer_id,amount,payment_date,method,note) VALUES(?,?,?,?,?)",
                       (customer_id, amount, day, method, request.form.get("note", "").strip()))
            db.commit()
            flash("Payment recorded.", "success")
        except (ValueError, KeyError, TypeError):
            flash("Enter valid payment details.", "error")
        return redirect(url_for("payments"))
    customers = db.execute("SELECT id,name FROM users WHERE role='customer' AND active=1 ORDER BY name").fetchall()
    rows = db.execute("""SELECT p.*,u.name customer_name FROM payments p JOIN users u ON u.id=p.customer_id
      ORDER BY payment_date DESC,p.id DESC LIMIT 100""").fetchall()
    return render_template("payments.html", customers=customers, payments=rows, today=date.today().isoformat())


@app.route("/prediction", methods=["GET", "POST"])
@require_login
@require_admin
def prediction():
    from ml_model import predict_next_days
    forecast, error, days = None, None, 7
    if request.method == "POST":
        try:
            days = max(1, min(30, int(request.form.get("days", 7))))
            forecast = predict_next_days(DB_PATH, days)
        except Exception as exc:
            error = "Prediction failed. Add more delivery history. " + str(exc)
    return render_template("prediction.html", forecast=forecast, error=error, days=days)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
