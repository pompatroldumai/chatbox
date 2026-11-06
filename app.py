import os
import sqlite3
from flask import Flask, render_template, request, jsonify

# Coba import upstash_redis
try:
    from upstash_redis import Redis
except ImportError:
    Redis = None

app = Flask(__name__)

DATABASE = 'visitor.db'

# Inisialisasi Upstash Redis jika environment variables tersedia (di Vercel)
redis_url = os.environ.get("KV_REST_API_URL")
redis_token = os.environ.get("KV_REST_API_TOKEN")

if Redis and redis_url and redis_token:
    redis_client = Redis(url=redis_url, token=redis_token)
else:
    redis_client = None

def init_db():
    """Inisialisasi tabel SQLite lokal jika Redis tidak digunakan."""
    if redis_client is None:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Tabel visitor count
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visitor (
                id INTEGER PRIMARY KEY,
                count INTEGER NOT NULL
            )
        ''')
        cursor.execute('SELECT COUNT(*) FROM visitor')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO visitor (id, count) VALUES (1, 0)')

        # Tabel feedback count
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY,
                useful_count INTEGER NOT NULL DEFAULT 0,
                not_useful_count INTEGER NOT NULL DEFAULT 0
            )
        ''')
        cursor.execute('SELECT COUNT(*) FROM feedback')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO feedback (id, useful_count, not_useful_count) VALUES (1, 0, 0)')

        conn.commit()
        conn.close()

# Jalankan inisialisasi SQLite lokal
init_db()

