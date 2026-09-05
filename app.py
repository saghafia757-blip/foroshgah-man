from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
import time


app = Flask(__name__)


# =========================================================
# Google verification
# =========================================================

@app.route("/google35cefc4bc1a94ac4.html")
def google_verification():
    return "google-site-verification: google35cefc4bc1a94ac4.html"


# =========================================================
# تنظیمات امنیتی
# =========================================================

SECRET_KEY = os.environ.get("SECRET_KEY")

if not SECRET_KEY:
    SECRET_KEY = os.urandom(32).hex()

app.secret_key = SECRET_KEY

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=3600
)


@app.after_request
def security_headers(response):

    response.headers["X-Content-Type-Options"] = "nosniff"

    response.headers["X-Frame-Options"] = "SAMEORIGIN"

    response.headers["Referrer-Policy"] = (
        "strict-origin-when-cross-origin"
    )

    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )

    return response


# =========================================================
# Database
# =========================================================

DATABASE = "store.db"


def get_db():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# Login protection
# =========================================================

LOGIN_ATTEMPTS = {}

MAX_LOGIN_ATTEMPTS = 5

LOGIN_BLOCK_TIME = 300


# =========================================================
# ساخت دیتابیس
# =========================================================

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

    # ساخت مدیر پیش‌فرض فقط در صورتی که مدیر وجود نداشته باشد
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

    # محصولات اولیه
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

    # تبلیغ اولیه
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
# بررسی ورود مدیر
# =========================================================

def admin_required():

    return session.get(
        "admin_logged_in"
    ) is True


# =========================================================
# صفحه اصلی + فیلتر محصولات
# =========================================================

