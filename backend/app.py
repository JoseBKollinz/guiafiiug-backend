import os
import re
import requests
from datetime import datetime, timedelta, timezone
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


def validar_password_segura(password):
    if len(password) < 8:
        return "La contraseña debe tener al menos 8 caracteres"
    if not re.search(r"[A-Z]", password):
        return "La contraseña debe incluir al menos una mayúscula"
    if not re.search(r"[a-z]", password):
        return "La contraseña debe incluir al menos una minúscula"
    if not re.search(r"[0-9]", password):
        return "La contraseña debe incluir al menos un número"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-]", password):
        return "La contraseña debe incluir al menos un carácter especial"
    return None


# ---------- Login / verificación de token (con auditoría) ----------
@app.route("/api/verify", methods=["POST"])
def verify():
    id_token = request.json.get("idToken")
    try:
        role, uid = get_role_from_token(id_token)
        if not role:
            return jsonify({"error": "Usuario sin rol asignado"}), 403

        admin_doc = db.collection("usuarios_admin").document(uid).get()
        debe_cambiar = admin_doc.to_dict().get("debe_cambiar_password", False) if admin_doc.exists else False

        db.collection("logs").add({
            "usuario_uid": uid,
            "usuario_nombre": obtener_nombre_usuario(uid),
            "accion": "login",
            "resultado": "exito",
            "rol": role,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "ip": request.remote_addr
        })

        return jsonify({"role": role, "uid": uid, "debe_cambiar_password": debe_cambiar})
    except Exception as e:
        db.collection("logs").add({
            "accion": "login",
            "resultado": "fallido",
            "error": str(e),
            "timestamp": firestore.SERVER_TIMESTAMP,
            "ip": request.remote_addr
        })
        return jsonify({"error": str(e)}), 401


