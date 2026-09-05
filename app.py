from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
import secrets
import re
from datetime import datetime

app = Flask(__name__)

# =========================================================
# Google Search Console verification
# =========================================================

@app.route("/google35cefc4bc1a94ac4.html")
def google_verification():
    return "google-site-verification: google35cefc4bc1a94ac4.html"


# =========================================================
# Security / Session
# =========================================================

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "CHANGE_THIS_SECRET_KEY"
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
    PERMANENT_SESSION_LIFETIME=3600
)

DATABASE = "store.db"


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    return response


# =========================================================
# Database
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            price INTEGER NOT NULL,
            discount INTEGER DEFAULT 0,
            category TEXT DEFAULT '',
            image TEXT DEFAULT '',
            stock INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            total INTEGER NOT NULL,
            status TEXT DEFAULT 'جدید'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            text TEXT DEFAULT '',
            image TEXT DEFAULT '',
            link TEXT DEFAULT ''
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS support_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'در حال پیگیری',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(request_id) REFERENCES support_requests(id)
        )
    """)

    admin = conn.execute(
        "SELECT * FROM admins LIMIT 1"
    ).fetchone()

    if not admin:
        conn.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            (
                "admin",
                generate_password_hash("159753")
            )
        )

    product_count = conn.execute(
        "SELECT COUNT(*) AS count FROM products"
    ).fetchone()["count"]

    if product_count == 0:
        products = [
            (
                "گوشی هوشمند مدل X",
                "گوشی هوشمند با طراحی مدرن و امکانات کامل",
                18990000,
                10,
                "موبایل",
                "",
                20
            ),
            (
                "هدفون بی‌سیم",
                "هدفون بی‌سیم با کیفیت صدای عالی",
                2490000,
                15,
                "لوازم جانبی",
                "",
                35
            ),
            (
                "ساعت هوشمند",
                "ساعت هوشمند مناسب استفاده روزمره",
                3290000,
                5,
                "پوشیدنی",
                "",
                15
            ),
            (
                "لپ‌تاپ اقتصادی",
                "لپ‌تاپ مناسب کار و تحصیل",
                28900000,
                8,
                "لپ‌تاپ",
                "",
                10
            )
        ]

        conn.executemany("""
            INSERT INTO products
            (name, description, price, discount, category, image, stock)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, products)

    ad_count = conn.execute(
        "SELECT COUNT(*) AS count FROM ads"
    ).fetchone()["count"]

    if ad_count == 0:
        conn.execute("""
            INSERT INTO ads
            (title, text, image, link)
            VALUES (?, ?, ?, ?)
        """, (
            "فروش ویژه",
            "تخفیف‌های ویژه فروشگاه را از دست ندهید",
            "",
            "/"
        ))

    conn.commit()
    conn.close()


# =========================================================
# Admin
# =========================================================

def admin_required():
    return session.get("admin_logged_in") is True


# =========================================================
# Home
# =========================================================

@app.route("/")
def home():
    conn = get_db()

    search = request.args.get(
        "search",
        ""
    ).strip()

    selected_category = request.args.get(
        "category",
        ""
    ).strip()

    min_price = request.args.get(
        "min_price",
        ""
    ).strip()

    max_price = request.args.get(
        "max_price",
        ""
    ).strip()

    query = """
        SELECT *
        FROM products
        WHERE 1 = 1
    """

    params = []

    if search:
        query += """
            AND (
                name LIKE ?
                OR description LIKE ?
                OR category LIKE ?
            )
        """

        params.extend([
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        ])

    if selected_category:
        query += " AND category = ?"
        params.append(selected_category)

    if min_price:
        try:
            min_value = int(min_price)
            query += " AND price >= ?"
            params.append(min_value)
        except ValueError:
            min_price = ""

    if max_price:
        try:
            max_value = int(max_price)
            query += " AND price <= ?"
            params.append(max_value)
        except ValueError:
            max_price = ""

    query += " ORDER BY id DESC"

    products = conn.execute(
        query,
        params
    ).fetchall()

    ads = conn.execute("""
        SELECT *
        FROM ads
        ORDER BY id DESC
    """).fetchall()

    categories = conn.execute("""
        SELECT DISTINCT category
        FROM products
        WHERE category != ''
        ORDER BY category
    """).fetchall()

    conn.close()

    return render_template(
        "home.html",
        products=products,
        ads=ads,
        categories=categories,
        search=search,
        selected_category=selected_category,
        min_price=min_price,
        max_price=max_price
    )


