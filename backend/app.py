from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from firebase_admin import auth as fb_auth
from firebase_admin_config import db
from firebase_admin import firestore
from crypto_utils import encriptar_cedula, desencriptar_cedula, hash_cedula

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)


# ---------- Servir el frontend ----------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "login.html")


@app.route("/<path:filename>")
def servir_estaticos(filename):
    if filename.startswith("api/"):
        return jsonify({"error": "Ruta de API no encontrada"}), 404
    response = send_from_directory(app.static_folder, filename)
    if filename.endswith(".js"):
        response.headers["Content-Type"] = "application/javascript"
    return response


# ---------- Helpers de autenticación y roles ----------
def get_role_from_token(id_token):
    decoded = fb_auth.verify_id_token(id_token)
    return decoded.get("role"), decoded["uid"]


def require_role(id_token, roles_permitidos):
    role, uid = get_role_from_token(id_token)
    if role not in roles_permitidos:
        raise PermissionError("No autorizado")
    return role, uid


def obtener_nombre_usuario(uid):
    try:
        doc = db.collection("usuarios_admin").document(uid).get()
        if doc.exists:
            return doc.to_dict().get("nombre", "Desconocido")
    except Exception:
        pass
    return "Desconocido"


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
            "usuario_nombre": obtener_nombre_usuario(uid),
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

    nuevo_doc = db.collection("usuarios").document()
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


# ---------- Módulo 2 — Gestión de Bloques (Admin, Admin Junior, Editor) ----------
@app.route("/api/bloques", methods=["GET"])
def listar_bloques():
    bloques = []
    for doc in db.collection("bloques").stream():
        d = doc.to_dict()
        d["id"] = doc.id
        bloques.append(d)
    return jsonify(bloques)


