<!-- NG-HEADER: Nombre de archivo: DEPLOYMENT_MARKET_ALERTS.md -->
<!-- NG-HEADER: Ubicación: docs/DEPLOYMENT_MARKET_ALERTS.md -->
<!-- NG-HEADER: Descripción: Checklist y guía para deployment del sistema de alertas -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Deployment: Sistema de Alertas de Mercado

Guía completa para poner en producción el sistema de alertas de variación de precios.

---

## 📋 Pre-Requisitos

Antes de comenzar el deployment, verificar:

- [ ] PostgreSQL corriendo y accesible
- [ ] Variables de entorno configuradas (`.env`)
- [ ] Backup de base de datos creado
- [ ] Worker de scraping funcionando
- [ ] Tests pasando en entorno de staging

---

## 🔍 Checklist de Verificación Pre-Deployment

### 1. Entorno Virtual Correcto

```bash
# ✅ Verificar que estás usando .venv
.\.venv\Scripts\Activate.ps1

# Verificar Python del .venv
python -c "import sys; print(sys.executable)"
# Debe incluir: .venv\Scripts\python.exe

# Verificar dependencias instaladas
pip list | Select-String "sqlalchemy|alembic|fastapi"
```

### 2. Conectividad a Base de Datos

```bash
# Test de conexión
python scripts\test_db_connection.py

# Debe mostrar:
# ✅ Conexión exitosa!
# 🗄️ Estado de la tabla market_alerts: ...
```

### 3. Variables de Entorno

Verificar en `.env`:

```bash
# Umbrales de alertas
ALERT_THRESHOLD_SALE_VS_MARKET=0.15
ALERT_THRESHOLD_MARKET_VS_PREVIOUS=0.20
ALERT_THRESHOLD_SPIKE=0.30
ALERT_THRESHOLD_DROP=0.25
ALERT_COOLDOWN_HOURS=24
ALERT_EMAIL_ENABLED=false

# Base de datos
DB_URL=postgresql+psycopg://user:password@host:port/dbname
```

**⚠️ IMPORTANTE**: Si la contraseña tiene caracteres especiales:
- `=` → `%3D`
- `:` → `%3A`
- `@` → `%40`

### 4. Archivos Modificados

Verificar que estos archivos fueron actualizados:

```bash
# Modelo de datos
git status db/models.py

# Servicio de alertas
git status services/market/alerts.py

# Router API
git status services/routers/alerts.py

# Integración worker
git status workers/market_scraping.py

# Router de market
git status services/routers/market.py

# Registro de routers
git status services/api.py
```

---

## 🚀 Proceso de Deployment

### Paso 1: Backup de Base de Datos

```bash
# Backup completo
docker exec growen-postgres pg_dump -U growen -d growen > backup_pre_alerts_$(date +%Y%m%d_%H%M%S).sql

# O usar script interno
python scripts/backup_db.py --output backups/pre_alerts_deploy.sql
```

### Paso 2: Verificar Migraciones Alembic

```bash
# Activar .venv
.\.venv\Scripts\Activate.ps1

# Ver estado actual
alembic current

# Ver historial de migraciones
alembic history | Select-String "market_alert" -Context 2,2

# Si la migración NO existe, generarla:
alembic revision --autogenerate -m "Add MarketAlert table for price variation alerts"

# Ver SQL que se ejecutará (dry-run)
alembic upgrade head --sql > migration_preview.sql
code migration_preview.sql
```

### Paso 3: Aplicar Migración

```bash
# PRODUCCIÓN: Aplicar migración
alembic upgrade head

# Verificar tabla creada
python -c "
from sqlalchemy import create_engine, text
import os; from dotenv import load_dotenv; load_dotenv()
engine = create_engine(os.getenv('DB_URL'))
with engine.connect() as conn:
    result = conn.execute(text(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_name='market_alerts'\"))
    print(f'Tabla market_alerts existe: {result.scalar() == 1}')
"
```

### Paso 4: Verificar Estructura de Tabla

```bash
# Ver estructura de market_alerts
docker exec -i growen-postgres psql -U growen -d growen -c "\d market_alerts"

# Debe mostrar:
# - Columna: id (integer, PK)
# - Columna: product_id (integer, FK)
# - Columna: alert_type (character varying)
# - Columna: severity (character varying)
# - Columna: old_value (numeric)
# - Columna: new_value (numeric)
# - Columna: delta_percentage (numeric)
# - Columna: message (text)
# - Columna: resolved (boolean)
# - Columna: resolved_at (timestamp)
# - Columna: resolved_by (integer)
# - Columna: resolution_note (text)
# - Columna: email_sent (boolean)
# - Columna: email_sent_at (timestamp)
# - Columna: created_at (timestamp)
# - Columna: updated_at (timestamp)
# - 4 índices
```

### Paso 5: Reiniciar Backend

