import os
import sqlite3

from flask import Flask, render_template, request, jsonify

# Import Upstash Redis
try:
    from upstash_redis import Redis
except ImportError:
    Redis = None


app = Flask(__name__)

DATABASE = "visitor.db"

# ==========================================
# UPSTASH REDIS - VERCEL
# ==========================================

redis_url = os.environ.get("KV_REST_API_URL")
redis_token = os.environ.get("KV_REST_API_TOKEN")

if Redis and redis_url and redis_token:
    redis_client = Redis(url=redis_url, token=redis_token)
else:
    redis_client = None


# ==========================================
# MASTER KATEGORI BARANG
# ==========================================

CATEGORY_LABELS = {
    "obat": "Obat",
    "obat_tradisional": "Obat Tradisional",
    "kosmetik": "Kosmetika",
    "suplemen": "Suplemen Kesehatan",
    "pkmk": "Pangan Olahan Medis Khusus (PKMK)",
    "makanan": "Pangan Olahan Lain"
}


# ==========================================
# MASTER BATASAN BARANG
# ==========================================

LIMITS = {
    "suplemen": {
        "limit": 5,
        "unit": "pcs",
        "name": "Suplemen Kesehatan / Obat Bahan Alam / Obat Kuasi"
    },
    "kosmetik": {
        "limit": 20,
        "unit": "pcs",
        "name": "Kosmetik"
    },
    "obat_tradisional": {
        "limit": 5,
        "unit": "pcs",
        "name": "Obat Bahan Alam / Obat Kuasi / Obat Tradisional"
    },
    "makanan": {
        "limit": 5,
        "unit": "kg",
        "name": "Pangan Olahan Lain (Kecuali Minuman Beralkohol)"
    },
    "tablet_kapsul": {
        "limit": 30,
        "unit": "pcs",
        "name": "Obat Sediaan Padat (Tablet / Kapsul)"
    },
    "krim_cairan_aerosol": {
        "limit": 3,
        "unit": "pcs",
        "name": "Obat Sediaan Semipadat, Cairan, dan Aerosol"
    }
}


MAIN_OPTIONS = [
    {"id": "obat", "icon": "💊", "text": "Obat"},
    {"id": "obat_tradisional", "icon": "🌿", "text": "Obat Tradisional"},
    {"id": "kosmetik", "icon": "💄", "text": "Kosmetika"},
    {"id": "suplemen", "icon": "💪🏻", "text": "Suplemen Kesehatan"},
    {"id": "pkmk", "icon": "🏥", "text": "Pangan Olahan Medis Khusus (PKMK)"},
    {
        "id": "makanan",
        "icon": "🧃",
        "text": "Pangan Olahan Lain",
        "note": "kecuali minuman beralkohol"
    }
]


AFTER_ACTION_OPTIONS = [
    {"id": "check_another", "text": "🔄 Cek Barang Lain"},
    {"id": "finish", "text": "✅ Selesai"}
]


# ==========================================
# DATABASE SQLITE
# ==========================================

def init_db():
    """Inisialisasi database SQLite lokal."""

    if redis_client is not None:
        return

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Tabel pengunjung
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visitor (
            id INTEGER PRIMARY KEY,
            count INTEGER NOT NULL
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM visitor")

    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO visitor (id, count) VALUES (1, 0)"
        )

    # Tabel feedback
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY,
            useful_count INTEGER NOT NULL DEFAULT 0,
            not_useful_count INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM feedback")

    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO feedback
            (id, useful_count, not_useful_count)
            VALUES (1, 0, 0)
        """)

    # Tabel statistik kategori
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_stats (
            category_id TEXT PRIMARY KEY,
            category_name TEXT NOT NULL,
            total_count INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Memastikan keenam kategori tersedia
    for category_id, category_name in CATEGORY_LABELS.items():
        cursor.execute("""
            INSERT OR IGNORE INTO category_stats
            (category_id, category_name, total_count)
            VALUES (?, ?, 0)
        """, (category_id, category_name))

    conn.commit()
    conn.close()


init_db()


# ==========================================
# FUNGSI STATISTIK KATEGORI
# ==========================================

def increment_category(category_id):
    """Menambahkan satu hitungan untuk kategori yang dipilih."""

    if category_id not in CATEGORY_LABELS:
        return False

    # Vercel menggunakan Redis
    if redis_client is not None:
        try:
            redis_client.incr(f"category_{category_id}")
            return True

        except Exception as e:
            print("Error Redis Category:", e)
            return False

    # Lokal menggunakan SQLite
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE category_stats
            SET total_count = total_count + 1
            WHERE category_id = ?
        """, (category_id,))

        conn.commit()
        conn.close()

        return True

    except Exception as e:
        print("Error SQLite Category:", e)
        return False


