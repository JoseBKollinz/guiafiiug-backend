from firebase_admin_config import auth, db

usuarios = [
    {"email": "admin@fiindustrial.edu.ec", "role": "admin", "nombre": "Administrador Principal"},
    {"email": "adminjr@fiindustrial.edu.ec", "role": "admin_junior", "nombre": "Admin Junior"},
    {"email": "editor@fiindustrial.edu.ec", "role": "editor", "nombre": "Editor de Espacios"},
    {"email": "auditor@fiindustrial.edu.ec", "role": "auditor", "nombre": "Auditor del Sistema"},
    {"email": "visitante@fiindustrial.edu.ec", "role": "visitante", "nombre": "Visitante"},
    {"email": "admin2@fiindustrial.edu.ec", "role": "admin", "nombre": "Administrador Secundario"},
]

for u in usuarios:
    try:
        user = auth.get_user_by_email(u["email"])

        # Actualiza el nombre visible en Firebase Auth
        auth.update_user(user.uid, display_name=u["nombre"])

        # Asegura que el custom claim de rol siga correcto
        auth.set_custom_user_claims(user.uid, {"role": u["role"]})

        # Guarda/actualiza en la colección usuarios_admin
        db.collection("usuarios_admin").document(user.uid).set({
            "nombre": u["nombre"],
            "email": u["email"],
            "role": u["role"]
        })

        print(f"✅ Actualizado: {u['email']} ({u['role']}) - {u['nombre']}")
    except auth.UserNotFoundError:
        print(f"⚠️ {u['email']}: no existe en Firebase Auth, créalo primero")
    except Exception as e:
        print(f"⚠️ {u['email']}: {e}")