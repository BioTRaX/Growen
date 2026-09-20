<!-- NG-HEADER: Nombre de archivo: visual-validation-checklist.md -->
<!-- NG-HEADER: Ubicación: .agents/skills/vue-module-migration/references/visual-validation-checklist.md -->
<!-- NG-HEADER: Descripción: Checklist de superficie y smoke visual para cortes Vue. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Checklist de validación visual Vue

## Elegir la superficie

- Usar diálogo para una acción focal, breve y sin navegación interna.
- Usar drawer para contexto secundario que debe convivir con la vista de origen.
- Usar página dedicada cuando haya tres o más pestañas, listas extensas, CRUD,
  historial, archivos, deep links o necesidad de volver al recurso padre.
- Si un overlay requiere varios ajustes de alto, ancho y scroll, reevaluar la
  superficie antes de agregar más CSS.

## Validar con condiciones reales

1. Probar el rol mínimo y el rol operativo requerido; no sustituirlos por guest.
2. Usar un registro con datos representativos, textos largos y volumen realista.
3. Iniciar el smoke desde la acción de origen y confirmar URL, título y destino.
4. Revisar DOM visible y consola; usar captura cuando el criterio sea espacial.
5. Comprobar scroll, pestañas, textos largos, acciones y estados vacíos/error.
6. Si cambia `config/modules.json`, regenerar rutas Nginx antes de typecheck/build.

## Gate mínimo

```powershell
cd frontend-vue
npm.cmd run generate:nginx
npm.cmd test -- <selección focal>
npm.cmd run typecheck
npm.cmd run build
```

Una suite verde no reemplaza el smoke visual autenticado. Registrar por separado
cualquier bloqueo de sesión, datos o servicio.

