#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: verify_drive_config.py
# NG-HEADER: Ubicación: scripts/verify_drive_config.py
# NG-HEADER: Descripción: Script para verificar configuración de Google Drive.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script para verificar que la configuración de Google Drive esté correcta."""

import os
import sys
from pathlib import Path
import json

# Cargar variables de entorno desde .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def check_credentials_file():
    """Verifica que el archivo de credenciales exista y sea válido."""
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        print("❌ ERROR: GOOGLE_APPLICATION_CREDENTIALS no está definido")
        print("   Agrega al .env: GOOGLE_APPLICATION_CREDENTIALS=./certs/growen-drive.json")
        return False
    
    # Resolver ruta relativa
    if not Path(creds_path).is_absolute():
        creds_path = Path(__file__).parent.parent / creds_path
    
    creds_file = Path(creds_path)
    
    if not creds_file.exists():
        print(f"❌ ERROR: Archivo de credenciales no encontrado: {creds_file}")
        return False
    
    # Verificar que sea JSON válido
    try:
        with open(creds_file, 'r') as f:
            data = json.load(f)
        
        # Verificar campos requeridos
        required_fields = ["type", "project_id", "private_key", "client_email"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            print(f"❌ ERROR: Archivo de credenciales incompleto. Faltan: {missing}")
            return False
        
        if data.get("type") != "service_account":
            print("❌ ERROR: El archivo no es de tipo 'service_account'")
            return False
        
        print(f"✅ Archivo de credenciales válido: {creds_file}")
        print(f"   Service Account: {data.get('client_email')}")
        print(f"   Project ID: {data.get('project_id')}")
        return True
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Archivo de credenciales no es JSON válido: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR al leer credenciales: {e}")
        return False

def check_folder_id():
    """Verifica que DRIVE_SOURCE_FOLDER_ID esté definido."""
    folder_id = os.getenv("DRIVE_SOURCE_FOLDER_ID")
    if not folder_id:
        print("❌ ERROR: DRIVE_SOURCE_FOLDER_ID no está definido")
        print("   Agrega al .env: DRIVE_SOURCE_FOLDER_ID=tu_folder_id_aqui")
        print("   Puedes obtenerlo de la URL de Google Drive:")
        print("   https://drive.google.com/drive/folders/FOLDER_ID")
        return False
    
    print(f"✅ DRIVE_SOURCE_FOLDER_ID configurado: {folder_id}")
    return True

def check_optional_vars():
    """Verifica variables opcionales y muestra valores por defecto."""
    vars_config = {
        "DRIVE_PROCESSED_FOLDER_NAME": "Procesados",
        "DRIVE_SIN_SKU_FOLDER_NAME": "SIN_SKU",
        "DRIVE_ERRORS_FOLDER_NAME": "Errores_SKU",
    }
    
    print("\n📋 Variables opcionales (valores por defecto):")
    for var, default in vars_config.items():
        value = os.getenv(var, default)
        if value == default:
            print(f"   {var}: {value} (default)")
        else:
            print(f"   {var}: {value} (custom)")

def test_connection():
    """Intenta conectar con Google Drive API."""
    try:
        # Agregar el directorio raíz al path para importar módulos
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from services.integrations.drive import GoogleDriveSync
        
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        folder_id = os.getenv("DRIVE_SOURCE_FOLDER_ID")
        
        if not creds_path or not folder_id:
            print("\n⚠️  No se puede probar conexión: faltan variables requeridas")
            return False
        
        # Resolver ruta relativa
        if not Path(creds_path).is_absolute():
            creds_path = project_root / creds_path
        
        print("\n🔌 Probando conexión con Google Drive API...")
        drive_sync = GoogleDriveSync(str(creds_path), folder_id)
        
        import asyncio
        async def test():
            try:
                await drive_sync.authenticate()
                print("✅ Autenticación exitosa")
                
                # Intentar listar archivos (puede estar vacío)
                files = await drive_sync.list_images_in_folder()
                print(f"✅ Conexión exitosa. Archivos encontrados: {len(files)}")
                return True
            except Exception as e:
                print(f"❌ Error de conexión: {e}")
                print(f"   Tipo: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                return False
        
        result = asyncio.run(test())
        return result
    except ImportError as e:
        print(f"⚠️  No se puede probar conexión: {e}")
        print("   Asegúrate de tener instaladas las dependencias:")
        print("   pip install google-api-python-client google-auth")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal."""
    print("=" * 60)
    print("Verificación de Configuración Google Drive")
    print("=" * 60)
    
    all_ok = True
    
    # Verificar credenciales
    print("\n1. Verificando archivo de credenciales...")
    if not check_credentials_file():
        all_ok = False
    
    # Verificar folder ID
    print("\n2. Verificando DRIVE_SOURCE_FOLDER_ID...")
    if not check_folder_id():
        all_ok = False
    
    # Variables opcionales
    check_optional_vars()
    
    # Probar conexión
    if all_ok:
        if not test_connection():
            all_ok = False
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ Configuración completa y válida")
        print("\nPuedes iniciar la sincronización desde:")
        print("  - Panel Admin → Drive Sync")
        print("  - O endpoint: POST /admin/drive-sync/start")
        return 0
    else:
        print("❌ Hay problemas en la configuración")
        print("\nRevisa los errores arriba y corrige las variables en .env")
        return 1

if __name__ == "__main__":
    sys.exit(main())