# =========================================================
# Search
# =========================================================

@app.route("/search")
def search():
    return redirect(
        url_for(
            "home",
            search=request.args.get("q", "")
        )
    )


# =========================================================
# Product
# =========================================================

@app.route("/product/<int:product_id>")
def product(product_id):
    conn = get_db()

    product_item = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    conn.close()

    if not product_item:
        return "محصول پیدا نشد", 404

    return render_template(
        "product.html",
        product=product_item
    )


# =========================================================
# Category
# =========================================================

@app.route("/category/<category>")
def category(category):
    conn = get_db()

    products = conn.execute("""
        SELECT *
        FROM products
        WHERE category = ?
        ORDER BY id DESC
    """, (
        category,
    )).fetchall()

    ads = conn.execute("""
        SELECT *
        FROM ads
        ORDER BY id DESC
    """).fetchall()

    categories = conn.execute("""
        SELECT DISTINCT category
        FROM products
        WHERE category != ''
        ORDER BY category
    """).fetchall()

    conn.close()

    return render_template(
        "home.html",
        products=products,
        ads=ads,
        categories=categories,
        search="",
        selected_category=category,
        min_price="",
        max_price=""
    )


# =========================================================
# Offers
# =========================================================

@app.route("/offers")
def offers():
    conn = get_db()

    products = conn.execute("""
        SELECT *
        FROM products
        WHERE discount > 0
        ORDER BY discount DESC
    """).fetchall()

    ads = conn.execute("""
        SELECT *
        FROM ads
        ORDER BY id DESC
    """).fetchall()

    categories = conn.execute("""
        SELECT DISTINCT category
        FROM products
        WHERE category != ''
        ORDER BY category
    """).fetchall()

    conn.close()

    return render_template(
        "home.html",
        products=products,
        ads=ads,
        categories=categories,
        search="",
        selected_category="",
        min_price="",
        max_price=""
    )


# =========================================================
# Categories
# =========================================================

@app.route("/categories")
def categories_page():
    return redirect(
        url_for("products_page")
    )


# =========================================================
# Products
# =========================================================

@app.route("/products")
def products_page():
    conn = get_db()

    products = conn.execute("""
        SELECT *
        FROM products
        ORDER BY id DESC
    """).fetchall()

    ads = conn.execute("""
        SELECT *
        FROM ads
        ORDER BY id DESC
    """).fetchall()

    categories = conn.execute("""
        SELECT DISTINCT category
        FROM products
        WHERE category != ''
        ORDER BY category
    """).fetchall()

    conn.close()

    return render_template(
        "home.html",
        products=products,
        ads=ads,
        categories=categories,
        search="",
        selected_category="",
        min_price="",
        max_price=""
    )


# =========================================================
# Cart
# =========================================================

@app.route("/cart")
def cart():
    cart_data = session.get(
        "cart",
        {}
    )

    items = []
    total = 0

    conn = get_db()

    for product_id, quantity in cart_data.items():

        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            continue

        if quantity <= 0:
            continue

        product_item = conn.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()

        if product_item:

            price = product_item["price"]
            discount = product_item["discount"] or 0

            final_price = int(
                price * (100 - discount) / 100
            )

            subtotal = final_price * quantity

            items.append({
                "product": product_item,
                "quantity": quantity,
                "price": final_price,
                "subtotal": subtotal
            })

            total += subtotal

    conn.close()

    return render_template(
        "cart.html",
        items=items,
        total=total
    )


