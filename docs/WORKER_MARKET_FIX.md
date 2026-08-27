<!-- NG-HEADER: Nombre de archivo: WORKER_MARKET_FIX.md -->
<!-- NG-HEADER: Ubicación: docs/WORKER_MARKET_FIX.md -->
<!-- NG-HEADER: Descripción: Correcciones históricas del worker de mercado. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Corrección del Worker de Market - Guía Rápida

**Fecha**: 2025-11-16  
**Problema**: Worker no conecta a Redis → Scraping no funciona  
**Solución**: Cambiar `localhost` → `127.0.0.1` en configuración Redis

---

## 🔴 Problema Actual

El worker de market (PID 15616) está en loop infinito intentando conectar a Redis:

```
[CRITICAL] Consumer encountered a connection error: Error 10061 connecting to localhost:6379
[INFO] Restarting consumer in 3.00 seconds.
```

**Causa**: 
- Worker inició antes de que Redis estuviera disponible
- Windows resuelve `localhost` a `::1` (IPv6) primero
- Redis escucha en `127.0.0.1` (IPv4)
- Conexión falla constantemente

**Impacto**:
- ❌ Botón "🔄 Actualizar Precios" no funciona
- ❌ Tareas quedan encoladas en Redis indefinidamente
- ❌ Precios nunca se actualizan vía scraping

---

## ✅ Solución Rápida (5 minutos)

### **Paso 1: Detener Worker Zombie**

Desde el panel de admin (`http://127.0.0.1:5175/admin/servicios/workers`):
1. Buscar "Worker Market"
2. Click en "Detener"

**O manualmente**:
```powershell
taskkill /PID 15616 /F
```

---

### **Paso 2: Corregir Configuración Redis**

**Archivo**: `.env`

```bash
# CAMBIAR:
REDIS_URL=redis://localhost:6379/0

# A:
REDIS_URL=redis://127.0.0.1:6379/0
```

**Guardar y cerrar el archivo.**

---

### **Paso 3: Verificar Redis Está Corriendo**

```powershell
docker ps | Select-String "growen-redis"
```

**Debe mostrar**:
```
5e2c3a01e82e   bb186d083732   ...   Up X minutes   0.0.0.0:6379->6379/tcp   growen-redis
```

Si no aparece:
```powershell
docker compose up -d redis
```

---

### **Paso 4: Limpiar Log Antiguo** (Opcional)

```powershell
Remove-Item "logs\worker_market.log" -Force
```

---

### **Paso 5: Reiniciar Worker**

**Opción A - Desde Admin Panel** (Recomendado):
1. Ir a `http://127.0.0.1:5175/admin/servicios/workers`
2. Buscar "Worker Market"
3. Click en "Iniciar"

**Opción B - Manualmente**:
```powershell
.\scripts\start_worker_market.cmd
```

---

### **Paso 6: Verificar Conexión Exitosa**

```powershell
Get-Content "logs\worker_market.log" -Tail 20
```

**Debe mostrar** (sin errores):
```
[INFO] Consumer is ready.
[INFO] Broker: redis://127.0.0.1:6379/0
[INFO] Listening on queue: market
```

**NO debe decir**:
```
[CRITICAL] Consumer encountered a connection error
```

---

## 🧪 Probar que Funciona

### **Test 1: Actualizar Precios Manualmente**

1. Ir a `http://127.0.0.1:5175/market`
2. Click en producto "Bandeja Bulldog Lisa" (ID 45)
3. En el modal, click en "🔄 Actualizar Precios"
4. **Esperar 5-10 segundos**
5. Recargar modal (cerrar y abrir de nuevo)

**Resultado esperado**:
- Las fuentes muestran precios actualizados
- "Última actualización" muestra "Hace X segundos/minutos"
- "Rango de Mercado" se recalcula automáticamente

---

### **Test 2: Ver Worker Procesando Tareas**

**Terminal con logs en tiempo real**:
```powershell
Get-Content "logs\worker_market.log" -Wait -Tail 20
```

