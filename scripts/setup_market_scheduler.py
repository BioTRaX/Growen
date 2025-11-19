#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: setup_market_scheduler.py
# NG-HEADER: Ubicación: scripts/setup_market_scheduler.py
# NG-HEADER: Descripción: Script de configuración inicial del scheduler de mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Script interactivo para configurar el scheduler de precios de mercado.

Ejecutar: python scripts/setup_market_scheduler.py
"""

import os
import sys
from pathlib import Path

# Colores para terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.END}\n")

def print_step(number, text):
    print(f"{Colors.CYAN}{Colors.BOLD}[Paso {number}]{Colors.END} {text}")

def print_success(text):
    print(f"{Colors.GREEN}✓{Colors.END} {text}")

def print_error(text):
    print(f"{Colors.RED}✗{Colors.END} {text}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠{Colors.END} {text}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ{Colors.END} {text}")

def get_input(prompt, default=None):
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    
    value = input(prompt).strip()
    return value if value else default

def get_yes_no(prompt, default="y"):
    response = get_input(f"{prompt} (y/n)", default).lower()
    return response in ["y", "yes", "s", "si", "sí"]

def main():
    print_header("CONFIGURACIÓN DEL SCHEDULER DE PRECIOS DE MERCADO")
    
    # Detectar directorio raíz
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent
    env_file = root_dir / ".env"
    env_example = root_dir / ".env.market_scheduler.example"
    
    print_info(f"Directorio del proyecto: {root_dir}")
    
    # Paso 1: Verificar dependencias
    print_step(1, "Verificando dependencias")
    
    try:
        import apscheduler
        print_success("APScheduler instalado")
    except ImportError:
        print_error("APScheduler no encontrado")
        if get_yes_no("¿Instalar APScheduler ahora?"):
            os.system("pip install apscheduler>=3.10.4")
            print_success("APScheduler instalado")
        else:
            print_error("APScheduler es requerido. Abortando.")
            return 1
    
    # Paso 2: Configuración
    print_step(2, "Configuración de parámetros")
    
    print("\n" + Colors.BOLD + "Configuración del scheduler:" + Colors.END)
    
    # Habilitar scheduler
    print("\n" + Colors.BOLD + "1. ¿Habilitar scheduler automático?" + Colors.END)
    print("   • true: Se ejecutará según el cron configurado")
    print("   • false: Solo ejecución manual")
    enabled = get_yes_no("Habilitar", "n")
    
    # Frecuencia
    print("\n" + Colors.BOLD + "2. Frecuencia de actualización (días)" + Colors.END)
    print("   • 1 día: Actualización diaria (alta frecuencia)")
    print("   • 2 días: Cada 2 días (balanceado)")
    print("   • 7 días: Semanal (baja frecuencia)")
    freq_days = get_input("Días", "2")
    
    # Productos por ejecución
    print("\n" + Colors.BOLD + "3. Máximo de productos por ejecución" + Colors.END)
    print("   • 10-20: Desarrollo/testing")
    print("   • 50: Producción balanceada")
    print("   • 100+: Alta demanda")
    max_products = get_input("Máximo productos", "50")
    
    # Priorizar obligatorios
    print("\n" + Colors.BOLD + "4. ¿Priorizar productos con fuentes obligatorias?" + Colors.END)
    prioritize = get_yes_no("Priorizar", "y")
    
    # Cron schedule
    print("\n" + Colors.BOLD + "5. Horario de ejecución (cron expression)" + Colors.END)
    print("   Ejemplos comunes:")
    print("   • '0 2 * * *'     -> Diario a las 2:00 AM")
    print("   • '0 */12 * * *'  -> Cada 12 horas")
    print("   • '0 2 * * 0'     -> Solo domingos a las 2:00 AM")
    print("   • '0 3 */2 * *'   -> Cada 2 días a las 3:00 AM")
    cron = get_input("Cron", "0 2 * * *")
    
    # Paso 3: Escribir configuración
    print_step(3, "Guardando configuración")
    
    config_lines = [
        "\n# ============================================",
        "# SCHEDULER DE PRECIOS DE MERCADO",
        "# ============================================",
        "",
        f"MARKET_SCHEDULER_ENABLED={'true' if enabled else 'false'}",
        f"MARKET_UPDATE_FREQUENCY_DAYS={freq_days}",
        f"MARKET_MAX_PRODUCTS_PER_RUN={max_products}",
        f"MARKET_PRIORITIZE_MANDATORY={'true' if prioritize else 'false'}",
        f'MARKET_CRON_SCHEDULE="{cron}"',
        ""
    ]
    
    # Verificar si .env existe
    if env_file.exists():
        print_warning(f"El archivo .env ya existe")
        
        # Leer contenido actual
        with open(env_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Verificar si ya tiene configuración de scheduler
        if "MARKET_SCHEDULER_ENABLED" in content:
            print_warning("Ya existe configuración de scheduler en .env")
            if not get_yes_no("¿Sobrescribir configuración?", "n"):
                print_info("Conservando configuración actual")
                return 0
            
            # Eliminar sección anterior
            lines = content.split("\n")
            new_lines = []
            skip = False
            for line in lines:
                if "SCHEDULER DE PRECIOS DE MERCADO" in line:
                    skip = True
                elif skip and line.startswith("#") and "=" * 10 in line:
                    skip = False
                    continue
                elif not skip or not (line.startswith("MARKET_") or line.strip() == ""):
                    new_lines.append(line)
            
            content = "\n".join(new_lines)
        
        # Agregar nueva configuración
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(content.rstrip() + "\n")
            f.write("\n".join(config_lines))
        
        print_success(f"Configuración actualizada en {env_file}")
    else:
        # Crear nuevo .env
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("\n".join(config_lines))
        
        print_success(f"Archivo .env creado: {env_file}")
    
    # Paso 4: Instrucciones de integración
    print_step(4, "Integración con la aplicación")
    
    print("\n" + Colors.BOLD + "Para completar la integración:" + Colors.END)
    print("\n1. Editar services/api.py y agregar:")
    print(f"{Colors.YELLOW}")
    print("   from services.jobs.market_scheduler import start_scheduler, stop_scheduler")
    print("")
    print("   @app.on_event('startup')")
    print("   async def startup():")
    print("       # ... otros inits")
    print("       start_scheduler()  # ← AGREGAR")
    print("")
    print("   @app.on_event('shutdown')")
    print("   async def shutdown():")
    print("       # ... otros cleanups")
    print("       stop_scheduler()  # ← AGREGAR")
    print(f"{Colors.END}")
    
    print("\n2. (Opcional) Registrar router de control en services/api.py:")
    print(f"{Colors.YELLOW}")
    print("   from services.routers import market_scheduler")
    print("   app.include_router(market_scheduler.router)")
    print(f"{Colors.END}")
    
    print("\n3. Iniciar worker de mercado:")
    print(f"{Colors.YELLOW}")
    print("   python -m dramatiq workers.market_scraping --queues market")
    print(f"{Colors.END}")
    
    # Paso 5: Próximos pasos
    print_step(5, "Próximos pasos")
    
    print("\n" + Colors.BOLD + "Para probar la configuración:" + Colors.END)
    print(f"\n{Colors.CYAN}# Verificar estado{Colors.END}")
    print(f"  python scripts/run_market_update.py --status-only")
    
    print(f"\n{Colors.CYAN}# Ejecutar manualmente (testing){Colors.END}")
    print(f"  python scripts/run_market_update.py --max-products 5")
    
    print(f"\n{Colors.CYAN}# Ver documentación completa{Colors.END}")
    print(f"  cat docs/MARKET_SCHEDULER.md")
    print(f"  cat MARKET_SCHEDULER_QUICKSTART.md")
    
    print("\n" + Colors.GREEN + Colors.BOLD + "✓ Configuración completada exitosamente" + Colors.END)
    print()
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Configuración cancelada por el usuario{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}ERROR: {e}{Colors.END}")
        sys.exit(1)