@app.route("/")
def home():

    conn = get_db()

    search = request.args.get(
        "search",
        ""
    ).strip()

    category_filter = request.args.get(
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

    sort = request.args.get(
        "sort",
        "newest"
    ).strip()

    in_stock = request.args.get(
        "in_stock",
        ""
    ).strip()

    query = """
        SELECT * FROM products
        WHERE 1=1
    """

    params = []

    # جستجو
    if search:

        query += """
            AND (
                name LIKE ?
                OR description LIKE ?
                OR category LIKE ?
            )
        """

        search_value = f"%{search}%"

        params.extend([
            search_value,
            search_value,
            search_value
        ])

    # دسته‌بندی
    if category_filter:

        query += """
            AND category = ?
        """

        params.append(category_filter)

    # حداقل قیمت
    if min_price:

        try:

            min_price_value = int(min_price)

            if min_price_value >= 0:

                query += """
                    AND price >= ?
                """

                params.append(min_price_value)

            else:
                min_price = ""

        except ValueError:

            min_price = ""

    # حداکثر قیمت
    if max_price:

        try:

            max_price_value = int(max_price)

            if max_price_value >= 0:

                query += """
                    AND price <= ?
                """

                params.append(max_price_value)

            else:
                max_price = ""

        except ValueError:

            max_price = ""

    # فقط محصولات موجود
    if in_stock == "1":

        query += """
            AND stock > 0
        """

    # مرتب‌سازی امن
    allowed_sorts = {

        "newest": "id DESC",

        "oldest": "id ASC",

        "cheap": "price ASC",

        "expensive": "price DESC",

        "discount": "discount DESC"
    }

    order_by = allowed_sorts.get(
        sort,
        "id DESC"
    )

    query += f"""
        ORDER BY {order_by}
    """

    products = conn.execute(
        query,
        params
    ).fetchall()

    ads = conn.execute("""
        SELECT * FROM ads
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

        selected_category=category_filter,

        min_price=min_price,

        max_price=max_price,

        sort=sort,

        in_stock=in_stock
    )


# =========================================================
# جستجو
# =========================================================

@app.route("/search")
def search():

    return redirect(
        url_for(
            "home",
            search=request.args.get(
                "q",
                ""
            )
        )
    )


# =========================================================
# محصول
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
# دسته‌بندی
# =========================================================

@app.route("/category/<category>")
def category(category):

    conn = get_db()

    products = conn.execute("""
        SELECT * FROM products
        WHERE category = ?
        ORDER BY id DESC
    """, (
        category,
    )).fetchall()

    ads = conn.execute(
        "SELECT * FROM ads ORDER BY id DESC"
    ).fetchall()

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

        max_price="",

        sort="newest",

        in_stock=""
    )


# =========================================================
# پیشنهادهای ویژه
# =========================================================

@app.route("/offers")
def offers():

    conn = get_db()

    products = conn.execute("""
        SELECT * FROM products
        WHERE discount > 0
        ORDER BY discount DESC
    """).fetchall()

    ads = conn.execute(
        "SELECT * FROM ads ORDER BY id DESC"
    ).fetchall()

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

        max_price="",

        sort="discount",

        in_stock=""
    )


# =========================================================
# محصولات
# =========================================================

@app.route("/categories")
def categories_page():

    return redirect(
        url_for("products_page")
    )


@app.route("/products")
def products_page():

    return redirect(
        url_for("home")
    )


# =========================================================
# سبد خرید
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


# =========================================================
# اضافه کردن به سبد
# =========================================================

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

    if current_quantity >= product_item["stock"]:

        return "بیشتر از موجودی نمی‌توانید اضافه کنید.", 400

    cart_data[product_key] = (
        current_quantity + 1
    )

    session["cart"] = cart_data

    return redirect(
        url_for("cart")
    )


# =========================================================
# حذف محصول از سبد
# =========================================================

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


# =========================================================
# خالی کردن سبد
# =========================================================

@app.post("/cart/clear")
def cart_clear():

    session["cart"] = {}

    return redirect(
        url_for("cart")
    )


# =========================================================
# پرداخت / ثبت سفارش
# =========================================================

@app.route(
    "/checkout",
    methods=["GET", "POST"]
)
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
# ورود مدیر
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    client_ip = request.remote_addr or "unknown"

    attempt_data = LOGIN_ATTEMPTS.get(
        client_ip,
        {
            "count": 0,
            "blocked_until": 0
        }
    )

    # بررسی محدودیت ورود
    if attempt_data["blocked_until"] > time.time():

        return (
            "تعداد تلاش‌های ورود بیش از حد مجاز است. "
            "لطفاً چند دقیقه بعد دوباره تلاش کنید.",
            429
        )

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
            SELECT * FROM admins
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

            # پاک کردن تلاش‌های ناموفق
            LOGIN_ATTEMPTS.pop(
                client_ip,
                None
            )

            # پاک کردن Session قبلی
            session.clear()

            session["admin_logged_in"] = True

            session.permanent = True

            return redirect(
                url_for("admin")
            )

        # ورود ناموفق
        attempt_data["count"] += 1

        if attempt_data["count"] >= MAX_LOGIN_ATTEMPTS:

            attempt_data["blocked_until"] = (
                time.time() + LOGIN_BLOCK_TIME
            )

            attempt_data["count"] = 0

        LOGIN_ATTEMPTS[client_ip] = attempt_data

        return render_template(
            "admin_login.html",

            error="نام کاربری یا رمز عبور اشتباه است."
        )

    return render_template(
        "admin_login.html"
    )


# =========================================================
# خروج مدیر
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# پنل مدیریت
# =========================================================

@app.route("/admin")
def admin():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    products = conn.execute("""
        SELECT * FROM products
        ORDER BY id DESC
    """).fetchall()

    orders = conn.execute("""
        SELECT * FROM orders
        ORDER BY id DESC
    """).fetchall()

    ads = conn.execute("""
        SELECT * FROM ads
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin.html",

        products=products,

        orders=orders,

        ads=ads
    )


# =========================================================
# حذف سفارش
# =========================================================

@app.post(
    "/admin/order/delete/<int:order_id>"
)
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


# =========================================================
# تغییر وضعیت سفارش
# =========================================================

@app.post(
    "/admin/order/status/<int:order_id>"
)
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
# افزودن محصول
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


# =========================================================
# حذف محصول
# =========================================================

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
# تبلیغات
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


# =========================================================
# حذف تبلیغ
# =========================================================

@app.post(
    "/admin/ad/delete/<int:ad_id>"
)
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
# تغییر حساب مدیر
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
        SELECT id FROM admins
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
# robots.txt
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
# sitemap.xml
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

    categories = conn.execute("""
        SELECT DISTINCT category
        FROM products
        WHERE category != ''
    """).fetchall()

    conn.close()

    for product in products:

        pages.append(
            url_for(
                "product",
                product_id=product["id"],
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
            f"<url>"
            f"<loc>{page}</loc>"
            f"</url>"
        )

    xml += "</urlset>"

    return xml, 200, {
        "Content-Type": "application/xml"
    }


# =========================================================
# اجرای برنامه
# =========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
