import os
import re
import requests
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

        # Revisa si debe cambiar contraseña
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
    
# ---------- Registro de estudiante (cifra la cédula antes de guardar) ----------
@app.route("/api/registrar-estudiante", methods=["POST"])
def registrar_estudiante():
    data = request.json
    nombre = data.get("nombre")
    apellido = data.get("apellido")
    cedula = data.get("cedula")
    id_token = data.get("idToken")  # opcional, solo viene si es desde el dashboard

    if not (nombre and apellido and cedula):
        return jsonify({"error": "Faltan datos"}), 400

    cedula_cifrada = encriptar_cedula(cedula)
    cedula_hash = hash_cedula(cedula)

    # Evita duplicados: si la cédula ya existe, no crear otro documento
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

    # Si vino con token (dashboard), añade quién lo hizo
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

    # Conteos con count() -> 1 sola lectura cada uno, sin importar cuántos documentos haya
    total_usuarios = db.collection("usuarios").count().get()[0][0].value
    total_areas = db.collection("areas_comunes").count().get()[0][0].value
    total_favoritos = db.collection_group("favoritos").count().get()[0][0].value

    # Bloques: necesitamos sus nombres para otros gráficos, así que sí traemos los documentos
    # (son pocos, 7 en tu caso, no es costoso)
    bloques_docs = list(db.collection("bloques").stream())
    total_bloques = len(bloques_docs)

    # Aulas por bloque: aquí sí necesitamos el conteo POR bloque, usamos count() por cada uno
    total_aulas = 0
    for b in bloques_docs:
        conteo_aulas = db.collection("bloques").document(b.id).collection("aulas").count().get()[0][0].value
        total_aulas += conteo_aulas

    # Administradores por rol (son pocos, count() no aplica bien aquí porque necesitamos agrupar por campo)
    admins_docs = list(db.collection("usuarios_admin").stream())
    conteo_roles = {}
    for a in admins_docs:
        rol = a.to_dict().get("role", "sin_rol")
        conteo_roles[rol] = conteo_roles.get(rol, 0) + 1

    # Logins 24h (necesitamos leer documentos para filtrar por timestamp, pero limitamos)
    from datetime import datetime, timedelta, timezone
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

    # Logins por día (últimos 7 días) - reutiliza los mismos docs ya traídos arriba si quieres optimizar más,
    # pero por simplicidad hacemos una segunda pasada con límite
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
    try:
        require_role(request.json.get("idToken"), ["admin", "admin_junior"])
    except PermissionError:
        return jsonify({"error": "Acceso denegado"}), 403

    # Total de estudiantes registrados
    total_usuarios = db.collection("usuarios").count().get()[0][0].value

    # Total de bloques y aulas
    bloques_docs = list(db.collection("bloques").stream())
    total_bloques = len(bloques_docs)
    total_aulas = 0
    for b in bloques_docs:
        total_aulas += len(list(db.collection("bloques").document(b.id).collection("aulas").stream()))

    # Total de áreas comunes
    total_areas = len(list(db.collection("areas_comunes").stream()))

    # Total de favoritos (todas las subcolecciones)
    total_favoritos = len(list(db.collection_group("favoritos").stream()))

    # Total de administradores por rol
    admins_docs = list(db.collection("usuarios_admin").stream())
    conteo_roles = {}
    for a in admins_docs:
        rol = a.to_dict().get("role", "sin_rol")
        conteo_roles[rol] = conteo_roles.get(rol, 0) + 1

    # Actividad reciente: logins en las últimas 24 horas
    from datetime import datetime, timedelta, timezone
    hace_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    logins_recientes = 0
    for doc in db.collection("logs").where("accion", "==", "login").where("resultado", "==", "exito").stream():
        ts = doc.to_dict().get("timestamp")
        if ts and ts >= hace_24h:
            logins_recientes += 1

    # Intentos de login fallidos en las últimas 24 horas (señal de seguridad)
    logins_fallidos = 0
    for doc in db.collection("logs").where("accion", "==", "login").where("resultado", "==", "fallido").stream():
        ts = doc.to_dict().get("timestamp")
        if ts and ts >= hace_24h:
            logins_fallidos += 1

# Conteo de acciones por tipo (últimos 100 logs, para no sobrecargar)
    # Logins exitosos y fallidos agrupados por día (últimos 7 días)
    from datetime import datetime, timedelta, timezone
    hoy = datetime.now(timezone.utc).date()
    dias = [(hoy - timedelta(days=i)) for i in range(6, -1, -1)]  # últimos 7 días, en orden

    logins_por_dia = {d.isoformat(): {"exitosos": 0, "fallidos": 0} for d in dias}

    hace_7_dias = datetime.now(timezone.utc) - timedelta(days=7)
    logs_login = db.collection("logs").where("accion", "==", "login").stream()

    for doc in logs_login:
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

# ---------- Módulo 12 — Configuración del Sistema (solo Admin) ----------
@app.route("/api/configuracion", methods=["GET"])
def obtener_configuracion():
    doc = db.collection("configuracion").document("sistema").get()
    if doc.exists:
        return jsonify(doc.to_dict())

    # Valores por defecto si nunca se ha configurado
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

    limite = int(request.json.get("limite", 100))
    query = db.collection("logs").order_by("timestamp", direction="DESCENDING").limit(limite)

    logs = []
    for doc in query.stream():
        d = doc.to_dict()
        d["id"] = doc.id
        logs.append(d)

    return jsonify(logs)

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
        d["id"] = doc.id   # ← agrega esta línea si no está
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

# ---------- Módulo 8 — Gestión de Administradores (solo Admin) ----------
ROLES_ASIGNABLES = ["admin_junior", "editor", "auditor"]  # admin NO se puede crear desde aquí


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


@app.route("/api/administradores", methods=["POST" ])
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
    "debe_cambiar_password": True   # ← nuevo
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

    # No permitir editar cuentas con rol "admin" desde este módulo (protección extra)
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

    # Protección: no puede eliminarse a sí mismo
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
    bloques_docs = list(db.collection("bloques").stream())

    aulas_por_bloque = {}
    servicios_conteo = {}
    total_aulas = 0

    for b in bloques_docs:
        aulas = list(db.collection("bloques").document(b.id).collection("aulas").stream())
        aulas_por_bloque[b.to_dict().get("nombre", b.id)] = len(aulas)
        total_aulas += len(aulas)

        for a in aulas:
            servicios = a.to_dict().get("servicios", [])
            for s in servicios:
                servicios_conteo[s] = servicios_conteo.get(s, 0) + 1

    tipos_conteo = {}
    for b in bloques_docs:
        for a in db.collection("bloques").document(b.id).collection("aulas").stream():
            tipo = a.to_dict().get("tipo", "Sin tipo")
            tipos_conteo[tipo] = tipos_conteo.get(tipo, 0) + 1

    return jsonify({
        "total_aulas": total_aulas,
        "total_bloques": len(bloques_docs),
        "aulas_por_bloque": aulas_por_bloque,
        "servicios_conteo": servicios_conteo,
        "tipos_conteo": tipos_conteo
    })
    return jsonify({"status": "ok"})
# ---------- Espacios públicos (visitante, sin login) ----------
@app.route("/api/espacios-publicos", methods=["GET"])
def espacios_publicos():
    espacios = db.collection("espacios").where("publico", "==", True).stream()
    return jsonify([e.to_dict() for e in espacios])


if __name__ == "__main__":
    app.run(debug=True, port=5000)