```bash
# Docker Compose
docker-compose restart api

# O servicio systemd
sudo systemctl restart growen-api

# Verificar logs
docker-compose logs -f api --tail=50

# Buscar errores
docker-compose logs api | Select-String "error|exception|traceback" -Context 3,3
```

### Paso 6: Verificar API Endpoints

```bash
# Health check
curl -X GET "http://localhost:8000/health"

# Stats de alertas (debe retornar aunque esté en 0)
curl -X GET "http://localhost:8000/alerts/stats" \
  -H "Authorization: Bearer $TOKEN"

# Debe retornar:
# {
#   "active_alerts": 0,
#   "resolved_alerts": 0,
#   "critical_alerts": 0,
#   "alerts_last_24h": 0,
#   "total_alerts": 0
# }
```

### Paso 7: Reiniciar Worker de Scraping

```bash
# Windows
scripts\start_worker_market.cmd

# Linux
dramatiq workers.market_scraping --queues market --processes 1

# Verificar logs
tail -f logs/worker_market.log | Select-String "alerta"
```

### Paso 8: Test End-to-End

```bash
# 1. Crear producto de prueba con precio
curl -X POST "http://localhost:8000/products" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Producto Test Alertas",
    "sale_price": 1000,
    "ng_sku": "TEST-001"
  }'

# 2. Simular precio de mercado diferente
curl -X PATCH "http://localhost:8000/products/TEST-001" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "market_price_reference": 1200
  }'

# 3. Ejecutar scraping manual (o esperar al programado)
python -m workers.market_scraping --product-id <ID>

# 4. Verificar alerta creada
curl -X GET "http://localhost:8000/alerts?product_id=<ID>" \
  -H "Authorization: Bearer $TOKEN"

# 5. Verificar indicador en lista de productos
curl -X GET "http://localhost:8000/market/products" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.items[] | select(.ng_sku=="TEST-001") | {name, has_active_alerts, active_alerts_count}'
```

---

## ✅ Verificación Post-Deployment

### 1. Smoke Tests

```bash
# Ejecutar suite de tests
.\.venv\Scripts\Activate.ps1
pytest tests/test_ai_policy.py -v

# Verificar imports
python -c "
from services.routers import alerts
from services.market.alerts import detect_price_alerts
from db.models import MarketAlert
print('✅ Todos los imports funcionan')
"
```

### 2. Monitoreo de Logs

```bash
# Backend logs
tail -f logs/backend.log | Select-String "alert|🚨"

# Worker logs
tail -f logs/worker_market.log | Select-String "alert|🚨"

# Errores críticos
tail -f logs/backend.log | Select-String "ERROR|CRITICAL"
```

### 3. Verificar Métricas

```bash
# Alertas activas
curl -s http://localhost:8000/alerts/stats | jq

# Productos con alertas
docker exec -i growen-postgres psql -U growen -d growen -c "
  SELECT 
    COUNT(DISTINCT ma.product_id) as productos_con_alertas,
    COUNT(*) as total_alertas
  FROM market_alerts ma
  WHERE ma.resolved = false;
"
```

---

## 🔧 Troubleshooting Post-Deployment

### Problema: API no levanta

```bash
# Ver logs completos
docker-compose logs api --tail=100

# Buscar errores de import
docker-compose logs api | Select-String "ImportError|ModuleNotFoundError"

# Solución común: recrear contenedor
docker-compose down
docker-compose up -d
```

### Problema: Worker no genera alertas

```bash
# Verificar worker corriendo
ps aux | grep dramatiq

# Verificar configuración ENV
python -c "
import os; from dotenv import load_dotenv; load_dotenv()
print('ALERT_THRESHOLD_SALE_VS_MARKET:', os.getenv('ALERT_THRESHOLD_SALE_VS_MARKET'))
print('ALERT_COOLDOWN_HOURS:', os.getenv('ALERT_COOLDOWN_HOURS'))
"

# Ejecutar scraping manual con logs
python -m workers.market_scraping --product-id <ID> --verbose
```

### Problema: Tabla market_alerts no existe

```bash
# Verificar migración aplicada
alembic current

# Si no está aplicada:
alembic upgrade head

# Si falla, ver detalle del error
alembic upgrade head 2>&1 | tee migration_error.log
```

### Problema: Tests fallan

```bash
# Verificar .venv activado
python -c "import sys; print(sys.executable)"

# Reinstalar dependencias
pip install -r requirements.txt --force-reinstall

# Ejecutar test específico con verbose
pytest tests/test_ai_policy.py -vv --tb=long
```

---

## 📊 Monitoreo Continuo

### Queries SQL Útiles

