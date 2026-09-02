@app.post("/admin/order/status/<int:order_id>")
def admin_update_order_status(order_id):

    if not admin_required():
        return redirect(url_for("admin_login"))

    status = request.form.get("status", "").strip()

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

    return redirect(url_for("admin"))