# ==========================================
# HALAMAN UTAMA
# ==========================================

@app.route("/")
def index():
    return render_template("index.html")


# ==========================================
# API TOTAL PENGUNJUNG
# ==========================================

@app.route("/api/visitor_count", methods=["GET"])
def visitor_count():

    if redis_client is not None:
        try:
            current_count = redis_client.incr("visitor_count")
            return jsonify({"count": int(current_count)})

        except Exception as e:
            print("Error Redis Visitor:", e)
            return jsonify({"count": 0})

    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT count FROM visitor WHERE id = 1"
        )

        row = cursor.fetchone()
        current_count = (row[0] if row else 0) + 1

        cursor.execute("""
            UPDATE visitor SET count = ?
            WHERE id = 1
        """, (current_count,))

        conn.commit()
        conn.close()

        return jsonify({"count": current_count})

    except Exception as e:
        print("Error SQLite Visitor:", e)
        return jsonify({"count": 0})


# ==========================================
# API STATISTIK FEEDBACK
# ==========================================

@app.route("/api/feedback_stats", methods=["GET"])
def get_feedback_stats():

    if redis_client is not None:
        try:
            useful = int(redis_client.get("feedback_useful") or 0)
            not_useful = int(
                redis_client.get("feedback_not_useful") or 0
            )

            return jsonify({
                "useful": useful,
                "not_useful": not_useful
            })

        except Exception as e:
            print("Error Redis Feedback Stats:", e)
            return jsonify({
                "useful": 0,
                "not_useful": 0
            })

    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT useful_count, not_useful_count
            FROM feedback
            WHERE id = 1
        """)

        row = cursor.fetchone()
        conn.close()

        if row:
            return jsonify({
                "useful": row[0],
                "not_useful": row[1]
            })

        return jsonify({
            "useful": 0,
            "not_useful": 0
        })

    except Exception as e:
        print("Error SQLite Feedback Stats:", e)
        return jsonify({
            "useful": 0,
            "not_useful": 0
        })


# ==========================================
# API MENYIMPAN FEEDBACK
# ==========================================

@app.route("/api/feedback", methods=["POST"])
def save_feedback():

    data = request.get_json(silent=True) or {}
    vote = data.get("vote")

    if vote not in ["useful", "not_useful"]:
        return jsonify({
            "type": "error",
            "message": "Pilihan tidak valid."
        }), 400

    if redis_client is not None:
        try:
            key = (
                "feedback_useful"
                if vote == "useful"
                else "feedback_not_useful"
            )

            redis_client.incr(key)

            useful = int(redis_client.get("feedback_useful") or 0)
            not_useful = int(
                redis_client.get("feedback_not_useful") or 0
            )

            return jsonify({
                "status": "success",
                "vote": vote,
                "useful": useful,
                "not_useful": not_useful
            })

        except Exception as e:
            print("Error Redis Feedback:", e)
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        column = (
            "useful_count"
            if vote == "useful"
            else "not_useful_count"
        )

        cursor.execute(f"""
            UPDATE feedback
            SET {column} = {column} + 1
            WHERE id = 1
        """)

        conn.commit()

        cursor.execute("""
            SELECT useful_count, not_useful_count
            FROM feedback
            WHERE id = 1
        """)

        row = cursor.fetchone()
        conn.close()

        return jsonify({
            "status": "success",
            "vote": vote,
            "useful": row[0],
            "not_useful": row[1]
        })

    except Exception as e:
        print("Error SQLite Feedback:", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ==========================================
# API STATISTIK ENAM KATEGORI
# ==========================================

@app.route("/api/category_stats", methods=["GET"])
def get_category_stats():

    stats = {
        category_id: 0
        for category_id in CATEGORY_LABELS
    }

    if redis_client is not None:
        try:
            for category_id in CATEGORY_LABELS:
                value = redis_client.get(
                    f"category_{category_id}"
                )

                stats[category_id] = int(value or 0)

            return jsonify(stats)

        except Exception as e:
            print("Error Redis Category Stats:", e)
            return jsonify(stats), 500

    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT category_id, total_count
            FROM category_stats
        """)

        rows = cursor.fetchall()
        conn.close()

        for category_id, total_count in rows:
            stats[category_id] = total_count

        return jsonify(stats)

    except Exception as e:
        print("Error SQLite Category Stats:", e)
        return jsonify(stats), 500