@app.route("/api/bloques", methods=["POST"])
def crear_bloque():
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    nombre = request.json.get("nombre", "").strip()
    if not nombre:
        return jsonify({"error": "El nombre del bloque es obligatorio"}), 400

    bloque_id = nombre.replace(" ", "_")
    db.collection("bloques").document(bloque_id).set({"nombre": nombre})

    db.collection("logs").add({
        "accion": "crear_bloque",
        "documento": bloque_id,
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok", "id": bloque_id})


@app.route("/api/bloques/<bloque_id>", methods=["PUT"])
def editar_bloque(bloque_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    nombre = request.json.get("nombre", "").strip()
    if not nombre:
        return jsonify({"error": "El nombre del bloque es obligatorio"}), 400

    db.collection("bloques").document(bloque_id).update({"nombre": nombre})

    db.collection("logs").add({
        "accion": "editar_bloque",
        "documento": bloque_id,
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "cambios": {"nombre": nombre},
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


@app.route("/api/bloques/<bloque_id>", methods=["DELETE"])
def eliminar_bloque(bloque_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    aulas = list(db.collection("bloques").document(bloque_id).collection("aulas").limit(1).stream())
    if aulas:
        return jsonify({"error": "No se puede eliminar: el bloque tiene aulas asociadas"}), 400

    db.collection("bloques").document(bloque_id).delete()

    db.collection("logs").add({
        "accion": "eliminar_bloque",
        "documento": bloque_id,
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


# ---------- Módulo 3 — Gestión de Aulas (Admin, Admin Junior, Editor) ----------
@app.route("/api/bloques/<bloque_id>/aulas", methods=["GET"])
def listar_aulas(bloque_id):
    aulas = []
    for doc in db.collection("bloques").document(bloque_id).collection("aulas").stream():
        d = doc.to_dict()
        d["id"] = doc.id
        aulas.append(d)
    return jsonify(aulas)


@app.route("/api/bloques/<bloque_id>/aulas", methods=["POST"])
def crear_aula(bloque_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    nombre = request.json.get("nombre", "").strip()
    tipo = request.json.get("tipo", "").strip()
    info = request.json.get("info", "").strip()
    mapa = request.json.get("mapa", "").strip()
    servicios = request.json.get("servicios", [])

    if not nombre:
        return jsonify({"error": "El nombre del aula es obligatorio"}), 400

    bloque_ref = db.collection("bloques").document(bloque_id)
    if not bloque_ref.get().exists:
        return jsonify({"error": "El bloque especificado no existe"}), 404

    aula_id = nombre.replace(" ", "_")
    bloque_ref.collection("aulas").document(aula_id).set({
        "nombre": nombre,
        "tipo": tipo,
        "info": info,
        "mapa": mapa,
        "servicios": servicios
    })

    db.collection("logs").add({
        "accion": "crear_aula",
        "documento": f"{bloque_id}/{aula_id}",
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok", "id": aula_id})


@app.route("/api/bloques/<bloque_id>/aulas/<aula_id>", methods=["PUT"])
def editar_aula(bloque_id, aula_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    nombre = request.json.get("nombre", "").strip()
    tipo = request.json.get("tipo", "").strip()
    info = request.json.get("info", "").strip()
    mapa = request.json.get("mapa", "").strip()
    servicios = request.json.get("servicios", [])

    if not nombre:
        return jsonify({"error": "El nombre del aula es obligatorio"}), 400

    aula_ref = db.collection("bloques").document(bloque_id).collection("aulas").document(aula_id)
    if not aula_ref.get().exists:
        return jsonify({"error": "El aula no existe"}), 404

    cambios = {
        "nombre": nombre,
        "tipo": tipo,
        "info": info,
        "mapa": mapa,
        "servicios": servicios
    }
    aula_ref.update(cambios)

    db.collection("logs").add({
        "accion": "editar_aula",
        "documento": f"{bloque_id}/{aula_id}",
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "cambios": cambios,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


@app.route("/api/bloques/<bloque_id>/aulas/<aula_id>", methods=["DELETE"])
def eliminar_aula(bloque_id, aula_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    aula_ref = db.collection("bloques").document(bloque_id).collection("aulas").document(aula_id)
    if not aula_ref.get().exists:
        return jsonify({"error": "El aula no existe"}), 404

    aula_ref.delete()

    db.collection("logs").add({
        "accion": "eliminar_aula",
        "documento": f"{bloque_id}/{aula_id}",
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})

# ---------- Módulo 4 — Gestión de Áreas Comunes (Admin, Admin Junior, Editor) ----------
@app.route("/api/areas-comunes", methods=["GET"])
def listar_areas_comunes():
    areas = []
    for doc in db.collection("areas_comunes").stream():
        d = doc.to_dict()
        d["id"] = doc.id
        areas.append(d)
    return jsonify(areas)


@app.route("/api/areas-comunes", methods=["POST"])
def crear_area_comun():
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    nombre = request.json.get("nombre", "").strip()
    tipo = request.json.get("tipo", "").strip()
    info = request.json.get("info", "").strip()
    mapa = request.json.get("mapa", "").strip()
    servicios = request.json.get("servicios", [])

    if not nombre:
        return jsonify({"error": "El nombre es obligatorio"}), 400

    area_id = nombre.replace(" ", "_")
    db.collection("areas_comunes").document(area_id).set({
        "nombre": nombre,
        "tipo": tipo,
        "info": info,
        "mapa": mapa,
        "servicios": servicios
    })

    db.collection("logs").add({
        "accion": "crear_area_comun",
        "documento": area_id,
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok", "id": area_id})


@app.route("/api/areas-comunes/<area_id>", methods=["PUT"])
def editar_area_comun(area_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    nombre = request.json.get("nombre", "").strip()
    tipo = request.json.get("tipo", "").strip()
    info = request.json.get("info", "").strip()
    mapa = request.json.get("mapa", "").strip()
    servicios = request.json.get("servicios", [])

    if not nombre:
        return jsonify({"error": "El nombre es obligatorio"}), 400

    area_ref = db.collection("areas_comunes").document(area_id)
    if not area_ref.get().exists:
        return jsonify({"error": "El área no existe"}), 404

    cambios = {
        "nombre": nombre,
        "tipo": tipo,
        "info": info,
        "mapa": mapa,
        "servicios": servicios
    }
    area_ref.update(cambios)

    db.collection("logs").add({
        "accion": "editar_area_comun",
        "documento": area_id,
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "cambios": cambios,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


@app.route("/api/areas-comunes/<area_id>", methods=["DELETE"])
def eliminar_area_comun(area_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    area_ref = db.collection("areas_comunes").document(area_id)
    if not area_ref.get().exists:
        return jsonify({"error": "El área no existe"}), 404

    area_ref.delete()

    db.collection("logs").add({
        "accion": "eliminar_area_comun",
        "documento": area_id,
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})

# ---------- Módulo 6 — Favoritos (Admin/Admin Junior/Auditor: ranking + por estudiante) ----------
@app.route("/api/favoritos-ranking", methods=["POST"])
def favoritos_ranking():
    id_token = request.json.get("idToken")
    try:
        require_role(id_token, ["admin", "admin_junior", "auditor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    conteo = {}
    for doc in db.collection_group("favoritos").stream():
        conteo[doc.id] = conteo.get(doc.id, 0) + 1

    ranking = [{"espacio": k, "total": v} for k, v in conteo.items()]
    ranking.sort(key=lambda x: x["total"], reverse=True)

    return jsonify(ranking)


@app.route("/api/favoritos-por-estudiante/<estudiante_id>", methods=["POST"])
def favoritos_por_estudiante(estudiante_id):
    id_token = request.json.get("idToken")
    try:
        require_role(id_token, ["admin", "admin_junior", "auditor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    favoritos = []
    for doc in db.collection("usuarios").document(estudiante_id).collection("favoritos").stream():
        d = doc.to_dict()
        d["id"] = doc.id
        favoritos.append(d)

    return jsonify(favoritos)


# ---------- Módulo 6 — Favoritos del visitante web (sesión anónima propia) ----------
@app.route("/api/favoritos-visitante/<estudiante_id>", methods=["GET"])
def favoritos_visitante(estudiante_id):
    # Público dentro del flujo del visitante: no exige rol, solo el ID válido
    favoritos = []
    for doc in db.collection("usuarios").document(estudiante_id).collection("favoritos").stream():
        d = doc.to_dict()
        d["id"] = doc.id
        favoritos.append(d)
    return jsonify(favoritos)


@app.route("/api/busquedas-visitante/<estudiante_id>", methods=["GET"])
def busquedas_visitante(estudiante_id):
    busquedas = []
    for doc in db.collection("busquedas").where("estudiante_id", "==", estudiante_id).stream():
        d = doc.to_dict()
        d["id"] = doc.id
        busquedas.append(d)
    return jsonify(busquedas)
    
# ---------- Módulo 1 — Estadísticas generales (solo Admin) ----------
@app.route("/api/estadisticas", methods=["POST"])
def estadisticas():
    try:
        require_role(request.json.get("idToken"), ["admin", "admin_junior"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403
    return jsonify({
        "total_usuarios": 1240,
        "pct_estudiantes": 87,
        "pct_visitantes": 13,
        "activos_semana": 312
    })


# ---------- Espacios más buscados (Admin + Admin Junior + Auditor) ----------
@app.route("/api/espacios-populares", methods=["POST"])
def espacios_populares():
    try:
        require_role(request.json.get("idToken"), ["admin", "admin_junior", "auditor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403
    return jsonify({"ranking": [
        {"espacio": "Lab. de Redes", "busquedas": 154},
        {"espacio": "Aula 302", "busquedas": 121},
        {"espacio": "Auditorio Central", "busquedas": 98}
    ]})


# ---------- Auditoría (Admin + Admin Junior + Auditor) ----------
@app.route("/api/auditoria", methods=["POST"])
def auditoria():
    try:
        require_role(request.json.get("idToken"), ["admin", "admin_junior", "auditor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403
    logs = db.collection("logs").order_by(
        "timestamp", direction="DESCENDING"
    ).limit(50).stream()
    return jsonify([l.to_dict() for l in logs])


# ---------- Listado de usuarios con cédula descifrada (Admin + Admin Junior + Auditor) ----------
@app.route("/api/usuarios", methods=["POST"])
def listar_usuarios():
    id_token = request.json.get("idToken")
    try:
        require_role(id_token, ["admin", "admin_junior", "auditor"])
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


@app.route("/api/popularidad-espacios", methods=["POST"])
def popularidad_espacios():
    id_token = request.json.get("idToken")
    try:
        require_role(id_token, ["admin", "admin_junior", "auditor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    conteo_busquedas = {}
    for doc in db.collection("busquedas").stream():
        espacio = doc.to_dict().get("espacio_id")
        if espacio:
            conteo_busquedas[espacio] = conteo_busquedas.get(espacio, 0) + 1

    conteo_favoritos = {}
    for doc in db.collection_group("favoritos").stream():
        conteo_favoritos[doc.id] = conteo_favoritos.get(doc.id, 0) + 1

    return jsonify({
        "busquedas": conteo_busquedas,
        "favoritos": conteo_favoritos
    })


# ---------- Espacios públicos (visitante, sin login) ----------
@app.route("/api/espacios-publicos", methods=["GET"])
def espacios_publicos():
    espacios = db.collection("espacios").where("publico", "==", True).stream()
    return jsonify([e.to_dict() for e in espacios])


if __name__ == "__main__":
    app.run(debug=True, port=5000)