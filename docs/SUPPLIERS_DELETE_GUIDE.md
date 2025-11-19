<!-- NG-HEADER: Nombre de archivo: SUPPLIERS_DELETE_GUIDE.md -->
<!-- NG-HEADER: Ubicación: docs/SUPPLIERS_DELETE_GUIDE.md -->
<!-- NG-HEADER: Descripción: Guía de uso del endpoint DELETE /suppliers con ejemplos -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Guía de eliminación de proveedores

## Resumen

El endpoint `DELETE /suppliers` permite eliminar múltiples proveedores con validación de integridad referencial y opciones de limpieza automática.

## Modos de eliminación

### 1. Eliminación básica (predeterminado)

Intenta eliminar proveedores, bloqueando aquellos con referencias:

```javascript
const response = await fetch('http://localhost:8000/suppliers', {
  method: 'DELETE',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken
  },
  body: JSON.stringify({
    ids: [71, 72, 73, 74, 75]
  })
});

const result = await response.json();
/*
{
  "requested": [71, 72, 73, 74, 75],
  "deleted": [],
  "blocked": [
    {
      "id": 71,
      "name": "Proveedor Test 1",
      "reasons": ["tiene_import_jobs"],
      "counts": {"import_jobs": 1},
      "details": {
        "import_jobs": {
          "count": 1,
          "jobs": [{"id": 84, "status": "DRY_RUN"}],
          "action": "Usar force_cascade=true para eliminar automáticamente, o ejecutar: DELETE FROM import_jobs WHERE supplier_id = 71"
        }
      }
    },
    // ... más proveedores bloqueados
  ],
  "not_found": [],
  "cascade_deleted": null,
  "help": {
    "force_cascade": "Agregar 'force_cascade': true al body para eliminar automáticamente import_jobs y product_equivalences",
    "manual_cleanup": "Para bloqueos críticos (compras, líneas), revisar detalles en 'blocked[].details'"
  }
}
*/
```

### 2. Eliminación con force_cascade

Elimina automáticamente `import_jobs` y `product_equivalences`:

```javascript
const response = await fetch('http://localhost:8000/suppliers', {
  method: 'DELETE',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken
  },
  body: JSON.stringify({
    ids: [71, 72, 73, 74, 75],
    force_cascade: true
  })
});

const result = await response.json();
/*
{
  "requested": [71, 72, 73, 74, 75],
  "deleted": [71, 72, 73, 74, 75],
  "blocked": [],
  "not_found": [],
  "cascade_deleted": {
    "import_jobs": [84, 85, 86, 87, 88],
    "product_equivalences": [92]
  },
  "help": { ... }
}
*/
```

## Tipos de bloqueos

### Bloqueos críticos (no auto-eliminables)

**1. tiene_compras**
- **Razón**: Existen compras registradas del proveedor
- **Acción**: Revisar módulo de compras, decidir si anular/transferir
- **Ejemplo details**:
```json
{
  "purchases": {
    "count": 5,
    "sample_ids": [12, 15, 18, 22, 25],
    "action": "No se pueden eliminar automáticamente. Revisar módulo de compras."
  }
}
```

**2. tiene_lineas_compra**
- **Razón**: Existen líneas de compra que referencian SKUs del proveedor
- **Acción**: Revisar líneas de compra, decidir migración/anulación
- **Ejemplo details**:
```json
{
  "purchase_lines": {
    "count": 18,
    "sample_ids": [45, 46, 47, 48, 49, 50, 51, 52, 53, 54],
    "action": "No se pueden eliminar automáticamente. Revisar líneas de compra asociadas."
  }
}
```

### Bloqueos no críticos (auto-eliminables con force_cascade)

**3. tiene_import_jobs**
- **Razón**: Existen jobs de importación (frecuentemente DRY_RUN de prueba)
- **Acción**: Usar `force_cascade=true` o limpiar manualmente
- **Ejemplo details**:
```json
{
  "import_jobs": {
    "count": 1,
    "jobs": [{"id": 84, "status": "DRY_RUN"}],
    "action": "Usar force_cascade=true para eliminar automáticamente, o ejecutar: DELETE FROM import_jobs WHERE supplier_id = 71"
  }
}
```

**4. tiene_equivalencias**
- **Razón**: Existen equivalencias de productos mapeadas al proveedor
- **Acción**: Usar `force_cascade=true` o limpiar manualmente
- **Ejemplo details**:
```json
{
  "equivalences": {
    "count": 3,
    "sample_ids": [92, 93, 94],
    "action": "Usar force_cascade=true para eliminar automáticamente, o ejecutar: DELETE FROM product_equivalences WHERE supplier_id = 89"
  }
}
```