# ==========================================
# API MENU UTAMA
# ==========================================

@app.route("/api/main_menu", methods=["GET"])
def main_menu():

    return jsonify({
        "type": "question",
        "message": "Silakan pilih kategori barang berikutnya yang ingin Anda cek:",
        "options": MAIN_OPTIONS
    })


# ==========================================
# API MEMILIH KATEGORI
# ==========================================

@app.route("/api/select_category", methods=["POST"])
def select_category():

    data = request.get_json(silent=True) or {}
    cat = data.get("category")

    # HITUNG KATEGORI UTAMA YANG DIPILIH
    if cat in CATEGORY_LABELS:
        increment_category(cat)

    # KATEGORI OBAT
    if cat == "obat":

        return jsonify({
            "type": "question",
            "message": "Anda memilih Obat. **Pilih jenis obat yang Anda bawa:**",
            "options": [
                {"id": "narkotika", "text": "Narkotika"},
                {"id": "psikotropika", "text": "Psikotropika"},
                {
                    "id": "tablet_kapsul",
                    "text": "Obat Sediaan Padat (Tablet/Kapsul)"
                },
                {
                    "id": "krim_cairan_aerosol",
                    "text": "Obat Sediaan Semipadat, Cairan, & Aerosol"
                }
            ]
        })

    # KATEGORI PKMK
    elif cat == "pkmk":

        return jsonify({
            "type": "question_bool",
            "item_key": "pkmk",
            "title": "Produk Pangan Olahan untuk Keperluan Medis Khusus (PKMK)",
            "message": "Apakah Anda membawa **Resep Dokter** untuk produk PKMK ini?",
            "options": [
                {
                    "id": "pkmk_ya",
                    "text": "Ya, membawa resep dokter"
                },
                {
                    "id": "pkmk_tidak",
                    "text": "Tidak membawa resep dokter"
                }
            ]
        })

    # KATEGORI DENGAN BATASAN JUMLAH
    elif cat in LIMITS:

        item = LIMITS[cat]

        return jsonify({
            "type": "input_quantity",
            "item_key": cat,
            "title": item["name"],
            "message": (
                f"Masukkan jumlah **{item['name']}** "
                f"yang Anda bawa (dalam {item['unit']}):"
            )
        })

    return jsonify({
        "type": "error",
        "message": "Pilihan tidak valid."
    }), 400


# ==========================================
# API MEMILIH JENIS OBAT
# ==========================================

@app.route("/api/select_drug_type", methods=["POST"])
def select_drug_type():

    data = request.get_json(silent=True) or {}
    drug_type = data.get("drug_type")

    if drug_type == "narkotika":

        return jsonify({
            "type": "result_popup",
            "status": "danger",
            "title": "🚫 TIDAK DIPERBOLEHKAN MASUK",
            "message": (
                "Pembawaan Narkotika sama sekali "
                "tidak diperbolehkan bagi penumpang."
            ),
            "actions": AFTER_ACTION_OPTIONS
        })

    elif drug_type == "psikotropika":

        return jsonify({
            "type": "question_psikotropika",
            "message": (
                "Untuk Psikotropika, batasan aturan:\n"
                "**Hanya WNA atau wisatawan asing**\n"
                "Berapapun jumlahnya **harus sesuai resep dokter** "
                "(maksimal 60 hari pengobatan)\n\n"
                "Apakah Anda WNA/Wisatawan Asing & membawa resep dokter?"
            ),
            "options": [
                {
                    "id": "psiko_ya",
                    "text": "Ya, WNA & Ada Resep Dokter"
                },
                {
                    "id": "psiko_tidak",
                    "text": "Tidak Memiliki Resep"
                }
            ]
        })

    elif drug_type in LIMITS:

        item = LIMITS[drug_type]

        return jsonify({
            "type": "input_quantity",
            "item_key": drug_type,
            "title": item["name"],
            "message": (
                f"Masukkan jumlah **{item['name']}** "
                f"yang Anda bawa (dalam {item['unit']}):"
            )
        })

    return jsonify({
        "type": "error",
        "message": "Jenis obat tidak valid."
    }), 400


# ==========================================
# API VALIDASI BARANG
# ==========================================