@app.post("/cart/add/<int:product_id>")
def cart_add(product_id):

    conn = get_db()

    product_item = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    conn.close()

    if not product_item:
        return "محصول پیدا نشد", 404

    if product_item["stock"] <= 0:
        return "این محصول موجود نیست.", 400

    cart_data = session.get(
        "cart",
        {}
    )

    product_key = str(product_id)

    current_quantity = cart_data.get(
        product_key,
        0
    )

    try:
        current_quantity = int(current_quantity)
    except (ValueError, TypeError):
        current_quantity = 0

    if current_quantity >= product_item["stock"]:
        return "بیشتر از موجودی نمی‌توانید اضافه کنید.", 400

    cart_data[product_key] = current_quantity + 1

    session["cart"] = cart_data

    return redirect(
        url_for("cart")
    )


@app.post("/cart/remove/<int:product_id>")
def cart_remove(product_id):

    cart_data = session.get(
        "cart",
        {}
    )

    product_key = str(product_id)

    if product_key in cart_data:
        del cart_data[product_key]

    session["cart"] = cart_data

    return redirect(
        url_for("cart")
    )


@app.post("/cart/clear")
def cart_clear():

    session["cart"] = {}

    return redirect(
        url_for("cart")
    )


# =========================================================
# Checkout
# =========================================================

@app.route("/checkout", methods=["GET", "POST"])
def checkout():

    if request.method == "GET":
        return render_template(
            "checkout.html"
        )

    customer_name = request.form.get(
        "customer_name",
        ""
    ).strip()

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    address = request.form.get(
        "address",
        ""
    ).strip()

    if not customer_name or not phone or not address:
        return "لطفاً همه اطلاعات را وارد کنید.", 400

    cart_data = session.get(
        "cart",
        {}
    )

    if not cart_data:
        return "سبد خرید خالی است.", 400

    total = 0

    conn = get_db()

    for product_id, quantity in cart_data.items():

        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            conn.close()
            return "تعداد محصول نامعتبر است.", 400

        if quantity <= 0:
            conn.close()
            return "تعداد محصول نامعتبر است.", 400

        product_item = conn.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()

        if not product_item:
            continue

        if quantity > product_item["stock"]:
            conn.close()
            return "موجودی یکی از محصولات کافی نیست.", 400

        price = product_item["price"]
        discount = product_item["discount"] or 0

        final_price = int(
            price * (100 - discount) / 100
        )

        total += final_price * quantity

    cursor = conn.execute("""
        INSERT INTO orders
        (customer_name, phone, address, total, status)
        VALUES (?, ?, ?, ?, ?)
    """, (
        customer_name,
        phone,
        address,
        total,
        "جدید"
    ))

    order_id = cursor.lastrowid

    for product_id, quantity in cart_data.items():

        conn.execute("""
            UPDATE products
            SET stock = stock - ?
            WHERE id = ?
        """, (
            quantity,
            product_id
        ))

    conn.commit()
    conn.close()

    session["cart"] = {}

    return render_template(
        "success.html",
        order_id=order_id
    )


# =========================================================
# Admin Login
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db()

        admin = conn.execute(
            """
            SELECT *
            FROM admins
            WHERE username = ?
            LIMIT 1
            """,
            (username,)
        ).fetchone()

        conn.close()

        if admin and check_password_hash(
            admin["password"],
            password
        ):

            session.clear()
            session["admin_logged_in"] = True
            session.permanent = True

            return redirect(
                url_for("admin")
            )

        return render_template(
            "admin_login.html",
            error="نام کاربری یا رمز عبور اشتباه است."
        )

    return render_template(
        "admin_login.html"
    )


# =========================================================
# Admin Logout
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# Admin Dashboard
# =========================================================

