<!-- NG-HEADER: Nombre de archivo: PURCHASES.md -->
<!-- NG-HEADER: Ubicación: docs/PURCHASES.md -->
<!-- NG-HEADER: Descripción: Documentación de endpoints y flujo de Compras -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Compras (Purchases)

Esta documentación cubre el flujo de importación, validación, confirmación y reenvío de stock, así como utilidades de diagnóstico.

## Estados
`BORRADOR -> VALIDADA -> CONFIRMADA -> ANULADA`

## Endpoints principales

- `POST /purchases` Crea compra (BORRADOR)
- `PUT /purchases/{id}` Actualiza encabezado y líneas
- `POST /purchases/{id}/validate` Valida líneas (marca OK / SIN_VINCULAR)
- `POST /purchases/{id}/confirm` Confirma (impacta stock y precios)
- `POST /purchases/{id}/cancel` Anula (revierte stock si estaba confirmada)
- `POST /purchases/import/santaplanta` Importa PDF y genera líneas
- `POST /purchases/{id}/resend-stock` Reenvía stock (nueva funcionalidad)

## Reenvío de Stock (`/purchases/{id}/resend-stock`)
Permite volver a aplicar (o previsualizar) los deltas de stock de una compra **ya CONFIRMADA**.

### Casos de uso
- Reprocesar stock tras un rollback parcial o corrupción manual.
- Auditar diferencias detectadas en inventario.
- Asegurar consistencia si falló un paso externo (ej. sincronización a otro sistema) y se decide volver a sumar.

### Reglas
- Solo permitido si `status == CONFIRMADA`.
- No reescribe precios de compra ni genera nuevos `PriceHistory`.
- Soporta preview (`apply=0`) y ejecución real (`apply=1`).
- Incluye modo debug para devolver `applied_deltas`.
- Registra `AuditLog` con acciones:
  - `purchase_resend_stock_preview`
  - `purchase_resend_stock`
- Persiste timestamp del último apply en `purchase.meta.last_resend_stock_at`.

### Cooldown
Se evita el doble reenvío accidental con un cooldown configurable:
- Variable: `PURCHASE_RESEND_COOLDOWN_SECONDS` (default: 300 segundos).
- Si se intenta `apply=1` antes de que expire el período → HTTP 429.

### Parámetros
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| apply | int (0/1) | 0 | 0=preview (no modifica), 1=aplica deltas |
| debug | int (0/1) | 0 | 1 incluye `applied_deltas` en respuesta y audit log |

### Respuesta (preview)
```json
{
  "status": "ok",
  "mode": "preview",
  "applied_deltas": [
    { "product_id": 12, "product_title": "X", "old": 40, "delta": 5, "new": 45, "line_id": 881 }
  ],
  "unresolved_lines": []
}
```

### Respuesta (apply)
Igual estructura pero `mode: "apply"` y stock actualizado.

### Errores frecuentes
| Código | Motivo |
|--------|--------|
| 400 | Compra no está CONFIRMADA |
| 404 | Compra inexistente |
| 429 | Cooldown activo |

## Logging y Auditoría
Se introdujo helper `_purchase_event_log` que estandariza logs estructurados con prefijo `purchase_event` para facilitar parsing posterior.

Eventos relevantes:
- `purchase_confirm`
- `purchase_resend_stock_preview`
- `purchase_resend_stock`

Cada apply exitoso añade entrada con `cooldown_seconds` y timestamp persistido.

## UI
En la vista `PurchaseDetail` se muestra (si existe) el último reenvío: `Último reenvío stock: <fecha local>`.

## Buenas prácticas
- Usar siempre preview antes de aplicar en entornos sensibles.
- Verificar que no existan líneas `SIN_VINCULAR` antes de confirmar inicialmente.
- Monitorear audit logs para detectar patrones de reenvíos frecuentes (posible síntoma de otros problemas).

## Próximos pasos sugeridos
- Endpoint para historial resumido de reenvíos (si se requiere auditoría regulatoria).
- Métrica Prometheus: contador de reenvíos aplicados y rechazados por cooldown.

---
Actualizado: 2025-09-14.