```sql
-- Alertas activas por severidad
SELECT severity, COUNT(*) as count
FROM market_alerts
WHERE resolved = false
GROUP BY severity
ORDER BY CASE severity
  WHEN 'critical' THEN 1
  WHEN 'high' THEN 2
  WHEN 'medium' THEN 3
  WHEN 'low' THEN 4
END;

-- Productos con más alertas
SELECT 
  cp.ng_sku,
  cp.name,
  COUNT(ma.id) as alert_count
FROM canonical_products cp
JOIN market_alerts ma ON cp.id = ma.product_id
WHERE ma.resolved = false
GROUP BY cp.id
ORDER BY alert_count DESC
LIMIT 10;

-- Tendencia de alertas (últimos 7 días)
SELECT 
  DATE(created_at) as date,
  COUNT(*) as count
FROM market_alerts
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date;

-- Alertas sin resolver >48h
SELECT 
  ma.id,
  cp.ng_sku,
  cp.name,
  ma.severity,
  ma.created_at,
  (NOW() - ma.created_at) as age
FROM market_alerts ma
JOIN canonical_products cp ON ma.product_id = cp.id
WHERE ma.resolved = false
  AND ma.created_at < NOW() - INTERVAL '48 hours'
ORDER BY ma.created_at;
```

### Comandos de Mantenimiento

```bash
# Limpiar alertas resueltas antiguas (>30 días)
docker exec -i growen-postgres psql -U growen -d growen -c "
  DELETE FROM market_alerts
  WHERE resolved = true
    AND resolved_at < NOW() - INTERVAL '30 days';
"

# Estadísticas diarias
docker exec -i growen-postgres psql -U growen -d growen -c "
  SELECT 
    DATE(created_at) as date,
    alert_type,
    severity,
    COUNT(*) as count
  FROM market_alerts
  WHERE created_at > NOW() - INTERVAL '7 days'
  GROUP BY DATE(created_at), alert_type, severity
  ORDER BY date DESC, alert_type;
"
```

---

## 🔄 Rollback Plan

Si algo sale mal y necesitas revertir:

### Paso 1: Restaurar Backup

```bash
# Detener servicios
docker-compose stop api worker

# Restaurar BD
docker exec -i growen-postgres psql -U growen -d growen < backup_pre_alerts_YYYYMMDD_HHMMSS.sql
```

### Paso 2: Revertir Código

```bash
# Git revert (si ya commiteaste)
git revert HEAD~1..HEAD

# O checkout a commit anterior
git checkout <commit_hash_pre_alertas>
```

### Paso 3: Eliminar Tabla (Opcional)

```bash
# Solo si quieres limpiar completamente
docker exec -i growen-postgres psql -U growen -d growen -c "
  DROP TABLE IF EXISTS market_alerts CASCADE;
"

# Revertir migración Alembic
alembic downgrade -1
```

### Paso 4: Reiniciar Servicios

```bash
docker-compose up -d
```

---

## 📝 Checklist Final

### Pre-Producción
- [ ] Backup de BD creado
- [ ] .env configurado con variables de alertas
- [ ] Tests pasando localmente
- [ ] Migración de BD probada en staging
- [ ] Documentación revisada

### Durante Deployment
- [ ] Migración aplicada exitosamente
- [ ] Tabla market_alerts creada con índices
- [ ] Backend reiniciado sin errores
- [ ] Worker reiniciado y detectando alertas
- [ ] API endpoints respondiendo correctamente

### Post-Deployment
- [ ] Test end-to-end completado
- [ ] Logs sin errores críticos
- [ ] Primera alerta generada y visible
- [ ] Indicador en frontend funcionando
- [ ] Monitoreo configurado
- [ ] Equipo notificado del deployment

---

## 🎯 Métricas de Éxito

Después de 24 horas en producción, verificar:

- [ ] Al menos 1 alerta generada (si hay variaciones)
- [ ] 0 errores de import en logs
- [ ] API response time <500ms para /alerts/stats
- [ ] Worker sin crashes
- [ ] Alertas duplicadas: 0 (verificar cooldown)
- [ ] Frontend mostrando indicadores correctamente

---

## 📞 Soporte

Si encuentras problemas:

1. Revisar logs: `logs/backend.log`, `logs/worker_market.log`
2. Ejecutar diagnóstico: `python scripts\test_db_connection.py`
3. Verificar documentación: `docs/MARKET_ALERTS.md`
4. Consultar troubleshooting en este documento

---

## 📚 Referencias

- [Guía Completa del Sistema](./MARKET_ALERTS.md)
- [Guía de Inicio Rápido](./MARKET_ALERTS_QUICK_START.md)
- [Entorno Python Correcto](./PYTHON_ENVIRONMENT_SETUP.md)
- [API Documentation](./API_PRODUCTS.md)

---

**Fecha**: 2025-11-12  
**Versión del Sistema**: 1.0.0  
**Deployment realizado por**: _____________  
**Hora de deployment**: _____________  
**Duración**: _____________  
**Incidentes**: _____________