@app.route("/admin")
def admin():

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    products = conn.execute("""
        SELECT *
        FROM products
        ORDER BY id DESC
    """).fetchall()

    orders = conn.execute("""
        SELECT *
        FROM orders
        ORDER BY id DESC
    """).fetchall()

    ads = conn.execute("""
        SELECT *
        FROM ads
        ORDER BY id DESC
    """).fetchall()

    support_requests = conn.execute("""
        SELECT *
        FROM support_requests
        WHERE status != 'حل شد'
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        products=products,
        orders=orders,
        ads=ads,
        support_requests=support_requests
    )


# =========================================================
# Admin Orders
# =========================================================

@app.post("/admin/order/delete/<int:order_id>")
def admin_delete_order(order_id):

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    conn.execute(
        "DELETE FROM orders WHERE id = ?",
        (order_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


@app.post("/admin/order/status/<int:order_id>")
def admin_update_order_status(order_id):

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    status = request.form.get(
        "status",
        ""
    ).strip()

    allowed_statuses = [
        "جدید",
        "در حال پردازش",
        "ارسال شد",
        "تحویل شد"
    ]

    if status not in allowed_statuses:
        return "وضعیت سفارش نامعتبر است.", 400

    conn = get_db()

    conn.execute("""
        UPDATE orders
        SET status = ?
        WHERE id = ?
    """, (
        status,
        order_id
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


# =========================================================
# Admin Products
# =========================================================

@app.post("/admin/product/add")
def admin_add_product():

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    name = request.form.get(
        "name",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    price = request.form.get(
        "price",
        "0"
    )

    discount = request.form.get(
        "discount",
        "0"
    )

    category = request.form.get(
        "category",
        ""
    ).strip()

    image = request.form.get(
        "image",
        ""
    ).strip()

    stock = request.form.get(
        "stock",
        "0"
    )

    try:
        price = int(price)
        discount = int(discount)
        stock = int(stock)
    except ValueError:
        return "مقادیر عددی صحیح نیستند.", 400

    if not name or price < 0:
        return "اطلاعات محصول صحیح نیست.", 400

    if discount < 0 or discount > 100:
        return "تخفیف باید بین ۰ تا ۱۰۰ باشد.", 400

    if stock < 0:
        return "موجودی نمی‌تواند منفی باشد.", 400

    conn = get_db()

    conn.execute("""
        INSERT INTO products
        (name, description, price, discount, category, image, stock)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        description,
        price,
        discount,
        category,
        image,
        stock
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


@app.post(
    "/admin/product/delete/<int:product_id>"
)
def admin_delete_product(product_id):

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    conn.execute(
        "DELETE FROM products WHERE id = ?",
        (product_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


# =========================================================
# Admin Ads
# =========================================================

@app.post("/admin/ad/add")
def admin_add_ad():

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    title = request.form.get(
        "title",
        ""
    ).strip()

    text = request.form.get(
        "text",
        ""
    ).strip()

    image = request.form.get(
        "image",
        ""
    ).strip()

    link = request.form.get(
        "link",
        ""
    ).strip()

    if not title:
        return "عنوان تبلیغ الزامی است.", 400

    conn = get_db()

    conn.execute("""
        INSERT INTO ads
        (title, text, image, link)
        VALUES (?, ?, ?, ?)
    """, (
        title,
        text,
        image,
        link
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


@app.post("/admin/ad/delete/<int:ad_id>")
def admin_delete_ad(ad_id):

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    conn.execute(
        "DELETE FROM ads WHERE id = ?",
        (ad_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


# =========================================================
# Admin Account
# =========================================================

@app.post("/admin/account")
def change_admin_account():

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    new_username = request.form.get(
        "new_username",
        ""
    ).strip()

    old_password = request.form.get(
        "old_password",
        ""
    )

    new_password = request.form.get(
        "new_password",
        ""
    )

    if len(new_username) < 3:
        return "نام کاربری باید حداقل ۳ کاراکتر باشد.", 400

    if new_password and len(new_password) < 6:
        return "رمز عبور جدید باید حداقل ۶ کاراکتر باشد.", 400

    conn = get_db()

    admin = conn.execute(
        "SELECT * FROM admins LIMIT 1"
    ).fetchone()

    if not admin:
        conn.close()
        return "حساب مدیر پیدا نشد.", 404

    if not check_password_hash(
        admin["password"],
        old_password
    ):
        conn.close()
        return "رمز عبور فعلی اشتباه است.", 400

    duplicate = conn.execute(
        """
        SELECT id
        FROM admins
        WHERE username = ?
        AND id != ?
        LIMIT 1
        """,
        (
            new_username,
            admin["id"]
        )
    ).fetchone()

    if duplicate:
        conn.close()
        return "این نام کاربری قبلاً استفاده شده است.", 400

    if new_password:
        password_hash = generate_password_hash(
            new_password
        )
    else:
        password_hash = admin["password"]

    conn.execute("""
        UPDATE admins
        SET username = ?, password = ?
        WHERE id = ?
    """, (
        new_username,
        password_hash,
        admin["id"]
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


# =========================================================
# پشتیبانی آنلاین
# =========================================================

SUPPORT_CATEGORIES = [
    "موبایل",
    "لپ‌تاپ",
    "پوشاک",
    "لوازم خانگی",
    "دیجیتال",
    "زیبایی",
    "سایر"
]


def support_now():
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


@app.post("/support/create")
def support_create():

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    category = request.form.get(
        "category",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    if not phone or not description:
        return "شماره تلفن و توضیحات الزامی است.", 400

    if category not in SUPPORT_CATEGORIES:
        return "دسته‌بندی نامعتبر است.", 400

    if len(phone) > 30:
        return "شماره تلفن بیش از حد مجاز است.", 400

    if len(description) > 2000:
        return "توضیحات بیش از حد مجاز است.", 400

    now = support_now()

    conn = get_db()

    cur = conn.execute("""
        INSERT INTO support_requests
        (
            token,
            phone,
            category,
            description,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        secrets.token_urlsafe(18),
        phone,
        category,
        description,
        "در حال پیگیری",
        now,
        now
    ))

    request_id = cur.lastrowid

    conn.execute("""
        INSERT INTO support_messages
        (
            request_id,
            sender,
            message,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        request_id,
        "customer",
        description,
        now
    ))

    conn.commit()
    conn.close()

    session["support_request_id"] = request_id

    return redirect(
        url_for("home")
    )


@app.get("/support/data")
def support_data():

    request_id = session.get(
        "support_request_id"
    )

    if not request_id:
        return {
            "exists": False
        }

    conn = get_db()

    support = conn.execute(
        """
        SELECT *
        FROM support_requests
        WHERE id = ?
        """,
        (request_id,)
    ).fetchone()

    if not support:
        conn.close()

        return {
            "exists": False
        }

    messages = conn.execute(
        """
        SELECT
            sender,
            message,
            created_at
        FROM support_messages
        WHERE request_id = ?
        ORDER BY id
        """,
        (request_id,)
    ).fetchall()

    conn.close()

    return {
        "exists": True,
        "request_id": support["id"],
        "phone": support["phone"],
        "category": support["category"],
        "description": support["description"],
        "status": support["status"],
        "created_at": support["created_at"],
        "updated_at": support["updated_at"],
        "messages": [
            {
                "sender": m["sender"],
                "message": m["message"],
                "created_at": m["created_at"]
            }
            for m in messages
        ]
    }


@app.post("/support/message")
def support_message():

    request_id = session.get(
        "support_request_id"
    )

    message = request.form.get(
        "message",
        ""
    ).strip()

    if not request_id:
        return "درخواست پشتیبانی پیدا نشد.", 400

    if not message:
        return "پیام خالی است.", 400

    if len(message) > 2000:
        return "پیام بیش از حد مجاز است.", 400

    conn = get_db()

    support = conn.execute(
        """
        SELECT status
        FROM support_requests
        WHERE id = ?
        """,
        (request_id,)
    ).fetchone()

    if not support:
        conn.close()
        return "درخواست پیدا نشد.", 404

    if support["status"] == "حل شد":
        conn.close()
        return "این درخواست قبلاً حل شده است.", 400

    now = support_now()

    conn.execute(
        """
        INSERT INTO support_messages
        (
            request_id,
            sender,
            message,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            request_id,
            "customer",
            message,
            now
        )
    )

    conn.execute(
        """
        UPDATE support_requests
        SET status = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            "در حال پیگیری",
            now,
            request_id
        )
    )

    conn.commit()
    conn.close()

    return {
        "ok": True
    }


@app.post(
    "/admin/support/<int:request_id>/reply"
)
def admin_support_reply(request_id):

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    message = request.form.get(
        "message",
        ""
    ).strip()

    if not message:
        return "پیام خالی است.", 400

    if len(message) > 2000:
        return "پیام بیش از حد مجاز است.", 400

    conn = get_db()

    support = conn.execute(
        """
        SELECT id, status
        FROM support_requests
        WHERE id = ?
        """,
        (request_id,)
    ).fetchone()

    if not support:
        conn.close()
        return "درخواست پیدا نشد.", 404

    if support["status"] == "حل شد":
        conn.close()
        return "این درخواست حل شده است.", 400

    now = support_now()

    conn.execute(
        """
        INSERT INTO support_messages
        (
            request_id,
            sender,
            message,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            request_id,
            "admin",
            message,
            now
        )
    )

    conn.execute(
        """
        UPDATE support_requests
        SET status = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            "در انتظار پاسخ مشتری",
            now,
            request_id
        )
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


@app.post(
    "/admin/support/<int:request_id>/resolve"
)
def admin_support_resolve(request_id):

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    support = conn.execute(
        """
        SELECT id
        FROM support_requests
        WHERE id = ?
        """,
        (request_id,)
    ).fetchone()

    if not support:
        conn.close()
        return "درخواست پیدا نشد.", 404

    now = support_now()

    conn.execute(
        """
        INSERT INTO support_messages
        (
            request_id,
            sender,
            message,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            request_id,
            "admin",
            "پیگیری انجام شد؛ مشکل شما حل شد.",
            now
        )
    )

    conn.execute(
        """
        UPDATE support_requests
        SET status = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            "حل شد",
            now,
            request_id
        )
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


# =========================================================
# AI رایگان فروشگاه
# =========================================================

AI_CATEGORIES = {
    "موبایل": [
        "موبایل",
        "گوشی",
        "تلفن"
    ],
    "لپ‌تاپ": [
        "لپ تاپ",
        "لپ‌تاپ",
        "لپتاپ",
        "نوت بوک"
    ],
    "لوازم جانبی": [
        "هدفون",
        "هندزفری",
        "شارژر",
        "کابل",
        "لوازم جانبی"
    ],
    "پوشیدنی": [
        "ساعت",
        "ساعت هوشمند",
        "پوشیدنی"
    ],
    "دیجیتال": [
        "دیجیتال"
    ],
    "پوشاک": [
        "پوشاک",
        "لباس"
    ],
    "لوازم خانگی": [
        "لوازم خانگی",
        "خانه"
    ],
    "زیبایی": [
        "زیبایی"
    ]
}


def ai_clean_text(text):
    text = str(text or "").lower().strip()

    replacements = {
        "ي": "ی",
        "ك": "ک",
        "ۀ": "ه",
        "ة": "ه",
        "‌": " "
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new
        )

    return re.sub(
        r"\s+",
        " ",
        text
    )


def ai_find_category(message):
    message = ai_clean_text(
        message
    )

    for category, keywords in AI_CATEGORIES.items():

        for keyword in keywords:

            if ai_clean_text(keyword) in message:
                return category

    return None


def ai_format_price(price):
    return f"{int(price):,}"


def ai_product_text(product):

    price = int(
        product["price"] or 0
    )

    discount = int(
        product["discount"] or 0
    )

    stock = int(
        product["stock"] or 0
    )

    final_price = int(
        price * (100 - discount) / 100
    )

    text = (
        f"**{product['name']}**\n"
    )

    text += (
        f"دسته‌بندی: "
        f"{product['category'] or 'عمومی'}\n"
    )

    if discount > 0:

        text += (
            f"قیمت اصلی: "
            f"{ai_format_price(price)} تومان\n"
        )

        text += (
            f"تخفیف: {discount}٪\n"
        )

        text += (
            f"قیمت نهایی: "
            f"{ai_format_price(final_price)} تومان\n"
        )

    else:

        text += (
            f"قیمت: "
            f"{ai_format_price(final_price)} تومان\n"
        )

    if stock > 0:

        text += (
            f"موجودی: {stock} عدد"
        )

    else:

        text += "وضعیت: ناموجود"

    return text


def ai_answer(message):

    message = ai_clean_text(
        message
    )

    if not message:
        return (
            "سؤالت را بنویس تا محصولات "
            "فروشگاه را برایت بررسی کنم."
        )

    conn = get_db()

    products = conn.execute("""
        SELECT *
        FROM products
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    if not products:
        return (
            "در حال حاضر محصولی "
            "در فروشگاه ثبت نشده است."
        )

    # -----------------------------------------------------
    # سلام
    # -----------------------------------------------------

    greetings = [
        "سلام",
        "درود",
        "خوبی",
        "سلام وقت بخیر",
        "وقت بخیر"
    ]

    if any(
        word in message
        for word in greetings
    ):

        return (
            "سلام. من دستیار هوشمند فروشگاه هستم.\n\n"
            "می‌توانم محصولات، قیمت، تخفیف، "
            "موجودی و دسته‌بندی‌ها را بررسی کنم.\n\n"
            "مثلاً بپرس:\n"
            "«چه گوشی‌هایی دارید؟»\n"
            "«لپ‌تاپ می‌خوام»\n"
            "«چه محصولاتی تخفیف دارند؟»"
        )

    # -----------------------------------------------------
    # تخفیف
    # -----------------------------------------------------

    if any(
        word in message
        for word in [
            "تخفیف",
            "تخفیف دار",
            "تخفیف‌دار",
            "ارزان شده",
            "پیشنهاد"
        ]
    ):

        discounted = [
            p
            for p in products
            if (
                (p["discount"] or 0) > 0
                and
                (p["stock"] or 0) > 0
            )
        ]

        if not discounted:
            return (
                "در حال حاضر محصول تخفیف‌داری "
                "موجود نیست."
            )

        discounted.sort(
            key=lambda p: p["discount"] or 0,
            reverse=True
        )

        result = (
            "این محصولات در حال حاضر "
            "تخفیف دارند:\n\n"
        )

        for product_item in discounted[:5]:

            result += (
                ai_product_text(
                    product_item
                )
                + "\n\n"
            )

        return result.strip()

    # -----------------------------------------------------
    # دسته‌بندی
    # -----------------------------------------------------

    category = ai_find_category(
        message
    )

    if category:

        category_products = [
            p
            for p in products
            if ai_clean_text(
                p["category"] or ""
            )
            ==
            ai_clean_text(
                category
            )
        ]

        if not category_products:

            category_products = [
                p
                for p in products
                if category in (
                    p["category"] or ""
                )
            ]

        if not category_products:

            return (
                f"در دسته‌بندی "
                f"«{category}» "
                f"محصولی پیدا نکردم."
            )

        available = [
            p
            for p in category_products
            if (p["stock"] or 0) > 0
        ]

        if not available:

            return (
                f"محصولی از دسته "
                f"«{category}» "
                f"در حال حاضر موجود نیست."
            )

        result = (
            f"این محصولات از دسته "
            f"«{category}» موجود هستند:\n\n"
        )

        for product_item in available[:5]:

            result += (
                ai_product_text(
                    product_item
                )
                + "\n\n"
            )

        return result.strip()

    # -----------------------------------------------------
    # جستجوی هوشمند در نام و توضیحات
    # -----------------------------------------------------

    stop_words = {
        "چی",
        "چه",
        "دارید",
        "دارین",
        "دارم",
        "میخوام",
        "می‌خوام",
        "میخواهم",
        "میشه",
        "لطفا",
        "لطفاً",
        "معرفی",
        "کن",
        "کنید",
        "کنین",
        "محصول",
        "محصولات",
        "قیمت",
        "چنده",
        "چند",
        "است",
        "هست",
        "هستند",
        "موجود",
        "رو",
        "را",
        "از",
        "برای",
        "به",
        "یک"
    }

    words = [
        word
        for word in message.split()
        if (
            word not in stop_words
            and len(word) >= 2
        )
    ]

    matches = []

    for product_item in products:

        searchable = ai_clean_text(
            f"{product_item['name']} "
            f"{product_item['description']} "
            f"{product_item['category']}"
        )

        score = 0

        for word in words:

            if word in searchable:
                score += 1

        if score > 0:

            matches.append(
                (
                    score,
                    product_item
                )
            )

    matches.sort(
        key=lambda item: item[0],
        reverse=True
    )

    if matches:

        result = (
            "چند محصول مرتبط "
            "با سؤال شما پیدا کردم:\n\n"
        )

        for _, product_item in matches[:5]:

            result += (
                ai_product_text(
                    product_item
                )
                + "\n\n"
            )

        return result.strip()

    # -----------------------------------------------------
    # موجودی کلی
    # -----------------------------------------------------

    if any(
        word in message
        for word in [
            "موجودی",
            "موجوده",
            "موجود هست",
            "موجود دارید"
        ]
    ):

        available = [
            p
            for p in products
            if (p["stock"] or 0) > 0
        ]

        return (
            f"در حال حاضر "
            f"{len(available)} محصول "
            f"موجود در فروشگاه داریم."
        )

    # -----------------------------------------------------
    # پاسخ پیش‌فرض
    # -----------------------------------------------------

    return (
        "سؤال شما را دقیق متوجه نشدم.\n\n"
        "می‌توانید درباره این موارد بپرسید:\n"
        "• گوشی و موبایل\n"
        "• لپ‌تاپ\n"
        "• قیمت محصولات\n"
        "• محصولات تخفیف‌دار\n"
        "• موجودی کالا\n"
        "• یک محصول خاص"
    )


@app.post("/ai/chat")
def ai_chat():

    data = request.get_json(
        silent=True
    ) or {}

    message = str(
        data.get(
            "message",
            ""
        )
    ).strip()

    if len(message) > 500:

        return {
            "ok": False,
            "answer": (
                "پیام شما بیش از "
                "حد مجاز طولانی است."
            )
        }, 400

    return {
        "ok": True,
        "answer": ai_answer(message)
    }


# =========================================================
# Robots.txt
# =========================================================

@app.route("/robots.txt")
def robots():

    return """User-agent: *
Allow: /

Sitemap: https://foroshgah-man.onrender.com/sitemap.xml
""", 200, {
        "Content-Type": "text/plain"
    }


# =========================================================
# Sitemap
# =========================================================

@app.route("/sitemap.xml")
def sitemap():

    pages = [
        url_for(
            "home",
            _external=True
        ),

        url_for(
            "products_page",
            _external=True
        ),

        url_for(
            "offers",
            _external=True
        ),

        url_for(
            "categories_page",
            _external=True
        )
    ]

    conn = get_db()

    products = conn.execute(
        "SELECT id FROM products"
    ).fetchall()

    categories = conn.execute(
        """
        SELECT DISTINCT category
        FROM products
        WHERE category != ''
        """
    ).fetchall()

    conn.close()

    for product_item in products:

        pages.append(
            url_for(
                "product",
                product_id=product_item["id"],
                _external=True
            )
        )

    for category_item in categories:

        pages.append(
            url_for(
                "category",
                category=category_item["category"],
                _external=True
            )
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
    )

    xml += (
        '<urlset '
        'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    )

    for page in pages:

        xml += (
            f"<url><loc>{page}</loc></url>"
        )

    xml += "</urlset>"

    return xml, 200, {
        "Content-Type": "application/xml"
    }


# =========================================================
# Start
# =========================================================

init_db()


if __name__ == "__main__":

    init_db()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
