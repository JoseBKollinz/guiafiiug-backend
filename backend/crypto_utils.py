import os
import hashlib
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

_key = os.environ.get("FERNET_KEY")
if not _key:
    raise ValueError("FERNET_KEY no está configurada en el archivo .env")

fernet = Fernet(_key.encode())


def encriptar_cedula(cedula: str) -> str:
    return fernet.encrypt(cedula.encode()).decode()


def desencriptar_cedula(cedula_cifrada: str) -> str:
    return fernet.decrypt(cedula_cifrada.encode()).decode()


def hash_cedula(cedula: str) -> str:
    return hashlib.sha256(cedula.encode()).hexdigest()