Luego click en "Actualizar Precios" desde la UI.

**Debe mostrar**:
```
[INFO] Received message: refresh_market_prices_task(45)
[INFO] Iniciando scraping para producto 'Bandeja Bulldog Lisa'
[INFO] ✓ Precio extraído exitosamente de fuente 'ML Bandeja Bulldog 27*18': 1180.00 ARS
[INFO] Guardando precio en DB para fuente ID 1
[INFO] Scraping completado para producto 45: 2/2 fuentes exitosas
```

---

## 🔍 Troubleshooting

### **Problema: Worker no inicia**

**Error**: `ModuleNotFoundError: No module named 'dramatiq'`

**Solución**:
```powershell
pip install dramatiq redis
```

---

### **Problema: Worker inicia pero sigue sin conectar a Redis**

**Verificar**:
```powershell
# 1. Redis escucha en 127.0.0.1:6379
netstat -ano | Select-String "6379"

# Debe mostrar:
# TCP    127.0.0.1:6379    0.0.0.0:0    LISTENING    22992

# 2. .env tiene 127.0.0.1 (NO localhost)
Get-Content ".env" | Select-String "REDIS_URL"

# Debe mostrar:
# REDIS_URL=redis://127.0.0.1:6379/0
```

**Si usa `localhost`**: Cambiar a `127.0.0.1` y reiniciar worker.

---

### **Problema: Scraping falla con timeout**

**Síntoma en logs**:
```
[ERROR] Error de red: Timeout after 15 seconds
```

**Causas posibles**:
1. URL de la fuente es inválida o está caída
2. Sitio bloqueó el scraping (requiere User-Agent)
3. Página requiere JavaScript (cambiar `source_type` a `dynamic`)

**Solución temporal**:
Actualizar precio manualmente en la UI:
1. Abrir modal de producto
2. Buscar la fuente que falló
3. Click en "✏️" en "Último precio"
4. Ingresar precio manualmente

---

### **Problema: Precios no se actualizan en la UI después de scraping**

**Verificar en DB**:
```powershell
docker exec -it growen-postgres psql -U growen -d growen -c "SELECT source_name, last_price, last_checked_at FROM market_sources WHERE product_id = 45;"
```

**Si `last_price` es NULL**:
- Scraping falló para esa fuente
- Revisar logs del worker para ver el error

**Si `last_price` tiene valor pero UI no muestra**:
- Recargar página (Ctrl+F5)
- Verificar que endpoint `/market/products/45/sources` retorna los valores

---

## 📋 Checklist Post-Corrección

- [ ] Worker se inició sin errores
- [ ] Log no muestra "connection error"
- [ ] Log muestra "Consumer is ready"
- [ ] Actualización de precios desde UI funciona
- [ ] Rango de mercado se calcula automáticamente
- [ ] Logs muestran scraping exitoso

---

## 🎯 Resultado Final Esperado

**ANTES** (Roto):
```
Usuario → Click "Actualizar" → API encola tarea → Redis guarda mensaje → ❌ Worker no consume → Nada pasa
```

**DESPUÉS** (Funcionando):
```
Usuario → Click "Actualizar" → API encola tarea → Redis guarda mensaje → ✅ Worker consume → Scraping ejecuta → DB actualiza → UI muestra rango
```

---

## 📞 Soporte

Si después de seguir estos pasos el worker sigue sin funcionar:

1. **Revisar logs completos**:
   ```powershell
   Get-Content "logs\worker_market.log" | Out-File "worker_debug.txt"
   ```

2. **Verificar estado de servicios**:
   ```powershell
   docker ps
   # Debe mostrar: growen-postgres, growen-redis (ambos Up)
   ```

3. **Consultar documentación completa**:
   - `docs/MARKET_ANALYSIS_FIX.md` - Análisis completo del sistema
   - `docs/API_MARKET.md` - Documentación de endpoints
   - `README.md` - Setup general

---

**Última actualización**: 2025-11-16 14:20  
**Próxima acción**: Ejecutar Paso 1-6 de la solución