@app.route("/api/registrar-login-fallido", methods=["POST"])
def registrar_login_fallido():
    email = request.json.get("email", "desconocido")

    db.collection("logs").add({
        "accion": "login",
        "resultado": "fallido",
        "email_intentado": email,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


@app.route("/api/logout-inactividad", methods=["POST"])
def logout_inactividad():
    id_token = request.json.get("idToken")
    try:
        decoded = fb_auth.verify_id_token(id_token)
        uid = decoded["uid"]
        role = decoded.get("role")
    except Exception:
        return jsonify({"error": "Sesión inválida"}), 401

    db.collection("logs").add({
        "accion": "logout_inactividad",
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


@app.route("/api/cambiar-password", methods=["POST"])
def cambiar_password():
    id_token = request.json.get("idToken")
    password_actual = request.json.get("passwordActual", "")
    password_nueva = request.json.get("passwordNueva", "")
    password_confirmar = request.json.get("passwordConfirmar", "")

    try:
        decoded = fb_auth.verify_id_token(id_token)
        uid = decoded["uid"]
        email = decoded.get("email")
    except Exception:
        return jsonify({"error": "Sesión inválida"}), 401

    if password_nueva != password_confirmar:
        return jsonify({"error": "Las contraseñas nuevas no coinciden"}), 400

    error_validacion = validar_password_segura(password_nueva)
    if error_validacion:
        return jsonify({"error": error_validacion}), 400

    firebase_api_key = os.environ.get("FIREBASE_API_KEY")
    verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}"
    resp = requests.post(verify_url, json={
        "email": email,
        "password": password_actual,
        "returnSecureToken": True
    })

    if resp.status_code != 200:
        return jsonify({"error": "La contraseña actual es incorrecta"}), 401

    fb_auth.update_user(uid, password=password_nueva)
    db.collection("usuarios_admin").document(uid).update({"debe_cambiar_password": False})

    db.collection("logs").add({
        "accion": "cambio_password",
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


# ---------- Registro de estudiante (cifra la cédula antes de guardar) ----------
@app.route("/api/registrar-estudiante", methods=["POST"])
def registrar_estudiante():
    data = request.json
    nombre = data.get("nombre")
    apellido = data.get("apellido")
    cedula = data.get("cedula")
    id_token = data.get("idToken")

    if not (nombre and apellido and cedula):
        return jsonify({"error": "Faltan datos"}), 400

    cedula_cifrada = encriptar_cedula(cedula)
    cedula_hash = hash_cedula(cedula)

    existente = db.collection("usuarios").where("cedula_hash", "==", cedula_hash).limit(1).stream()
    if list(existente):
        return jsonify({"error": "Ya existe un estudiante registrado con esa cédula"}), 400

    nuevo_doc = db.collection("usuarios").document()
    nuevo_doc.set({
        "nombre": nombre,
        "apellido": apellido,
        "cedula": cedula_cifrada,
        "cedula_hash": cedula_hash,
        "fechaRegistro": firestore.SERVER_TIMESTAMP
    })

    log_data = {
        "accion": "registro_estudiante",
        "documento": nuevo_doc.id,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    }

    if id_token:
        try:
            role, uid = get_role_from_token(id_token)
            log_data["usuario_uid"] = uid
            log_data["usuario_nombre"] = obtener_nombre_usuario(uid)
            log_data["rol"] = role
        except Exception:
            pass

    db.collection("logs").add(log_data)

    return jsonify({"status": "ok", "id": nuevo_doc.id})


@app.route("/api/buscar-usuario", methods=["POST"])
def buscar_usuario():
    cedula = request.json.get("cedula", "").strip()
    apellido = request.json.get("apellido", "").strip()

    if not cedula or not apellido:
        return jsonify({"error": "Cédula y apellido son obligatorios"}), 400

    hash_buscado = hash_cedula(cedula)
    query = db.collection("usuarios").where("cedula_hash", "==", hash_buscado).limit(1).stream()
    resultado = list(query)

    if not resultado:
        db.collection("logs").add({
            "accion": "acceso_visitante",
            "resultado": "fallido",
            "motivo": "cedula_no_encontrada",
            "timestamp": firestore.SERVER_TIMESTAMP,
            "ip": request.remote_addr
        })
        return jsonify({"error": "No encontramos ningún registro con esos datos"}), 404

    doc = resultado[0]
    datos = doc.to_dict()
    apellido_real = datos.get("apellido", "").strip().lower()

    if apellido_real != apellido.lower():
        db.collection("logs").add({
            "accion": "acceso_visitante",
            "resultado": "fallido",
            "motivo": "apellido_incorrecto",
            "documento": doc.id,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "ip": request.remote_addr
        })
        return jsonify({"error": "No encontramos ningún registro con esos datos"}), 404

    db.collection("logs").add({
        "accion": "acceso_visitante",
        "resultado": "exito",
        "documento": doc.id,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"id": doc.id})


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


@app.route("/api/aulas-resumen", methods=["GET"])
def aulas_resumen():
    bloques_docs = list(db.collection("bloques").stream())

    aulas_por_bloque = {}
    servicios_conteo = {}
    tipos_conteo = {}
    total_aulas = 0

    for b in bloques_docs:
        aulas = list(db.collection("bloques").document(b.id).collection("aulas").stream())
        aulas_por_bloque[b.to_dict().get("nombre", b.id)] = len(aulas)
        total_aulas += len(aulas)

        for a in aulas:
            data = a.to_dict()
            for s in data.get("servicios", []):
                servicios_conteo[s] = servicios_conteo.get(s, 0) + 1
            tipo = data.get("tipo", "Sin tipo")
            tipos_conteo[tipo] = tipos_conteo.get(tipo, 0) + 1

    return jsonify({
        "total_aulas": total_aulas,
        "total_bloques": len(bloques_docs),
        "aulas_por_bloque": aulas_por_bloque,
        "servicios_conteo": servicios_conteo,
        "tipos_conteo": tipos_conteo
    })


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


# ---------- Edición de "lugares_info" desde la app móvil (Admin, Admin Junior, Editor) ----------
# Esta colección la usa la app Android para ediciones rápidas de información
# de un lugar (descripción, cómo llegar, servicios) sin pasar por la
# estructura jerárquica bloques/aulas. Se mantiene separada por decisión
# de diseño, pero ahora pasa por el backend para quedar auditada y protegida.
@app.route("/api/lugares-info/<lugar_id>", methods=["GET"])
def obtener_lugar_info(lugar_id):
    doc = db.collection("lugares_info").document(lugar_id).get()
    if not doc.exists:
        return jsonify({"error": "El lugar no existe"}), 404
    d = doc.to_dict()
    d["id"] = doc.id
    return jsonify(d)


@app.route("/api/lugares-info/<lugar_id>", methods=["PUT"])
def editar_lugar_info(lugar_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    nombre = request.json.get("nombre", "").strip()
    descripcion = request.json.get("descripcion", "").strip()
    info = request.json.get("info", "").strip()
    comoLlegar = request.json.get("comoLlegar", "").strip()
    tipo = request.json.get("tipo", "").strip()
    servicios = request.json.get("servicios", [])

    if not nombre:
        return jsonify({"error": "El nombre es obligatorio"}), 400

    lugar_ref = db.collection("lugares_info").document(lugar_id)

    cambios = {
        "nombre": nombre,
        "descripcion": descripcion,
        "info": info,
        "comoLlegar": comoLlegar,
        "tipo": tipo,
        "servicios": servicios
    }
    lugar_ref.set(cambios, merge=True)

    db.collection("logs").add({
        "accion": "editar_lugar_info",
        "documento": lugar_id,
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "cambios": cambios,
        "resultado": "exito",
        "origen": "app_movil",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


# ---------- Módulo 5 — Mapa de popularidad de búsquedas (Admin/Admin Junior/Auditor) ----------
@app.route("/api/busquedas-ranking", methods=["POST"])
def busquedas_ranking():
    id_token = request.json.get("idToken")
    try:
        require_role(id_token, ["admin", "admin_junior", "auditor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    conteo = {}
    for doc in db.collection("busquedas").stream():
        espacio = doc.to_dict().get("espacio_encontrado")
        if espacio:
            conteo[espacio] = conteo.get(espacio, 0) + 1

    ranking = [{"espacio": k, "total": v} for k, v in conteo.items()]
    ranking.sort(key=lambda x: x["total"], reverse=True)

    return jsonify(ranking)


@app.route("/api/busquedas-recientes", methods=["POST"])
def busquedas_recientes():
    id_token = request.json.get("idToken")
    try:
        require_role(id_token, ["admin", "admin_junior", "auditor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    limite = int(request.json.get("limite", 20))
    docs = db.collection("busquedas").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limite).stream()

    resultado = []
    for doc in docs:
        d = doc.to_dict()
        d["id"] = doc.id
        resultado.append(d)

    return jsonify(resultado)


@app.route("/api/busquedas-visitante/<estudiante_id>", methods=["GET"])
def busquedas_visitante(estudiante_id):
    # Nota: actualmente no hay relación verificable entre uid_usuario (anónimo)
    # y el usuario_id real del estudiante. Ver limitación documentada.
    busquedas = []
    for doc in db.collection("busquedas").where("usuario_id", "==", estudiante_id).stream():
        d = doc.to_dict()
        d["id"] = doc.id
        busquedas.append(d)
    return jsonify(busquedas)


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


@app.route("/api/favoritos-visitante/<estudiante_id>", methods=["GET"])
def favoritos_visitante(estudiante_id):
    favoritos = []
    for doc in db.collection("usuarios").document(estudiante_id).collection("favoritos").stream():
        d = doc.to_dict()
        d["id"] = doc.id
        favoritos.append(d)
    return jsonify(favoritos)


# ---------- Módulo 1 — Estadísticas generales (Admin, Admin Junior) ----------
@app.route("/api/estadisticas", methods=["POST"])
def estadisticas():
    try:
        require_role(request.json.get("idToken"), ["admin", "admin_junior"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    total_usuarios = db.collection("usuarios").count().get()[0][0].value
    total_areas = db.collection("areas_comunes").count().get()[0][0].value
    total_favoritos = db.collection_group("favoritos").count().get()[0][0].value

    bloques_docs = list(db.collection("bloques").stream())
    total_bloques = len(bloques_docs)

    total_aulas = 0
    for b in bloques_docs:
        conteo_aulas = db.collection("bloques").document(b.id).collection("aulas").count().get()[0][0].value
        total_aulas += conteo_aulas

    admins_docs = list(db.collection("usuarios_admin").stream())
    conteo_roles = {}
    for a in admins_docs:
        rol = a.to_dict().get("role", "sin_rol")
        conteo_roles[rol] = conteo_roles.get(rol, 0) + 1

    hace_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    logins_recientes = 0
    logins_fallidos = 0
    logs_login_docs = db.collection("logs").where("accion", "==", "login").limit(500).stream()
    for doc in logs_login_docs:
        d = doc.to_dict()
        ts = d.get("timestamp")
        if not ts or ts < hace_24h:
            continue
        if d.get("resultado") == "exito":
            logins_recientes += 1
        else:
            logins_fallidos += 1

    hoy = datetime.now(timezone.utc).date()
    dias = [(hoy - timedelta(days=i)) for i in range(6, -1, -1)]
    logins_por_dia = {d.isoformat(): {"exitosos": 0, "fallidos": 0} for d in dias}

    hace_7_dias = datetime.now(timezone.utc) - timedelta(days=7)
    logs_semana = db.collection("logs").where("accion", "==", "login").limit(500).stream()
    for doc in logs_semana:
        d = doc.to_dict()
        ts = d.get("timestamp")
        if not ts or ts < hace_7_dias:
            continue
        fecha_str = ts.date().isoformat()
        if fecha_str in logins_por_dia:
            if d.get("resultado") == "exito":
                logins_por_dia[fecha_str]["exitosos"] += 1
            else:
                logins_por_dia[fecha_str]["fallidos"] += 1

    return jsonify({
        "total_usuarios": total_usuarios,
        "total_bloques": total_bloques,
        "total_aulas": total_aulas,
        "total_areas_comunes": total_areas,
        "total_favoritos": total_favoritos,
        "administradores_por_rol": conteo_roles,
        "logins_ultimas_24h": logins_recientes,
        "logins_fallidos_ultimas_24h": logins_fallidos,
        "logins_por_dia": logins_por_dia
    })


# ---------- Módulo 12 — Configuración del Sistema (Admin) ----------
@app.route("/api/configuracion", methods=["GET"])
def obtener_configuracion():
    doc = db.collection("configuracion").document("sistema").get()
    if doc.exists:
        return jsonify(doc.to_dict())

    return jsonify({
        "nombre_facultad": "Facultad de Ingeniería Industrial",
        "periodo_academico": "2026-2027",
        "logo_url": "",
        "duracion_sesion_minutos": 60,
        "limite_resultados_busqueda": 20
    })


@app.route("/api/configuracion", methods=["PUT"])
def actualizar_configuracion():
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    nombre_facultad = request.json.get("nombre_facultad", "").strip()
    periodo_academico = request.json.get("periodo_academico", "").strip()
    logo_url = request.json.get("logo_url", "").strip()
    duracion_sesion = request.json.get("duracion_sesion_minutos")
    limite_resultados = request.json.get("limite_resultados_busqueda")

    if not (nombre_facultad and periodo_academico):
        return jsonify({"error": "Nombre de facultad y periodo académico son obligatorios"}), 400

    try:
        duracion_sesion = int(duracion_sesion)
        limite_resultados = int(limite_resultados)
    except (TypeError, ValueError):
        return jsonify({"error": "Duración de sesión y límite de resultados deben ser números"}), 400

    if duracion_sesion < 5 or duracion_sesion > 480:
        return jsonify({"error": "La duración de sesión debe estar entre 5 y 480 minutos"}), 400

    if limite_resultados < 5 or limite_resultados > 100:
        return jsonify({"error": "El límite de resultados debe estar entre 5 y 100"}), 400

    nueva_config = {
        "nombre_facultad": nombre_facultad,
        "periodo_academico": periodo_academico,
        "logo_url": logo_url,
        "duracion_sesion_minutos": duracion_sesion,
        "limite_resultados_busqueda": limite_resultados
    }

    db.collection("configuracion").document("sistema").set(nueva_config)

    db.collection("logs").add({
        "accion": "editar_configuracion",
        "documento": "sistema",
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "cambios": nueva_config,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


@app.route("/api/config-fotos", methods=["GET"])
def obtener_config_fotos():
    doc = db.collection("configuracion").document("app_movil").get()
    if doc.exists:
        return jsonify(doc.to_dict())
    return jsonify({"fotosHabilitadas": True})


@app.route("/api/config-fotos", methods=["PUT"])
def actualizar_config_fotos():
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    doc_ref = db.collection("configuracion").document("app_movil")
    actual = doc_ref.get().to_dict() or {"fotosHabilitadas": True}
    nuevo_valor = not actual.get("fotosHabilitadas", True)
    doc_ref.set({"fotosHabilitadas": nuevo_valor})

    db.collection("logs").add({
        "accion": "toggle_subida_fotos",
        "documento": "app_movil",
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "cambios": {"fotosHabilitadas": nuevo_valor},
        "resultado": "exito",
        "origen": "app_movil",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok", "fotosHabilitadas": nuevo_valor})


# ---------- Auditoría (Admin, Admin Junior, Auditor) ----------
@app.route("/api/auditoria", methods=["POST"])
def auditoria():
    try:
        require_role(request.json.get("idToken"), ["admin", "admin_junior", "auditor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    limite = int(request.json.get("limite", 100))
    query = db.collection("logs").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limite)

    logs = []
    for doc in query.stream():
        d = doc.to_dict()
        d["id"] = doc.id
        logs.append(d)

    return jsonify(logs)


# ---------- Listado de usuarios con cédula descifrada (Admin, Admin Junior, Auditor) ----------
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
        d["id"] = doc.id
        try:
            d["cedula"] = desencriptar_cedula(d["cedula"])
        except Exception:
            d["cedula"] = "(dato antiguo sin cifrar o corrupto)"
        resultado.append(d)

    return jsonify(resultado)


@app.route("/api/usuarios/<estudiante_id>", methods=["PUT"])
def editar_usuario(estudiante_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    nombre = request.json.get("nombre", "").strip()
    apellido = request.json.get("apellido", "").strip()

    if not (nombre and apellido):
        return jsonify({"error": "Nombre y apellido son obligatorios"}), 400

    est_ref = db.collection("usuarios").document(estudiante_id)
    if not est_ref.get().exists:
        return jsonify({"error": "El estudiante no existe"}), 404

    est_ref.update({"nombre": nombre, "apellido": apellido})

    db.collection("logs").add({
        "accion": "editar_usuario",
        "documento": estudiante_id,
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "cambios": {"nombre": nombre, "apellido": apellido},
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


@app.route("/api/usuarios/<estudiante_id>", methods=["DELETE"])
def eliminar_usuario(estudiante_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    est_ref = db.collection("usuarios").document(estudiante_id)
    if not est_ref.get().exists:
        return jsonify({"error": "El estudiante no existe"}), 404

    est_ref.delete()

    db.collection("logs").add({
        "accion": "eliminar_usuario",
        "documento": estudiante_id,
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


# ---------- Módulo 8 — Gestión de Administradores (Admin) ----------
ROLES_ASIGNABLES = ["admin_junior", "editor", "auditor"]


@app.route("/api/administradores", methods=["POST"])
def listar_administradores():
    id_token = request.json.get("idToken")
    try:
        require_role(id_token, ["admin"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    admins = []
    for doc in db.collection("usuarios_admin").stream():
        d = doc.to_dict()
        d["uid"] = doc.id
        admins.append(d)
    return jsonify(admins)


@app.route("/api/administradores/crear", methods=["POST"])
def crear_administrador():
    id_token = request.json.get("idToken")
    try:
        role, uid_actor = require_role(id_token, ["admin"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    nombre = request.json.get("nombre", "").strip()
    email = request.json.get("email", "").strip()
    password = request.json.get("password", "").strip()
    rol_nuevo = request.json.get("role", "").strip()

    if not (nombre and email and password and rol_nuevo):
        return jsonify({"error": "Todos los campos son obligatorios"}), 400

    if rol_nuevo not in ROLES_ASIGNABLES:
        return jsonify({"error": "Rol no permitido. Solo se pueden crear: admin_junior, editor, auditor"}), 400

    if len(password) < 8:
        return jsonify({"error": "La contraseña debe tener al menos 8 caracteres"}), 400

    try:
        nuevo_user = fb_auth.create_user(email=email, password=password, display_name=nombre)
        fb_auth.set_custom_user_claims(nuevo_user.uid, {"role": rol_nuevo})

        db.collection("usuarios_admin").document(nuevo_user.uid).set({
            "nombre": nombre,
            "email": email,
            "role": rol_nuevo,
            "debe_cambiar_password": True
        })

        db.collection("logs").add({
            "accion": "crear_administrador",
            "documento": nuevo_user.uid,
            "usuario_uid": uid_actor,
            "usuario_nombre": obtener_nombre_usuario(uid_actor),
            "rol": role,
            "cambios": {"nombre": nombre, "email": email, "role": rol_nuevo},
            "resultado": "exito",
            "timestamp": firestore.SERVER_TIMESTAMP,
            "ip": request.remote_addr
        })

        return jsonify({"status": "ok", "uid": nuevo_user.uid})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/administradores/<admin_uid>", methods=["PUT"])
def editar_administrador(admin_uid):
    id_token = request.json.get("idToken")
    try:
        role, uid_actor = require_role(id_token, ["admin"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    nombre = request.json.get("nombre", "").strip()
    rol_nuevo = request.json.get("role", "").strip()

    if not (nombre and rol_nuevo):
        return jsonify({"error": "Nombre y rol son obligatorios"}), 400

    if rol_nuevo not in ROLES_ASIGNABLES:
        return jsonify({"error": "Rol no permitido. Solo se puede asignar: admin_junior, editor, auditor"}), 400

    admin_ref = db.collection("usuarios_admin").document(admin_uid)
    doc = admin_ref.get()
    if not doc.exists:
        return jsonify({"error": "El administrador no existe"}), 404

    if doc.to_dict().get("role") == "admin":
        return jsonify({"error": "No se puede modificar una cuenta admin desde este módulo"}), 403

    fb_auth.update_user(admin_uid, display_name=nombre)
    fb_auth.set_custom_user_claims(admin_uid, {"role": rol_nuevo})
    admin_ref.update({"nombre": nombre, "role": rol_nuevo})

    db.collection("logs").add({
        "accion": "editar_administrador",
        "documento": admin_uid,
        "usuario_uid": uid_actor,
        "usuario_nombre": obtener_nombre_usuario(uid_actor),
        "rol": role,
        "cambios": {"nombre": nombre, "role": rol_nuevo},
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


@app.route("/api/administradores/<admin_uid>", methods=["DELETE"])
def eliminar_administrador(admin_uid):
    id_token = request.json.get("idToken")
    try:
        role, uid_actor = require_role(id_token, ["admin"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    if admin_uid == uid_actor:
        return jsonify({"error": "No puedes eliminar tu propia cuenta"}), 400

    admin_ref = db.collection("usuarios_admin").document(admin_uid)
    doc = admin_ref.get()
    if not doc.exists:
        return jsonify({"error": "El administrador no existe"}), 404

    if doc.to_dict().get("role") == "admin":
        return jsonify({"error": "No se puede eliminar una cuenta admin desde este módulo"}), 403

    fb_auth.delete_user(admin_uid)
    admin_ref.delete()

    db.collection("logs").add({
        "accion": "eliminar_administrador",
        "documento": admin_uid,
        "usuario_uid": uid_actor,
        "usuario_nombre": obtener_nombre_usuario(uid_actor),
        "rol": role,
        "resultado": "exito",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


# ---------- Moderación de fotos (Admin, Admin Junior, Editor) ----------
@app.route("/api/fotos-lugares", methods=["POST"])
def listar_fotos_lugares():
    id_token = request.json.get("idToken")
    try:
        require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    fotos = []
    for doc in db.collection("fotos_lugares").stream():
        d = doc.to_dict()
        d["id"] = doc.id
        fotos.append(d)
    return jsonify(fotos)


@app.route("/api/fotos-lugares/<foto_id>", methods=["DELETE"])
def eliminar_foto_lugar(foto_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    foto_ref = db.collection("fotos_lugares").document(foto_id)
    doc = foto_ref.get()
    if not doc.exists:
        return jsonify({"error": "La foto no existe"}), 404

    lugar_id = doc.to_dict().get("lugarId", "desconocido")
    foto_ref.delete()

    db.collection("logs").add({
        "accion": "eliminar_foto",
        "documento": f"{lugar_id} ({foto_id})",
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "resultado": "exito",
        "origen": "app_movil",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


# ---------- Reportes de usuarios (Admin, Admin Junior, Editor) ----------
@app.route("/api/reportes", methods=["POST"])
def listar_reportes():
    id_token = request.json.get("idToken")
    try:
        require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    solo_pendientes = request.json.get("soloPendientes", True)
    query = db.collection("reportes")
    if solo_pendientes:
        query = query.where("resuelto", "==", False)

    reportes = []
    for doc in query.stream():
        d = doc.to_dict()
        d["id"] = doc.id
        reportes.append(d)
    return jsonify(reportes)


@app.route("/api/reportes/<reporte_id>/resolver", methods=["PUT"])
def resolver_reporte(reporte_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    reporte_ref = db.collection("reportes").document(reporte_id)
    doc = reporte_ref.get()
    if not doc.exists:
        return jsonify({"error": "El reporte no existe"}), 404

    reporte_ref.update({"resuelto": True})

    db.collection("logs").add({
        "accion": "resolver_reporte",
        "documento": reporte_id,
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "resultado": "exito",
        "origen": "app_movil",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})


@app.route("/api/reportes/<reporte_id>", methods=["DELETE"])
def eliminar_reporte(reporte_id):
    id_token = request.json.get("idToken")
    try:
        role, uid = require_role(id_token, ["admin", "admin_junior", "editor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    reporte_ref = db.collection("reportes").document(reporte_id)
    if not reporte_ref.get().exists:
        return jsonify({"error": "El reporte no existe"}), 404

    reporte_ref.delete()

    db.collection("logs").add({
        "accion": "eliminar_reporte",
        "documento": reporte_id,
        "usuario_uid": uid,
        "usuario_nombre": obtener_nombre_usuario(uid),
        "rol": role,
        "resultado": "exito",
        "origen": "app_movil",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "ip": request.remote_addr
    })

    return jsonify({"status": "ok"})

@app.route("/api/lugares-info", methods=["POST"])
def listar_lugares_info():
    id_token = request.json.get("idToken")
    try:
        require_role(id_token, ["admin", "admin_junior", "auditor"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    lugares = []
    for doc in db.collection("lugares_info").limit(100).stream():
        d = doc.to_dict()
        d["id"] = doc.id
        lugares.append(d)
    return jsonify(lugares)

@app.route("/lugar/<lugar_id>")
def compartir_lugar(lugar_id):
    nombre_lugar = lugar_id.replace("_", " ")
    info_extra = ""

    for bloque in db.collection("bloques").stream():
        aula_ref = db.collection("bloques").document(bloque.id).collection("aulas").document(lugar_id)
        aula_doc = aula_ref.get()
        if aula_doc.exists:
            d = aula_doc.to_dict()
            nombre_lugar = d.get("nombre", nombre_lugar)
            info_extra = d.get("info", "")
            break

    if not info_extra:
        area_doc = db.collection("areas_comunes").document(lugar_id).get()
        if area_doc.exists:
            d = area_doc.to_dict()
            nombre_lugar = d.get("nombre", nombre_lugar)
            info_extra = d.get("info", "")

    deep_link = f"mapafii://lugar?id={lugar_id}"

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{nombre_lugar} — Sistema de Gestión de Espacios</title>
        <style>
            body {{
                font-family: 'Segoe UI', system-ui, sans-serif;
                background: #071620;
                color: #fff;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                padding: 24px;
                text-align: center;
            }}
            h1 {{ font-size: 22px; margin-bottom: 8px; }}
            p {{ color: #9fb8c2; font-size: 14px; max-width: 320px; }}
            .btn {{
                margin-top: 20px;
                padding: 12px 28px;
                background: linear-gradient(90deg, #0a3d42, #2fd4d4);
                color: #fff;
                border-radius: 24px;
                text-decoration: none;
                font-weight: 600;
                font-size: 14px;
            }}
            .spinner {{
                margin-top: 24px;
                font-size: 12px;
                color: #5a7684;
            }}
        </style>
    </head>
    <body>
        <h1>📍 {nombre_lugar}</h1>
        <p>{info_extra or "Abriendo en la app del campus..."}</p>
        <a class="btn" href="{deep_link}">Abrir en la app</a>
        <p class="spinner">Si no se abre automáticamente, toca el botón de arriba.</p>

        <script>
            window.location.href = "{deep_link}";
        </script>
    </body>
    </html>
    """
    return html
    
# ---------- Espacios públicos (visitante, sin login) ----------
@app.route("/api/espacios-publicos", methods=["GET"])
def espacios_publicos():
    espacios = db.collection("espacios").where("publico", "==", True).stream()
    return jsonify([e.to_dict() for e in espacios])


if __name__ == "__main__":
    app.run(debug=True, port=5000)