**5. tiene_archivos**
- **Razón**: Existen archivos cargados (catálogos PDF, Excel, etc.)
- **Acción**: Se eliminan automáticamente (CASCADE), bloqueo solo informativo
- **Ejemplo details**:
```json
{
  "files": {
    "count": 2,
    "sample_ids": [45, 46],
    "action": "Se eliminarán automáticamente (CASCADE). Este bloqueo es informativo."
  }
}
```

## Flujo recomendado en UI

### 1. Intentar eliminación básica primero

```typescript
async function deleteSuppliers(ids: number[]) {
  const response = await api.delete('/suppliers', { ids });
  const result = await response.json();
  
  if (result.blocked.length === 0) {
    // Éxito total
    showSuccess(`Eliminados ${result.deleted.length} proveedores`);
    return;
  }
  
  // Analizar bloqueos
  const criticalBlocks = result.blocked.filter(b => 
    b.reasons.some(r => r === 'tiene_compras' || r === 'tiene_lineas_compra')
  );
  
  const nonCriticalBlocks = result.blocked.filter(b =>
    !criticalBlocks.includes(b)
  );
  
  if (criticalBlocks.length > 0) {
    showCriticalBlocksModal(criticalBlocks);
  }
  
  if (nonCriticalBlocks.length > 0 && criticalBlocks.length === 0) {
    showForceCascadeOption(nonCriticalBlocks, ids);
  }
}
```

### 2. Modal de detalles de bloqueos