# Master Batasan Sesuai Regulasi BPOM & Bea Cukai
LIMITS = {
    "kosmetik": {
        "limit": 20, 
        "unit": "pcs", 
        "name": "Kosmetik"
    },
    "suplemen": {
        "limit": 5, 
        "unit": "pcs", 
        "name": "Suplemen Kesehatan / Obat Bahan Alam / Obat Kuasi"
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

# Opsi Menu Utama Kategori
MAIN_OPTIONS = [
    {"id": "obat", "icon": "💊", "text": "Obat"},
    {"id": "obat_tradisional", "icon": "🌿", "text": "Obat Tradisional"},
    {"id": "suplemen", "icon": "💪🏻", "text": "Suplemen Kesehatan"},
    {"id": "kosmetik", "icon": "💄", "text": "Kosmetika"},
    {"id": "pkmk", "icon": "🏥", "text": "Pangan Olahan Medis Khusus (PKMK)"},
    {"id": "makanan", "icon": "🧃", "text": "Pangan Olahan Lain", "note": "kecuali minuman beralkohol"}
]

AFTER_ACTION_OPTIONS = [
    {"id": "check_another", "text": "🔄 Cek Barang Lain"},
    {"id": "finish", "text": "✅ Selesai"}
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/visitor_count', methods=['GET'])
def visitor_count():
    # 1. Jika running di Vercel (Menggunakan Upstash Redis)
    if redis_client:
        try:
            current_count = redis_client.incr("visitor_count")
            return jsonify({"count": current_count})
        except Exception as e:
            print("Error Redis:", e)
            return jsonify({"count": 1})

    # 2. Jika running di Localhouse/Komputer Sendiri (Menggunakan SQLite)
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT count FROM visitor WHERE id = 1')
        row = cursor.fetchone()
        current_count = (row[0] if row else 0) + 1
        
        cursor.execute('UPDATE visitor SET count = ? WHERE id = 1', (current_count,))
        conn.commit()
        conn.close()
        return jsonify({"count": current_count})
    except Exception as e:
        print("Error SQLite:", e)
        return jsonify({"count": 1})

@app.route('/api/feedback_stats', methods=['GET'])
def get_feedback_stats():
    """Endpoint untuk mengambil statistik feedback terbaru."""
    if redis_client:
        try:
            useful = int(redis_client.get("feedback_useful") or 0)
            not_useful = int(redis_client.get("feedback_not_useful") or 0)
            return jsonify({"useful": useful, "not_useful": not_useful})
        except Exception as e:
            print("Error Redis Feedback Stats:", e)
            return jsonify({"useful": 0, "not_useful": 0})

    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT useful_count, not_useful_count FROM feedback WHERE id = 1')
        row = cursor.fetchone()
        conn.close()

        if row:
            return jsonify({"useful": row[0], "not_useful": row[1]})
        return jsonify({"useful": 0, "not_useful": 0})
    except Exception as e:
        print("Error SQLite Feedback Stats:", e)
        return jsonify({"useful": 0, "not_useful": 0})

@app.route('/api/feedback', methods=['POST'])
def save_feedback():
    """Endpoint untuk menyimpan vote feedback pengguna (bermanfaat/tidak_bermanfaat)."""
    data = request.get_json(silent=True) or {}
    vote = data.get('vote')  # 'useful' atau 'not_useful'

    if vote not in ['useful', 'not_useful']:
        return jsonify({"type": "error", "message": "Pilihan tidak valid."}), 400

    # 1. Penyimpanan via Upstash Redis (Vercel)
    if redis_client:
        try:
            key = "feedback_useful" if vote == "useful" else "feedback_not_useful"
            redis_client.incr(key)
            useful = int(redis_client.get("feedback_useful") or 0)
            not_useful = int(redis_client.get("feedback_not_useful") or 0)
            return jsonify({"status": "success", "vote": vote, "useful": useful, "not_useful": not_useful})
        except Exception as e:
            print("Error Redis Feedback:", e)
            return jsonify({"status": "error", "message": str(e)}), 500

    # 2. Penyimpanan via SQLite (Lokal)
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        column = "useful_count" if vote == "useful" else "not_useful_count"
        
        cursor.execute(f'UPDATE feedback SET {column} = {column} + 1 WHERE id = 1')
        conn.commit()

        cursor.execute('SELECT useful_count, not_useful_count FROM feedback WHERE id = 1')
        row = cursor.fetchone()
        conn.close()

        return jsonify({"status": "success", "vote": vote, "useful": row[0], "not_useful": row[1]})
    except Exception as e:
        print("Error SQLite Feedback:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/main_menu', methods=['GET'])
def main_menu():
    return jsonify({
        "type": "question",
        "message": "Silakan pilih kategori barang berikutnya yang ingin Anda cek:",
        "options": MAIN_OPTIONS
    })

@app.route('/api/select_category', methods=['POST'])
def select_category():
    data = request.get_json(silent=True) or {}
    cat = data.get('category')

    if cat == 'obat':
        return jsonify({
            "type": "question",
            "message": "Anda memilih Obat. **Pilih jenis obat yang Anda bawa:**",
            "options": [
                {"id": "narkotika", "text": "Narkotika"},
                {"id": "psikotropika", "text": "Psikotropika"},
                {"id": "tablet_kapsul", "text": "Obat Sediaan Padat (Tablet/Kapsul)"},
                {"id": "krim_cairan_aerosol", "text": "Obat Sediaan Semipadat, Cairan, & Aerosol"}
            ]
        })
    elif cat == 'pkmk':
        return jsonify({
            "type": "question_bool",
            "item_key": "pkmk",
            "title": "Produk Pangan Olahan untuk Keperluan Medis Khusus (PKMK)",
            "message": "Apakah Anda membawa **Resep Dokter** untuk produk PKMK ini?",
            "options": [
                {"id": "pkmk_ya", "text": "Ya, membawa resep dokter"},
                {"id": "pkmk_tidak", "text": "Tidak membawa resep dokter"}
            ]
        })
    elif cat in LIMITS:
        item = LIMITS[cat]
        return jsonify({
            "type": "input_quantity",
            "item_key": cat,
            "title": item["name"],
            "message": f"Masukkan jumlah **{item['name']}** yang Anda bawa (dalam {item['unit']}):"
        })
    return jsonify({"type": "error", "message": "Pilihan tidak valid."}), 400

@app.route('/api/select_drug_type', methods=['POST'])
def select_drug_type():
    data = request.get_json(silent=True) or {}
    drug_type = data.get('drug_type')

    if drug_type == 'narkotika':
        return jsonify({
            "type": "result_popup",
            "status": "danger",
            "title": "🚫 TIDAK DIPERBOLEHKAN MASUK",
            "message": "Pembawaan Narkotika **sama sekali tidak diperbolehkan** bagi penumpang.",
            "actions": AFTER_ACTION_OPTIONS
        })
    elif drug_type == 'psikotropika':
        return jsonify({
            "type": "question_psikotropika",
            "message": "Untuk Psikotropika, batasan aturan:\n**Hanya WNA atau wisatawan asing**\nBerapapun jumlahnya **harus sesuai resep dokter** (maksimal 60 hari pengobatan)\n\nApakah Anda WNA/Wisatawan Asing & membawa resep dokter?",
            "options": [
                {"id": "psiko_ya", "text": "Ya, WNA & Ada Resep Dokter"},
                {"id": "psiko_tidak", "text": "Tidak Memiliki Resep"}
            ]
        })
    elif drug_type in LIMITS:
        item = LIMITS[drug_type]
        return jsonify({
            "type": "input_quantity",
            "item_key": drug_type,
            "title": item["name"],
            "message": f"Masukkan jumlah **{item['name']}** yang Anda bawa (dalam {item['unit']}):"
        })
    return jsonify({"type": "error", "message": "Jenis obat tidak valid."}), 400

@app.route('/api/validate_input', methods=['POST'])
def validate_input():
    data = request.get_json(silent=True) or {}
    item_key = data.get('item_key')
    
    # Validasi Psikotropika
    if item_key == 'psikotropika_check':
        is_valid = data.get('is_valid', False)
        if is_valid:
            return jsonify({
                "type": "result_popup",
                "status": "success",
                "title": "✅ DIPERSILAHKAN MASUK",
                "message": "Psikotropika diperbolehkan masuk khusus WNA/wisatawan asing sesuai resep dokter (maksimal 60 hari pengobatan).",
                "actions": AFTER_ACTION_OPTIONS
            })
        else:
            return jsonify({
                "type": "result_popup",
                "status": "danger",
                "title": "🚫 TIDAK DIPERBOLEHKAN MASUK",
                "message": "Psikotropika **tidak diperbolehkan masuk** jika Anda bukan WNA/wisatawan asing atau tanpa resep dokter.",
                "actions": AFTER_ACTION_OPTIONS
            })

    # Validasi PKMK
    if item_key == 'pkmk':
        has_prescription = data.get('has_prescription', False)
        if has_prescription:
            return jsonify({
                "type": "result_popup",
                "status": "success",
                "title": "✅ DIPERSILAHKAN MASUK",
                "message": "Produk PKMK diperbolehkan masuk sesuai dengan resep dokter yang dibawa.",
                "actions": AFTER_ACTION_OPTIONS
            })
        else:
            return jsonify({
                "type": "result_popup",
                "status": "danger",
                "title": "🚫 TIDAK DIPERBOLEHKAN MASUK",
                "message": "Produk PKMK **wajib sesuai dengan resep dokter**. Barang tidak diperbolehkan masuk tanpa resep.",
                "actions": AFTER_ACTION_OPTIONS
            })

    # Validasi Berdasarkan Jumlah
    if item_key in LIMITS:
        item = LIMITS[item_key]
        try:
            qty = float(data.get('quantity', 0))
        except (ValueError, TypeError):
            qty = 0

        limit = item["limit"]
        unit = item["unit"]

        if qty <= limit:
            return jsonify({
                "type": "result_popup",
                "status": "success",
                "title": "✅ DIPERSILAHKAN MASUK",
                "message": f"Jumlah **{int(qty) if qty.is_integer() else qty} {unit} {item['name']}** tidak melebihi batasan maksimal ({limit} {unit}).",
                "actions": AFTER_ACTION_OPTIONS
            })
        else:
            excess = qty - limit
            if item_key in ['tablet_kapsul', 'krim_cairan_aerosol']:
                return jsonify({
                    "type": "result_popup",
                    "status": "warning",
                    "title": "⚠️ MELEBIHI BATAS TANPA RESEP",
                    "message": f"Anda membawa **{int(qty) if qty.is_integer() else qty} {unit}** (Batas tanpa resep dokter: {limit} {unit}).\n\n" +
                               f"• Jika **membawa resep dokter**: Dipersilahkan masuk (maksimal 90 hari pengobatan).\n" +
                               f"• Jika **tanpa resep dokter**: Silakan **kurangi Jumlah sebanyak {int(excess) if excess.is_integer() else excess} {unit}** (hanya {limit} {unit} yang diperbolehkan).",
                    "actions": AFTER_ACTION_OPTIONS
                })
            else:
                return jsonify({
                    "type": "result_popup",
                    "status": "warning",
                    "title": "⚠️ PERINGATAN / KURANGI JUMLAH",
                    "message": f"Jumlah **{int(qty) if qty.is_integer() else qty} {unit}** melebihi batas maksimal pembawaan ({limit} {unit} per penumpang).\n\n" +
                               f"👉 Silakan kurangi Jumlah Anda sebanyak **{int(excess) if excess.is_integer() else excess} {unit}** agar tidak melebihi batasan {limit} {unit}.",
                    "excess": excess,
                    "actions": AFTER_ACTION_OPTIONS
                })

    return jsonify({"type": "error", "message": "Terjadi kesalahan sistem."}), 400

# Wajib untuk deployment Vercel Serverless Function
app_instance = app

if __name__ == '__main__':
    app.run(debug=True, port=5000)