from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import base64
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY was not found in .env")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ============================================================
# APP
# ============================================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "medisafe.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(
        DATABASE,
        timeout=10,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass

    conn.execute("PRAGMA busy_timeout=10000")

    return conn


def init_db():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicine_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_name TEXT NOT NULL,
            status TEXT,
            searched_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interaction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine1 TEXT NOT NULL,
            medicine2 TEXT NOT NULL,
            risk TEXT,
            explanation TEXT,
            checked_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prescription_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            result TEXT,
            scanned_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_name TEXT NOT NULL,
            reminder_time TEXT NOT NULL,
            frequency TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            uses TEXT,
            dosage TEXT,
            side_effects TEXT,
            warnings TEXT
        )
    """)

    medicines = [

        (
            "Paracetamol",
            "Used for fever, headache and mild to moderate pain.",
            "Usually 500-650 mg as directed by a doctor.",
            "Nausea, stomach discomfort, allergic reaction.",
            "Do not exceed the recommended daily dose. Excessive use can damage the liver."
        ),

        (
            "Ibuprofen",
            "Used for pain, fever and inflammation.",
            "Usually 200-400 mg as directed.",
            "Stomach irritation, nausea, heartburn.",
            "Use carefully if you have stomach ulcers, kidney problems or bleeding risk."
        ),

        (
            "Cetirizine",
            "Used for allergies, sneezing, runny nose and itching.",
            "Usually 5-10 mg once daily.",
            "Drowsiness, dry mouth, tiredness.",
            "May cause sleepiness. Avoid driving if affected."
        ),

        (
            "Levocetirizine",
            "Used to treat allergy symptoms.",
            "Usually 5 mg once daily.",
            "Drowsiness, dry mouth, fatigue.",
            "Can cause drowsiness."
        ),

        (
            "Amoxicillin",
            "Antibiotic used for certain bacterial infections.",
            "Take only according to prescription.",
            "Nausea, diarrhea, rash.",
            "Complete the prescribed course. Not useful for viral infections."
        ),

        (
            "Azithromycin",
            "Antibiotic used for certain bacterial infections.",
            "Take only according to prescription.",
            "Nausea, diarrhea, stomach pain.",
            "Use only when prescribed."
        ),

        (
            "Pantoprazole",
            "Reduces stomach acid and is used for acidity and reflux.",
            "Usually taken before food as prescribed.",
            "Headache, diarrhea, nausea.",
            "Long-term use should be monitored by a healthcare professional."
        ),

        (
            "Omeprazole",
            "Used for acidity, heartburn and acid reflux.",
            "Usually taken before food.",
            "Headache, nausea, abdominal discomfort.",
            "Use according to medical advice."
        ),

        (
            "Metformin",
            "Commonly used to control blood glucose in type 2 diabetes.",
            "Dose depends on the patient and prescription.",
            "Nausea, diarrhea, stomach discomfort.",
            "Kidney function may need monitoring."
        ),

        (
            "Glimepiride",
            "Used to help control blood glucose in type 2 diabetes.",
            "Dose is individualized by the doctor.",
            "Low blood sugar, dizziness, sweating.",
            "Take exactly as prescribed."
        ),

        (
            "Amlodipine",
            "Used to treat high blood pressure.",
            "Usually once daily as prescribed.",
            "Swelling, dizziness, headache.",
            "Monitor blood pressure regularly."
        ),

        (
            "Losartan",
            "Used for high blood pressure and certain heart/kidney conditions.",
            "Usually once daily as prescribed.",
            "Dizziness, increased potassium.",
            "Blood pressure and kidney function may require monitoring."
        ),

        (
            "Atorvastatin",
            "Used to lower cholesterol and reduce cardiovascular risk.",
            "Dose depends on prescription.",
            "Muscle pain, headache, digestive problems.",
            "Report unexplained severe muscle pain to a doctor."
        ),

        (
            "Aspirin",
            "Used in selected cases for pain or prevention of blood clots.",
            "Dose depends strongly on the indication.",
            "Stomach irritation, bruising, bleeding.",
            "Use regularly only under medical advice."
        ),

        (
            "Montelukast",
            "Used for asthma and allergy symptoms.",
            "Usually once daily as prescribed.",
            "Headache, abdominal pain.",
            "Report unusual mood or behavior changes."
        ),

        (
            "Salbutamol",
            "Used to relieve breathing difficulty in asthma.",
            "Use according to prescribed inhaler instructions.",
            "Tremor, fast heartbeat, headache.",
            "Seek medical help if breathing difficulty is severe."
        ),

        (
            "Doxycycline",
            "Antibiotic used for certain bacterial infections.",
            "Take only according to prescription.",
            "Nausea, stomach upset, sun sensitivity.",
            "Take with adequate water."
        ),

        (
            "Fluconazole",
            "Antifungal medicine used for certain fungal infections.",
            "Dose depends on infection and prescription.",
            "Nausea, headache, abdominal discomfort.",
            "Can interact with several medicines."
        ),

        (
            "Clotrimazole",
            "Antifungal medicine used for fungal skin infections.",
            "Apply/use according to product instructions.",
            "Skin irritation, redness or itching.",
            "For external use unless advised otherwise."
        ),

        (
            "ORS",
            "Helps replace fluids and electrolytes during dehydration.",
            "Prepare exactly according to packet instructions.",
            "Usually well tolerated when prepared correctly.",
            "Do not change the amount of water specified."
        ),

        (
            "Domperidone",
            "Used in selected cases for nausea and vomiting.",
            "Use only according to medical advice.",
            "Dry mouth, abdominal discomfort.",
            "May affect heart rhythm in some people."
        ),

        (
            "Diclofenac",
            "Used for pain and inflammation.",
            "Dose depends on prescription.",
            "Stomach irritation, nausea, dizziness.",
            "Can increase stomach, kidney and cardiovascular risks."
        ),

        (
            "Furosemide",
            "Diuretic used for fluid retention.",
            "Dose is prescribed individually.",
            "Frequent urination, dehydration, electrolyte changes.",
            "Blood pressure and electrolytes may need monitoring."
        ),

        (
            "Levothyroxine",
            "Used to replace thyroid hormone in hypothyroidism.",
            "Dose is individualized.",
            "Usually well tolerated when correctly dosed.",
            "Take consistently as instructed."
        ),

        (
            "Prednisolone",
            "Corticosteroid used for inflammation and certain immune conditions.",
            "Dose and duration depend on the condition.",
            "Increased appetite, mood changes, stomach upset.",
            "Do not stop long-term treatment suddenly without medical advice."
        )
    ]

    for medicine in medicines:
        cursor.execute("""
            INSERT OR IGNORE INTO medicines
            (name, uses, dosage, side_effects, warnings)
            VALUES (?, ?, ?, ?, ?)
        """, medicine)

    conn.commit()
    conn.close()


# ============================================================
# INTERACTIONS
# ============================================================

INTERACTIONS = {

    frozenset(["ibuprofen", "aspirin"]): {
        "risk": "Moderate",
        "explanation": "Using ibuprofen with aspirin can increase stomach irritation and bleeding risk.",
        "recommendation": "Use together only when advised by a healthcare professional."
    },

    frozenset(["aspirin", "diclofenac"]): {
        "risk": "High",
        "explanation": "Both medicines can increase stomach irritation and bleeding risk.",
        "recommendation": "Avoid combining them unless specifically prescribed."
    },

    frozenset(["ibuprofen", "diclofenac"]): {
        "risk": "High",
        "explanation": "Both are NSAIDs and combining them may increase stomach, kidney and bleeding risks.",
        "recommendation": "Do not combine without medical advice."
    },

    frozenset(["losartan", "ibuprofen"]): {
        "risk": "Moderate",
        "explanation": "Ibuprofen may affect blood pressure control and kidney function.",
        "recommendation": "Consult a healthcare professional before regular combined use."
    },

    frozenset(["amlodipine", "ibuprofen"]): {
        "risk": "Moderate",
        "explanation": "Ibuprofen may reduce the blood-pressure-lowering effect of amlodipine.",
        "recommendation": "Monitor blood pressure and ask a doctor if regular use is needed."
    },

    frozenset(["metformin", "furosemide"]): {
        "risk": "Moderate",
        "explanation": "These medicines may require monitoring of kidney function and fluid balance.",
        "recommendation": "Use under medical supervision."
    },

    frozenset(["fluconazole", "atorvastatin"]): {
        "risk": "Moderate",
        "explanation": "Fluconazole can affect atorvastatin metabolism and increase side-effect risk.",
        "recommendation": "Consult your doctor or pharmacist."
    },

    frozenset(["cetirizine", "levocetirizine"]): {
        "risk": "Moderate",
        "explanation": "Both are antihistamines and may increase drowsiness.",
        "recommendation": "Avoid combining unless specifically instructed."
    },

    frozenset(["paracetamol", "ibuprofen"]): {
        "risk": "Low",
        "explanation": "These medicines can sometimes be used together, but individual factors and doses matter.",
        "recommendation": "Use according to recommended doses or medical advice."
    }
}


# ============================================================
# PAGES
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/medicine")
def medicine_page():
    return render_template("medicine.html")


@app.route("/prescription")
def prescription_page():
    return render_template("prescription.html")


@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


# ============================================================
# MEDICINE CHECK
# ============================================================

@app.route("/api/check-medicine", methods=["POST"])
@app.route("/check-medicine", methods=["POST"])
def check_medicine():

    data = request.get_json(silent=True) or {}

    medicine_name = data.get("medicine_name") or data.get("medicine")

    if not medicine_name:
        return jsonify({
            "success": False,
            "error": "Please enter a medicine name."
        }), 400

    medicine_name = medicine_name.strip()

    conn = get_db()

    medicine = conn.execute("""
        SELECT *
        FROM medicines
        WHERE LOWER(name) = LOWER(?)
    """, (medicine_name,)).fetchone()

    if medicine:

        conn.execute("""
            INSERT INTO medicine_history
            (medicine_name, status, searched_at)
            VALUES (?, ?, ?)
        """, (
            medicine["name"],
            "Found",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "found": True,
            "medicine": {
                "name": medicine["name"],
                "uses": medicine["uses"],
                "dosage": medicine["dosage"],
                "side_effects": medicine["side_effects"],
                "warnings": medicine["warnings"]
            }
        })

    conn.execute("""
        INSERT INTO medicine_history
        (medicine_name, status, searched_at)
        VALUES (?, ?, ?)
    """, (
        medicine_name,
        "Not Found",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "found": False,
        "message": "Medicine not found in the MediSafe database.",
        "recommendation": "Please verify the medicine name or consult a qualified healthcare professional."
    })


# ============================================================
# INTERACTION CHECK
# ============================================================

@app.route("/api/check-interaction", methods=["POST"])
@app.route("/check-interaction", methods=["POST"])
def check_interaction():

    data = request.get_json(silent=True) or {}

    medicine1 = (
        data.get("medicine1")
        or data.get("medicine_a")
        or data.get("first_medicine")
        or ""
    ).strip().lower()

    medicine2 = (
        data.get("medicine2")
        or data.get("medicine_b")
        or data.get("second_medicine")
        or ""
    ).strip().lower()

    if not medicine1 or not medicine2:
        return jsonify({
            "success": False,
            "error": "Please enter both medicine names."
        }), 400

    key = frozenset([medicine1, medicine2])
    result = INTERACTIONS.get(key)

    conn = get_db()

    if result:

        conn.execute("""
            INSERT INTO interaction_history
            (medicine1, medicine2, risk, explanation, checked_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            medicine1,
            medicine2,
            result["risk"],
            result["explanation"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "interaction_found": True,
            "risk": result["risk"],
            "explanation": result["explanation"],
            "recommendation": result["recommendation"]
        })

    conn.execute("""
        INSERT INTO interaction_history
        (medicine1, medicine2, risk, explanation, checked_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        medicine1,
        medicine2,
        "No Known Interaction",
        "No interaction rule was found in the current MediSafe database.",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "interaction_found": False,
        "risk": "No Known Interaction",
        "explanation": "No known interaction was found in the current MediSafe database.",
        "recommendation": "This does not guarantee that no interaction exists. Confirm with a doctor or pharmacist."
    })


# ============================================================
# REMINDERS
# ============================================================

@app.route("/api/add-reminder", methods=["POST"])
def add_reminder():

    data = request.get_json(silent=True) or {}

    medicine_name = data.get("medicine_name", "").strip()
    reminder_time = data.get("time", "").strip()
    frequency = data.get("frequency", "").strip()

    if not medicine_name or not reminder_time or not frequency:
        return jsonify({
            "success": False,
            "error": "Please fill all reminder fields."
        }), 400

    conn = get_db()

    cursor = conn.execute("""
        INSERT INTO reminders
        (medicine_name, reminder_time, frequency, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        medicine_name,
        reminder_time,
        frequency,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    reminder_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Reminder added successfully.",
        "id": reminder_id
    })


