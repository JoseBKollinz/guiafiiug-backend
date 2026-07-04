from flask import Flask, request, jsonify
from flask_cors import CORS
from firebase_admin import auth as fb_auth
from firebase_admin_config import db
from firebase_admin import firestore
from crypto_utils import encriptar_cedula, desencriptar_cedula, hash_cedula
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

# Sirve login.html en la raíz
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "login.html")

# Sirve cualquier otro archivo del frontend (dashboard.html, css, js)
@app.route("/<path:filename>")
def servir_estaticos(filename):
    return send_from_directory(app.static_folder, filename)


def get_role_from_token(id_token):
    decoded = fb_auth.verify_id_token(id_token)
    return decoded.get("role"), decoded["uid"]


def require_role(id_token, roles_permitidos):
    role, uid = get_role_from_token(id_token)
    if role not in roles_permitidos:
        raise PermissionError("No autorizado")
    return role, uid


# ---------- Login / verificación de token (con auditoría) ----------
@app.route("/api/verify", methods=["POST"])
def verify():
    id_token = request.json.get("idToken")
    try:
        role, uid = get_role_from_token(id_token)
        if not role:
            return jsonify({"error": "Usuario sin rol asignado"}), 403

        db.collection("logs").add({
            "usuario_uid": uid,
            "accion": "login",
            "resultado": "exito",
            "rol": role,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "ip": request.remote_addr
        })

        return jsonify({"role": role, "uid": uid})
    except Exception as e:
        db.collection("logs").add({
            "accion": "login",
            "resultado": "fallido",
            "error": str(e),
            "timestamp": firestore.SERVER_TIMESTAMP,
            "ip": request.remote_addr
        })
        return jsonify({"error": str(e)}), 401


# ---------- Registro de estudiante (cifra la cédula antes de guardar) ----------
@app.route("/api/registrar-estudiante", methods=["POST"])
def registrar_estudiante():
    data = request.json
    nombre = data.get("nombre")
    apellido = data.get("apellido")
    cedula = data.get("cedula")

    if not (nombre and apellido and cedula):
        return jsonify({"error": "Faltan datos"}), 400

    cedula_cifrada = encriptar_cedula(cedula)
    cedula_hash = hash_cedula(cedula)

    nuevo_doc = db.collection("usuarios").document()  # ID aleatorio
    nuevo_doc.set({
        "nombre": nombre,
        "apellido": apellido,
        "cedula": cedula_cifrada,
        "cedula_hash": cedula_hash,
        "fechaRegistro": firestore.SERVER_TIMESTAMP
    })

    db.collection("logs").add({
        "accion": "registro_estudiante",
        "documento": nuevo_doc.id,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok", "id": nuevo_doc.id})


# ---------- Módulo 1 — Estadísticas generales (solo Admin) ----------
@app.route("/api/estadisticas", methods=["POST"])
def estadisticas():
    try:
        require_role(request.json.get("idToken"), ["admin"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403
    return jsonify({
        "total_usuarios": 1240,
        "pct_estudiantes": 87,
        "pct_visitantes": 13,
        "activos_semana": 312
    })


# ---------- Módulo 2 — Espacios más buscados (Admin + Auditor) ----------
@app.route("/api/espacios-populares", methods=["POST"])
def espacios_populares():
    try:
        require_role(request.json.get("idToken"), ["admin", "auditor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403
    return jsonify({"ranking": [
        {"espacio": "Lab. de Redes", "busquedas": 154},
        {"espacio": "Aula 302", "busquedas": 121},
        {"espacio": "Auditorio Central", "busquedas": 98}
    ]})


# ---------- Módulo 3 — Gestión de espacios (Admin + Editor) ----------
@app.route("/api/espacios", methods=["GET", "POST", "PUT", "DELETE"])
def gestion_espacios():
    id_token = request.args.get("idToken") or request.json.get("idToken")
    try:
        require_role(id_token, ["admin", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403
    # Aquí iría el CRUD real contra Firestore (db.collection("espacios")...)
    return jsonify({"status": "ok"})


# ---------- Módulo 4 — Auditoría (Admin + Auditor) ----------
@app.route("/api/auditoria", methods=["POST"])
def auditoria():
    try:
        require_role(request.json.get("idToken"), ["admin", "auditor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403
    logs = db.collection("logs").order_by(
        "timestamp", direction="DESCENDING"
    ).limit(50).stream()
    return jsonify([l.to_dict() for l in logs])


# ---------- Módulo 4.5 — Listado de usuarios con cédula descifrada (Admin + Auditor) ----------
@app.route("/api/usuarios", methods=["POST"])
def listar_usuarios():
    id_token = request.json.get("idToken")
    try:
        require_role(id_token, ["admin", "auditor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    docs = db.collection("usuarios").stream()
    resultado = []
    for doc in docs:
        d = doc.to_dict()
        try:
            d["cedula"] = desencriptar_cedula(d["cedula"])
        except Exception:
            d["cedula"] = "(dato antiguo sin cifrar o corrupto)"
        resultado.append(d)

    return jsonify(resultado)

@app.route("/api/buscar-usuario", methods=["POST"])
def buscar_usuario():
    cedula = request.json.get("cedula")
    hash_buscado = hash_cedula(cedula)

    query = db.collection("usuarios").where("cedula_hash", "==", hash_buscado).limit(1).stream()
    resultado = list(query)

    if not resultado:
        return jsonify({"error": "Usuario no encontrado"}), 404

    doc = resultado[0]
    return jsonify({"id": doc.id})

# ---------- Módulo 5 — Visitante Web (público, sin login) ----------
@app.route("/api/espacios-publicos", methods=["GET"])
def espacios_publicos():
    espacios = db.collection("espacios").where("publico", "==", True).stream()
    return jsonify([e.to_dict() for e in espacios])


if __name__ == "__main__":
    app.run(debug=True, port=5000)