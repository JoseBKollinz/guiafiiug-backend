from firebase_admin_config import auth, db

usuarios = [
    {"email": "admin@fiindustrial.edu.ec", "password": "Admin#2026", "role": "admin"},
    {"email": "editor@fiindustrial.edu.ec", "password": "Editor#2026", "role": "editor"},
    {"email": "auditor@fiindustrial.edu.ec", "password": "Auditor#2026", "role": "auditor"},
    {"email": "visitante@fiindustrial.edu.ec", "password": "Visita#2026", "role": "visitante"},
    {"email": "admin2@fiindustrial.edu.ec", "password": "Admin2#2026", "role": "admin"},
]

for u in usuarios:
    try:
        user = auth.create_user(email=u["email"], password=u["password"])
        # Guardamos el rol como custom claim (seguro, verificable en el token)
        auth.set_custom_user_claims(user.uid, {"role": u["role"]})
        # También lo guardamos en Firestore para consultas más ricas
        db.collection("usuarios").document(user.uid).set({
            "email": u["email"],
            "role": u["role"]
        })
        print(f"✅ Creado: {u['email']} ({u['role']})")
    except Exception as e:
        print(f"⚠️ {u['email']}: {e}")