@app.route("/api/reminders", methods=["GET"])
def get_reminders():

    conn = get_db()

    rows = conn.execute("""
        SELECT id, medicine_name, reminder_time, frequency, created_at
        FROM reminders
        ORDER BY reminder_time ASC
    """).fetchall()

    conn.close()

    reminders = []

    for row in rows:
        reminders.append({
            "id": row["id"],
            "medicine_name": row["medicine_name"],
            "time": row["reminder_time"],
            "frequency": row["frequency"],
            "created_at": row["created_at"]
        })

    return jsonify({
        "success": True,
        "reminders": reminders
    })


@app.route("/api/delete-reminder/<int:reminder_id>", methods=["DELETE"])
def delete_reminder(reminder_id):

    conn = get_db()

    conn.execute("""
        DELETE FROM reminders
        WHERE id = ?
    """, (reminder_id,))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Reminder deleted successfully."
    })


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/api/dashboard", methods=["GET"])
def dashboard_data():

    conn = get_db()

    medicine_checks = conn.execute(
        "SELECT COUNT(*) AS total FROM medicine_history"
    ).fetchone()["total"]

    interaction_checks = conn.execute(
        "SELECT COUNT(*) AS total FROM interaction_history"
    ).fetchone()["total"]

    prescription_scans = conn.execute(
        "SELECT COUNT(*) AS total FROM prescription_history"
    ).fetchone()["total"]

    active_reminders = conn.execute(
        "SELECT COUNT(*) AS total FROM reminders"
    ).fetchone()["total"]

    recent_medicines = conn.execute("""
        SELECT medicine_name, status, searched_at
        FROM medicine_history
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    recent = []

    for row in recent_medicines:
        recent.append({
            "medicine_name": row["medicine_name"],
            "status": row["status"],
            "date": row["searched_at"]
        })

    return jsonify({
        "success": True,
        "stats": {
            "medicine_checks": medicine_checks,
            "interaction_checks": interaction_checks,
            "prescription_scans": prescription_scans,
            "active_reminders": active_reminders
        },
        "recent_activity": recent
    })


# ============================================================
# PRESCRIPTION SCANNER - REAL AI VISION
# ============================================================

@app.route("/api/scan-prescription", methods=["POST"])
@app.route("/scan-prescription", methods=["POST"])
def scan_prescription():

    if "prescription" not in request.files:
        return jsonify({
            "success": False,
            "error": "Please upload a prescription image."
        }), 400

    file = request.files["prescription"]

    if file.filename == "":
        return jsonify({
            "success": False,
            "error": "No file selected."
        }), 400

    if client is None:
        return jsonify({
            "success": False,
            "error": "OpenAI API key is not configured. Check your .env file."
        }), 500

    allowed_extensions = {"jpg", "jpeg", "png"}

    extension = file.filename.rsplit(".", 1)[-1].lower()

    if extension not in allowed_extensions:
        return jsonify({
            "success": False,
            "error": "Only JPG, JPEG and PNG images are allowed."
        }), 400

    safe_filename = os.path.basename(file.filename)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    safe_filename = f"{timestamp}_{safe_filename}"

    filepath = os.path.join(
        UPLOAD_FOLDER,
        safe_filename
    )

    try:

        file.save(filepath)

        with open(filepath, "rb") as image_file:
            image_bytes = image_file.read()

        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        if extension == "png":
            mime_type = "image/png"
        else:
            mime_type = "image/jpeg"

        # ----------------------------------------------------
        # AI VISION
        # ----------------------------------------------------

        response = client.chat.completions.create(

            model="gpt-4o-mini",

            messages=[

                {
                    "role": "system",
                    "content": """
You are the prescription verification component of MediSafe AI.

Your task is ONLY to analyze the uploaded image.

IMPORTANT RULES:

1. First decide whether the image appears to be a real medical
   prescription or medicine-related document.

2. If it is NOT a prescription or medicine-related document,
   return exactly:

STATUS: NOT_A_PRESCRIPTION

3. If the image is too blurry, unreadable, cropped, extremely
   dark, or the medicine names cannot be reliably read, return:

STATUS: UNREADABLE

4. NEVER invent or guess medicine names.

5. Only report a medicine if its name is clearly visible in the
   image.

6. Do not assume that a medicine is present just because it is
   common.

7. If it is a valid prescription and medicine names are clearly
   visible, return:

STATUS: VALID

MEDICINES:
- medicine name
- medicine name

8. If a medicine name is uncertain, DO NOT include it.

9. Do not provide diagnosis.

10. Do not create a prescription.

11. Do not guess dosage.

Be conservative. Accuracy is more important than producing a
result.
"""
                },

                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this image carefully. Do not guess anything that cannot be clearly read."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }

            ],

            temperature=0
        )

        ai_result = response.choices[0].message.content.strip()

        print("=" * 60)
        print("PRESCRIPTION AI RESULT")
        print(ai_result)
        print("=" * 60)

        # ----------------------------------------------------
        # NOT A PRESCRIPTION
        # ----------------------------------------------------

        if "STATUS: NOT_A_PRESCRIPTION" in ai_result:

            result_text = "The uploaded image does not appear to be a prescription."

            conn = get_db()

            conn.execute("""
                INSERT INTO prescription_history
                (filename, result, scanned_at)
                VALUES (?, ?, ?)
            """, (
                safe_filename,
                result_text,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            conn.commit()
            conn.close()

            return jsonify({
                "success": True,
                "valid_prescription": False,
                "status": "NOT_A_PRESCRIPTION",
                "filename": safe_filename,
                "message": result_text,
                "medicines": []
            })

        # ----------------------------------------------------
        # UNREADABLE
        # ----------------------------------------------------

        if "STATUS: UNREADABLE" in ai_result:

            result_text = (
                "The prescription could not be read reliably. "
                "Please upload a clearer and well-lit image."
            )

            conn = get_db()

            conn.execute("""
                INSERT INTO prescription_history
                (filename, result, scanned_at)
                VALUES (?, ?, ?)
            """, (
                safe_filename,
                result_text,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            conn.commit()
            conn.close()

            return jsonify({
                "success": True,
                "valid_prescription": False,
                "status": "UNREADABLE",
                "filename": safe_filename,
                "message": result_text,
                "medicines": []
            })

        # ----------------------------------------------------
        # VALID PRESCRIPTION
        # ----------------------------------------------------

        detected_names = []

        if "MEDICINES:" in ai_result:

            medicine_section = ai_result.split(
                "MEDICINES:",
                1
            )[1]

            for line in medicine_section.splitlines():

                line = line.strip()

                if line.startswith("-"):
                    name = line[1:].strip()

                    if name:
                        detected_names.append(name)

        # ----------------------------------------------------
        # MATCH WITH DATABASE
        # ----------------------------------------------------

        conn = get_db()

        database_medicines = conn.execute("""
            SELECT name, uses, dosage, side_effects, warnings
            FROM medicines
        """).fetchall()

        database_lookup = {
            row["name"].lower(): row
            for row in database_medicines
        }

        final_medicines = []

        for detected_name in detected_names:

            matched = database_lookup.get(
                detected_name.lower()
            )

            if matched:

                final_medicines.append({
                    "name": matched["name"],
                    "database_match": True,
                    "uses": matched["uses"],
                    "dosage": matched["dosage"],
                    "side_effects": matched["side_effects"],
                    "warnings": matched["warnings"]
                })

            else:

                final_medicines.append({
                    "name": detected_name,
                    "database_match": False,
                    "uses": "",
                    "dosage": "",
                    "side_effects": "",
                    "warnings": ""
                })

        # ----------------------------------------------------
        # NO MEDICINES RELIABLY FOUND
        # ----------------------------------------------------

        if len(final_medicines) == 0:

            result_text = (
                "The image appears to be prescription-related, "
                "but no medicine name could be reliably identified."
            )

            conn.execute("""
                INSERT INTO prescription_history
                (filename, result, scanned_at)
                VALUES (?, ?, ?)
            """, (
                safe_filename,
                result_text,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            conn.commit()
            conn.close()

            return jsonify({
                "success": True,
                "valid_prescription": True,
                "status": "NO_MEDICINES_RELIABLY_DETECTED",
                "filename": safe_filename,
                "message": result_text,
                "medicines": []
            })

        # ----------------------------------------------------
        # SAVE HISTORY
        # ----------------------------------------------------

        result_text = (
            f"{len(final_medicines)} medicine(s) detected from prescription."
        )

        conn.execute("""
            INSERT INTO prescription_history
            (filename, result, scanned_at)
            VALUES (?, ?, ?)
        """, (
            safe_filename,
            result_text,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "valid_prescription": True,
            "status": "VALID",
            "filename": safe_filename,
            "message": result_text,
            "medicines": final_medicines,
            "warning": (
                "AI image reading can make mistakes. "
                "Always compare the detected medicine names "
                "with the original prescription and confirm "
                "with a doctor or pharmacist."
            )
        })

    except Exception as e:

        print("=" * 60)
        print("PRESCRIPTION SCANNER ERROR")
        print(repr(e))
        print("=" * 60)

        return jsonify({
            "success": False,
            "error": (
                "The prescription could not be analyzed. "
                "Please check your internet connection and OpenAI API access."
            )
        }), 500


# ============================================================
# AI HEALTH ASSISTANT
# ============================================================

@app.route("/api/health-assistant", methods=["POST"])
def health_assistant():

    data = request.get_json(silent=True) or {}

    question = str(data.get("question", "")).strip()

    if not question:
        return jsonify({
            "success": False,
            "error": "Please enter your question."
        }), 400

    q = question.lower()

    conn = get_db()

    medicines = conn.execute("""
        SELECT name, uses, dosage, side_effects, warnings
        FROM medicines
    """).fetchall()

    conn.close()

    selected_medicine = None

    for medicine in medicines:

        if medicine["name"].lower() in q:
            selected_medicine = medicine
            break

    # --------------------------------------------------------
    # MEDICINE QUESTIONS
    # --------------------------------------------------------

    if selected_medicine:

        name = selected_medicine["name"]
        uses = selected_medicine["uses"]
        dosage = selected_medicine["dosage"]
        side_effects = selected_medicine["side_effects"]
        warnings = selected_medicine["warnings"]

        if any(word in q for word in [
            "use",
            "uses",
            "used for",
            "purpose",
            "why use",
            "what is it for",
            "what does it do"
        ]):

            answer = (
                f"💊 {name}\n\n"
                f"{uses}\n\n"
                f"⚠️ This is general educational information. "
                f"For personalized advice, consult a doctor or pharmacist."
            )

        elif any(word in q for word in [
            "side effect",
            "side effects",
            "adverse effect",
            "reaction"
        ]):

            answer = (
                f"💊 Common side effects of {name}:\n\n"
                f"{side_effects}\n\n"
                f"If you experience severe or unusual symptoms, "
                f"seek medical advice."
            )

        elif any(word in q for word in [
            "dosage",
            "dose",
            "how much",
            "how many"
        ]):

            answer = (
                f"💊 Dosage information for {name}:\n\n"
                f"{dosage}\n\n"
                f"Do not change a prescribed dose without consulting "
                f"a healthcare professional."
            )

        elif any(word in q for word in [
            "warning",
            "warnings",
            "precaution",
            "precautions",
            "careful",
            "danger",
            "safe"
        ]):

            answer = (
                f"🛡️ Important safety information for {name}:\n\n"
                f"{warnings}\n\n"
                f"For personalized advice, consult a doctor or pharmacist."
            )

        else:

            answer = (
                f"💊 {name}\n\n"
                f"Uses: {uses}\n\n"
                f"Dosage: {dosage}\n\n"
                f"Common side effects: {side_effects}\n\n"
                f"Important warnings: {warnings}\n\n"
                f"⚠️ This information is for educational purposes "
                f"and does not replace professional medical advice."
            )

        return jsonify({
            "success": True,
            "question": question,
            "answer": answer,
            "source": "MediSafe Medicine Knowledge Base"
        })

    # --------------------------------------------------------
    # INTERACTION QUESTIONS
    # --------------------------------------------------------

    if any(word in q for word in [
        "interaction",
        "interact",
        "take together",
        "combine",
        "together"
    ]):

        found_medicines = []

        for medicine in medicines:

            if medicine["name"].lower() in q:
                found_medicines.append(
                    medicine["name"].lower()
                )

        if len(found_medicines) >= 2:

            medicine1 = found_medicines[0]
            medicine2 = found_medicines[1]

            interaction = INTERACTIONS.get(
                frozenset([medicine1, medicine2])
            )

            if interaction:

                answer = (
                    f"⚠️ Drug Interaction Check\n\n"
                    f"Medicines: {medicine1.title()} + "
                    f"{medicine2.title()}\n\n"
                    f"Risk Level: {interaction['risk']}\n\n"
                    f"Explanation: {interaction['explanation']}\n\n"
                    f"Recommendation: {interaction['recommendation']}"
                )

            else:

                answer = (
                    f"No interaction rule was found for "
                    f"{medicine1.title()} and {medicine2.title()} "
                    f"in the current MediSafe database.\n\n"
                    f"This does not guarantee that no interaction exists. "
                    f"Please confirm with a doctor or pharmacist."
                )

            return jsonify({
                "success": True,
                "question": question,
                "answer": answer,
                "source": "MediSafe Interaction Database"
            })

    # --------------------------------------------------------
    # REAL AI
    # --------------------------------------------------------

    if client:

        try:

            response = client.chat.completions.create(

                model="gpt-4o-mini",

                messages=[

                    {
                        "role": "system",
                        "content": """
You are MediSafe AI, a medicine safety education assistant.

Give simple, clear general health information.

Do not diagnose diseases.

Do not prescribe medicines.

Do not tell users to change, increase or decrease prescribed doses.

Do not tell users to stop prescribed medicines.

For emergencies such as overdose, poisoning, severe allergic
reaction, unconsciousness, chest pain or severe breathing
difficulty, advise immediate professional medical help.

Keep answers reasonably concise.
"""
                    },

                    {
                        "role": "user",
                        "content": question
                    }

                ],

                temperature=0.3
            )

            answer = response.choices[0].message.content

            if answer:

                return jsonify({
                    "success": True,
                    "question": question,
                    "answer": answer,
                    "source": "AI Assistant"
                })

        except Exception as e:

            print("AI Assistant Error:", repr(e))

    return jsonify({
        "success": True,
        "question": question,
        "answer": (
            "🤖 MediSafe AI can help with general medicine "
            "information, medicine safety, side effects, "
            "warnings and drug interactions.\n\n"
            "Please mention the medicine name in your question."
        ),
        "source": "MediSafe AI Knowledge Base"
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/api/health")
def health():

    return jsonify({
        "success": True,
        "status": "MediSafe AI server is running",
        "database": DATABASE,
        "ai_configured": client is not None
    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return jsonify({
        "success": False,
        "error": "Route not found."
    }), 404


@app.errorhandler(500)
def internal_error(error):

    return jsonify({
        "success": False,
        "error": "Internal server error."
    }), 500


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    init_db()

    print("=" * 60)
    print("       MediSafe AI - Medicine Safety Assistant")
    print("=" * 60)
    print(f"Database: {DATABASE}")

    try:

        conn = get_db()

        medicine_count = conn.execute(
            "SELECT COUNT(*) AS total FROM medicines"
        ).fetchone()["total"]

        conn.close()

        print(f"Medicine records: {medicine_count}")
        print(f"Interaction rules: {len(INTERACTIONS)}")

    except Exception as e:

        print("Database check error:", e)

    print(f"AI configured: {client is not None}")
    print("Server: http://127.0.0.1:5000")
    print("=" * 60)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )