import os
from dotenv import load_dotenv

def verify_setup():
    print("--- Verificando Configuración ---")
    
    # 1. Check .env
    if os.path.exists(".env"):
        load_dotenv()
        code = os.getenv("ACCESS_CODE")
        if code:
            print(f"✅ Archivo .env encontrado. Código: {code}")
        else:
            print("❌ Archivo .env encontrado pero ACCESS_CODE está vacío.")
    else:
        print("❌ Archivo .env no encontrado.")

    # 2. Check main.py for auth logic
    with open("app/main.py", "r", encoding="utf-8") as f:
        content = f.read()
        if "st.session_state.authenticated" in content and "check_password" in content:
            print("✅ Lógica de autenticación encontrada en main.py.")
        else:
            print("❌ Lógica de autenticación NO encontrada en main.py.")

    # 3. Check run_mobile.ps1
    if os.path.exists("run_mobile.ps1"):
        print("✅ Archivo run_mobile.ps1 creado.")
    else:
        print("❌ Archivo run_mobile.ps1 no encontrado.")

if __name__ == "__main__":
    verify_setup()