@app.route("/api/validate_input", methods=["POST"])
def validate_input():

    data = request.get_json(silent=True) or {}
    item_key = data.get("item_key")

    # VALIDASI PSIKOTROPIKA
    if item_key == "psikotropika_check":

        is_valid = data.get("is_valid", False)

        if is_valid:

            return jsonify({
                "type": "result_popup",
                "status": "success",
                "title": "✅ DIPERSILAHKAN MASUK",
                "message": (
                    "Psikotropika diperbolehkan masuk khusus "
                    "WNA/wisatawan asing sesuai resep dokter "
                    "(maksimal 60 hari pengobatan)."
                ),
                "actions": AFTER_ACTION_OPTIONS
            })

        return jsonify({
            "type": "result_popup",
            "status": "danger",
            "title": "🚫 TIDAK DIPERBOLEHKAN MASUK",
            "message": (
                "Psikotropika tidak diperbolehkan masuk "
                "jika Anda bukan WNA/wisatawan asing "
                "atau tanpa resep dokter."
            ),
            "actions": AFTER_ACTION_OPTIONS
        })

    # VALIDASI PKMK
    if item_key == "pkmk":

        has_prescription = data.get("has_prescription", False)

        if has_prescription:

            return jsonify({
                "type": "result_popup",
                "status": "success",
                "title": "✅ DIPERSILAHKAN MASUK",
                "message": (
                    "Produk PKMK diperbolehkan masuk "
                    "sesuai dengan resep dokter yang dibawa."
                ),
                "actions": AFTER_ACTION_OPTIONS
            })

        return jsonify({
            "type": "result_popup",
            "status": "danger",
            "title": "🚫 TIDAK DIPERBOLEHKAN MASUK",
            "message": (
                "Produk PKMK wajib sesuai dengan resep dokter. "
                "Barang tidak diperbolehkan masuk tanpa resep."
            ),
            "actions": AFTER_ACTION_OPTIONS
        })

    # VALIDASI JUMLAH BARANG
    if item_key in LIMITS:

        item = LIMITS[item_key]

        try:
            qty = float(data.get("quantity", 0))
        except (ValueError, TypeError):
            qty = 0

        if qty < 0:
            return jsonify({
                "type": "error",
                "message": "Jumlah barang tidak boleh negatif."
            }), 400

        limit = item["limit"]
        unit = item["unit"]

        quantity_text = (
            str(int(qty))
            if qty.is_integer()
            else str(qty)
        )

        if qty <= limit:

            return jsonify({
                "type": "result_popup",
                "status": "success",
                "title": "✅ DIPERSILAHKAN MASUK",
                "message": (
                    f"Jumlah **{quantity_text} {unit} "
                    f"{item['name']}** tidak melebihi "
                    f"batasan maksimal ({limit} {unit})."
                ),
                "actions": AFTER_ACTION_OPTIONS
            })

        excess = qty - limit

        excess_text = (
            str(int(excess))
            if excess.is_integer()
            else str(excess)
        )

        if item_key in ["tablet_kapsul", "krim_cairan_aerosol"]:

            return jsonify({
                "type": "result_popup",
                "status": "warning",
                "title": "⚠️ MELEBIHI BATAS TANPA RESEP",
                "message": (
                    f"Anda membawa **{quantity_text} {unit}** "
                    f"(Batas tanpa resep dokter: {limit} {unit}).\n\n"
                    f"• Jika **membawa resep dokter**: "
                    "Dipersilahkan masuk (maksimal 90 hari pengobatan).\n"
                    f"• Jika **tanpa resep dokter**: Silakan "
                    f"**kurangi jumlah sebanyak {excess_text} {unit}** "
                    f"(hanya {limit} {unit} yang diperbolehkan)."
                ),
                "actions": AFTER_ACTION_OPTIONS
            })

        return jsonify({
            "type": "result_popup",
            "status": "warning",
            "title": "⚠️ PERINGATAN / KURANGI JUMLAH",
            "message": (
                f"Jumlah **{quantity_text} {unit}** melebihi "
                f"batas maksimal pembawaan ({limit} {unit} "
                "per penumpang).\n\n"
                f"👉 Silakan kurangi jumlah Anda sebanyak "
                f"**{excess_text} {unit}** agar tidak melebihi "
                f"batasan {limit} {unit}."
            ),
            "excess": excess,
            "actions": AFTER_ACTION_OPTIONS
        })

    return jsonify({
        "type": "error",
        "message": "Terjadi kesalahan sistem."
    }), 400


# ==========================================
# VERCEL SERVERLESS
# ==========================================

app_instance = app


if __name__ == "__main__":
    app.run(debug=True, port=5000)