```typescript
function showBlockDetailsModal(blocked: BlockedSupplier[]) {
  const modal = `
    <div class="modal">
      <h2>Proveedores no eliminados</h2>
      <p>Los siguientes proveedores tienen referencias que impiden su eliminación:</p>
      
      ${blocked.map(supplier => `
        <div class="blocked-supplier">
          <h3>${supplier.name} (ID: ${supplier.id})</h3>
          
          ${Object.entries(supplier.details).map(([type, detail]) => `
            <div class="block-detail ${detail.action.includes('No se pueden') ? 'critical' : 'non-critical'}">
              <strong>${type}</strong>: ${detail.count} registro(s)
              <p>${detail.action}</p>
              
              ${detail.jobs ? `
                <ul>
                  ${detail.jobs.map(job => `<li>Job #${job.id} - ${job.status}</li>`).join('')}
                </ul>
              ` : ''}
              
              ${detail.sample_ids ? `
                <details>
                  <summary>Ver IDs (muestra)</summary>
                  <code>${detail.sample_ids.join(', ')}</code>
                </details>
              ` : ''}
            </div>
          `).join('')}
        </div>
      `).join('')}
      
      <div class="modal-actions">
        <button onclick="closeModal()">Cerrar</button>
        ${hasOnlyNonCriticalBlocks(blocked) ? `
          <button onclick="retryWithForceCascade()" class="btn-warning">
            Eliminar con limpieza automática (force_cascade)
          </button>
        ` : ''}
      </div>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', modal);
}
```

### 3. Opción de force_cascade

```typescript
async function retryWithForceCascade(ids: number[]) {
  const confirmMsg = `
    Se eliminarán automáticamente:
    - Import jobs (pruebas DRY_RUN y jobs completados)
    - Equivalencias de productos
    
    ¿Continuar?
  `;
  
  if (!confirm(confirmMsg)) return;
  
  const response = await api.delete('/suppliers', { 
    ids, 
    force_cascade: true 
  });
  
  const result = await response.json();
  
  if (result.cascade_deleted) {
    showSuccess(`
      Eliminados ${result.deleted.length} proveedores.
      Limpieza en cascada:
      - ${result.cascade_deleted.import_jobs.length} import jobs
      - ${result.cascade_deleted.product_equivalences.length} equivalencias
    `);
  }
  
  if (result.blocked.length > 0) {
    showCriticalBlocksModal(result.blocked);
  }
}
```

## Limpieza manual (SQL)

Si prefieres limpiar manualmente antes de intentar eliminación:

```sql
-- Ver qué está bloqueando a proveedores específicos
SELECT 
  s.id,
  s.name,
  COUNT(DISTINCT p.id) as purchases,
  COUNT(DISTINCT sf.id) as files,
  COUNT(DISTINCT ij.id) as import_jobs,
  COUNT(DISTINCT pe.id) as equivalences,
  COUNT(DISTINCT pl.id) as purchase_lines
FROM suppliers s
LEFT JOIN purchases p ON p.supplier_id = s.id
LEFT JOIN supplier_files sf ON sf.supplier_id = s.id
LEFT JOIN import_jobs ij ON ij.supplier_id = s.id
LEFT JOIN product_equivalences pe ON pe.supplier_id = s.id
LEFT JOIN supplier_products sp ON sp.supplier_id = s.id
LEFT JOIN purchase_lines pl ON pl.supplier_item_id = sp.id
WHERE s.id IN (71, 72, 73, 74, 75)
GROUP BY s.id, s.name;

-- Limpiar import_jobs de prueba
DELETE FROM import_jobs 
WHERE supplier_id IN (71, 72, 73, 74, 75) 
AND status = 'DRY_RUN';

-- Limpiar equivalencias
DELETE FROM product_equivalences 
WHERE supplier_id IN (71, 72, 73, 74, 75);

-- Intentar eliminación nuevamente desde API
```

## Ejemplo completo PowerShell

```powershell
# 1. Obtener token CSRF
$loginResponse = Invoke-WebRequest -Uri "http://localhost:8000/login" `
  -Method POST -Body (@{username='admin'; password='***'} | ConvertTo-Json) `
  -ContentType "application/json" -SessionVariable 'session'

$csrfToken = $session.Cookies.GetCookies("http://localhost:8000")["csrf_token"].Value

# 2. Intentar eliminación básica
$headers = @{
  'X-CSRF-Token' = $csrfToken
  'Content-Type' = 'application/json'
}

$body = @{ ids = @(71..90) } | ConvertTo-Json

$result = Invoke-RestMethod -Uri "http://localhost:8000/suppliers" `
  -Method DELETE -Headers $headers -Body $body `
  -WebSession $session

# 3. Analizar resultado
Write-Host "Solicitados: $($result.requested.Count)"
Write-Host "Eliminados: $($result.deleted.Count)"
Write-Host "Bloqueados: $($result.blocked.Count)"

if ($result.blocked.Count -gt 0) {
  Write-Host "`nProveedores bloqueados:"
  foreach ($b in $result.blocked) {
    Write-Host "  $($b.name) (ID $($b.id)):"
    foreach ($reason in $b.reasons) {
      $detail = $b.details.$reason
      Write-Host "    - $reason: $($detail.count) registros"
      Write-Host "      Acción: $($detail.action)"
    }
  }
  
  # 4. Preguntar si usar force_cascade
  $hasOnlyNonCritical = $result.blocked | Where-Object { 
    $_.reasons -notcontains "tiene_compras" -and 
    $_.reasons -notcontains "tiene_lineas_compra" 
  }
  
  if ($hasOnlyNonCritical) {
    $retry = Read-Host "`n¿Reintentar con force_cascade? (S/N)"
    if ($retry -eq 'S') {
      $bodyForce = @{ 
        ids = $result.blocked.id
        force_cascade = $true 
      } | ConvertTo-Json
      
      $resultForce = Invoke-RestMethod -Uri "http://localhost:8000/suppliers" `
        -Method DELETE -Headers $headers -Body $bodyForce `
        -WebSession $session
      
      Write-Host "`nResultado con force_cascade:"
      Write-Host "Eliminados: $($resultForce.deleted.Count)"
      Write-Host "Import jobs eliminados: $($resultForce.cascade_deleted.import_jobs.Count)"
      Write-Host "Equivalencias eliminadas: $($resultForce.cascade_deleted.product_equivalences.Count)"
    }
  }
}
```

## Resumen de flujo de decisión

```
┌─────────────────────────────┐
│ Usuario selecciona IDs      │
│ para eliminar               │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ DELETE /suppliers           │
│ (sin force_cascade)         │
└──────────┬──────────────────┘
           │
           ▼
      ¿Bloqueados?
           │
    ┌──────┴──────┐
    │             │
   NO            SÍ
    │             │
    ▼             ▼
 Éxito    ¿Bloqueos críticos?
          (compras/líneas)
           │
    ┌──────┴──────┐
    │             │
   NO            SÍ
    │             │
    ▼             ▼
 Mostrar      Mostrar modal
 opción       "No se puede
 force_       eliminar,
 cascade      revisar datos"
    │             
    ▼
 Usuario
 confirma
    │
    ▼
 DELETE con
 force_cascade
    │
    ▼
 Mostrar
 resumen
 cascade_
 deleted
```

## Notas finales

- **Siempre revisar `blocked[].details`** antes de tomar acciones manuales
- **force_cascade es seguro** para import_jobs y equivalencias (no afecta datos críticos)
- **Nunca usar force_cascade** si hay "tiene_compras" o "tiene_lineas_compra"
- **Auditoría**: Todas las eliminaciones quedan registradas en `audit_logs`
- **Límite**: Máximo 500 IDs por solicitud

