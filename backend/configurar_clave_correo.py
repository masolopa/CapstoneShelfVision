"""Guarda localmente la contraseña de aplicación sin mostrarla."""
import getpass
from dotenv import set_key
from app.core.config import BACKEND_ROOT

if __name__ == "__main__":
    try:
        value = getpass.getpass("Contraseña de aplicación de Gmail (no la contraseña habitual): ").replace(" ", "")
        if len(value) != 16 or not value.isascii() or not value.isalpha():
            raise ValueError("Se esperaba la contraseña de aplicación de 16 letras generada por Google.")
        set_key(str(BACKEND_ROOT / ".env"), "REGOVA_SMTP_PASSWORD", value)
        print("Credencial guardada. Reinicia EJECUTAR.bat para cargarla.")
    except (EOFError, KeyboardInterrupt):
        print("Cancelado. No se guardó la credencial.")
    except ValueError as error:
        print(error)
        raise SystemExit(1)
