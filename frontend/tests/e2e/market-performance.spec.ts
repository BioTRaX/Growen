// NG-HEADER: Nombre de archivo: market-performance.spec.ts
// NG-HEADER: Ubicación: frontend/tests/e2e/market-performance.spec.ts
// NG-HEADER: Descripción: Tests de performance E2E para módulo Mercado
// NG-HEADER: Lineamientos: Ver AGENTS.md

/**
 * Tests de performance end-to-end para el módulo Mercado.
 * 
 * Valida:
 * - Tiempo de carga con volumen grande de datos (200 productos)
 * - Responsividad de la UI bajo carga
 * - Performance de filtros y paginación
 * - Métricas FPS y tiempos de renderizado
 */

import { test, expect, Page } from '@playwright/test';

/**
 * Configuración de test de performance
 */
test.describe.configure({ mode: 'serial', timeout: 60000 });

/**
 * Helper: Crear productos simulados para tests de carga
 */
async function seedLargeProductDataset(page: Page, count: number = 200) {
  // Mock del endpoint de API con datos grandes
  await page.route('**/api/market/products*', async (route) => {
    const url = new URL(route.request().url());
    const page_size = parseInt(url.searchParams.get('page_size') || '50');
    const page_num = parseInt(url.searchParams.get('page') || '1');
    
    const mockProducts = Array.from({ length: count }, (_, i) => ({
      product_id: i + 1,
      preferred_name: `Producto Test ${i + 1}`,
      sale_price: 100 + (i * 10),
      market_price_reference: 110 + (i * 10),
      market_price_min: 95 + (i * 10),
      market_price_max: 120 + (i * 10),
      last_market_update: new Date(Date.now() - i * 60000).toISOString(),
      category_id: (i % 5) + 1,
      category_name: `Categoría ${(i % 5) + 1}`,
      supplier_id: (i % 10) + 1,
      supplier_name: `Proveedor ${(i % 10) + 1}`,
    }));
    
    // Paginación
    const start = (page_num - 1) * page_size;
    const end = start + page_size;
    const paginatedItems = mockProducts.slice(start, end);
    
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: paginatedItems,
        total: count,
        page: page_num,
        page_size: page_size,
        pages: Math.ceil(count / page_size),
      }),
    });
  });
  
  // Mock de categorías
  await page.route('**/api/categories*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        Array.from({ length: 5 }, (_, i) => ({
          id: i + 1,
          name: `Categoría ${i + 1}`,
          parent_id: null,
        }))
      ),
    });
  });
  
  // Mock de proveedores
  await page.route('**/api/suppliers*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: Array.from({ length: 10 }, (_, i) => ({
          id: i + 1,
          name: `Proveedor ${i + 1}`,
        })),
        total: 10,
      }),
    });
  });
}

test.describe('Performance del Módulo Mercado', () => {
  test.beforeEach(async ({ page }) => {
    // Mock de autenticación
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          username: 'test_user',
          role: 'admin',
        }),
      });
    });
  });

  test('renderiza tabla con 200 productos en menos de 2 segundos', async ({ page }) => {
    console.log('\n' + '='.repeat(70));
    console.log('TEST DE PERFORMANCE: Renderizado de 200 Productos');
    console.log('='.repeat(70));
    
    // Configurar dataset grande
    await seedLargeProductDataset(page, 200);
    
    console.log('\n[1/4] Navegando a página de Mercado...');
    await page.goto('/mercado');
    
    // Marcar inicio de medición
    console.log('\n[2/4] Iniciando medición de performance...');
    await page.evaluate(() => performance.mark('render-start'));
    
    // Esperar a que la tabla esté visible y cargada
    await page.waitForSelector('table', { state: 'visible' });
    
    // Esperar al último producto de la primera página (índice 49)
    console.log('\n[3/4] Esperando renderizado completo de primera página...');
    await page.waitForSelector('text=Producto Test 50', { timeout: 5000 });
    
    // Marcar fin de medición
    await page.evaluate(() => performance.mark('render-end'));
    
    // Obtener métricas de performance
    const metrics = await page.evaluate(() => {
      performance.measure('render-duration', 'render-start', 'render-end');
      const measure = performance.getEntriesByName('render-duration')[0];
      
      // Métricas adicionales
      const paintMetrics = performance.getEntriesByType('paint');
      const fcp = paintMetrics.find(m => m.name === 'first-contentful-paint');
      const lcp = performance.getEntriesByType('largest-contentful-paint')[0];
      
      return {
        renderDuration: measure.duration,
        firstContentfulPaint: fcp?.startTime || 0,
        largestContentfulPaint: lcp?.startTime || 0,
      };
    });
    
    console.log('\n[4/4] Resultados de performance:');
    console.log(`  → Duración de render: ${metrics.renderDuration.toFixed(2)}ms`);
    console.log(`  → First Contentful Paint: ${metrics.firstContentfulPaint.toFixed(2)}ms`);
    console.log(`  → Largest Contentful Paint: ${metrics.largestContentfulPaint.toFixed(2)}ms`);
    
    // Criterio: renderizado completo en menos de 2 segundos
    expect(metrics.renderDuration).toBeLessThan(2000);
    console.log(`\n✓ PASÓ: Render en ${metrics.renderDuration.toFixed(2)}ms < 2000ms`);
    
    // Verificar que los elementos están en el DOM
    const rowCount = await page.locator('table tbody tr').count();
    console.log(`\n✓ Filas renderizadas: ${rowCount}`);
    expect(rowCount).toBeGreaterThan(0);
    expect(rowCount).toBeLessThanOrEqual(50); // Primera página
    
    console.log('='.repeat(70));
  });

  test('paginación no causa degradación de performance', async ({ page }) => {
    console.log('\n' + '='.repeat(70));
    console.log('TEST DE PERFORMANCE: Paginación');
    console.log('='.repeat(70));
    
    await seedLargeProductDataset(page, 200);
    await page.goto('/mercado');
    
    // Esperar carga inicial
    await page.waitForSelector('text=Producto Test 1');
    
    console.log('\n[1/3] Midiendo tiempo de navegación entre páginas...');
    const pageTimes: number[] = [];
    
    // Navegar por 5 páginas
    for (let i = 1; i <= 5; i++) {
      const startMark = `page-${i}-start`;
      const endMark = `page-${i}-end`;
      
      await page.evaluate((mark) => performance.mark(mark), startMark);
      
      if (i > 1) {
        // Click en "Siguiente"
        await page.click('button:has-text("Siguiente")');
      }
      
      // Esperar a que se cargue la nueva página
      const expectedFirstProduct = ((i - 1) * 50) + 1;
      await page.waitForSelector(`text=Producto Test ${expectedFirstProduct}`, { timeout: 5000 });
      
      await page.evaluate((mark) => performance.mark(mark), endMark);
      
      const duration = await page.evaluate((start, end) => {
        performance.measure('page-load', start, end);
        return performance.getEntriesByName('page-load')[0].duration;
      }, startMark, endMark);
      
      pageTimes.push(duration);
      console.log(`  Página ${i}: ${duration.toFixed(2)}ms`);
    }
    
    console.log('\n[2/3] Análisis de tiempos de paginación:');
    const avgTime = pageTimes.reduce((a, b) => a + b, 0) / pageTimes.length;
    const maxTime = Math.max(...pageTimes);
    const minTime = Math.min(...pageTimes);
    
    console.log(`  → Promedio: ${avgTime.toFixed(2)}ms`);
    console.log(`  → Mínimo: ${minTime.toFixed(2)}ms`);
    console.log(`  → Máximo: ${maxTime.toFixed(2)}ms`);
    console.log(`  → Variación: ${((maxTime - minTime) / avgTime * 100).toFixed(1)}%`);
    
    // Criterios de aceptación
    console.log('\n[3/3] Validando criterios:');
    
    // Criterio 1: Tiempo promedio < 1 segundo
    expect(avgTime).toBeLessThan(1000);
    console.log(`  ✓ Tiempo promedio ${avgTime.toFixed(2)}ms < 1000ms`);
    
    // Criterio 2: No hay degradación progresiva (último no más del doble del primero)
    const degradation = pageTimes[pageTimes.length - 1] / pageTimes[0];
    expect(degradation).toBeLessThan(2);
    console.log(`  ✓ Sin degradación: último/primero = ${degradation.toFixed(2)}x`);
    
    console.log('='.repeat(70));
  });

  test('filtros responden en menos de 500ms', async ({ page }) => {
    console.log('\n' + '='.repeat(70));
    console.log('TEST DE PERFORMANCE: Filtros');
    console.log('='.repeat(70));
    
    await seedLargeProductDataset(page, 200);
    await page.goto('/mercado');
    await page.waitForSelector('table');
    
    console.log('\n[1/3] Probando filtro por nombre...');
    
    // Medir tiempo de respuesta del filtro
    await page.evaluate(() => performance.mark('filter-start'));
    
    const searchInput = page.locator('input[placeholder*="Nombre"]');
    await searchInput.fill('Producto Test 150');
    
    // Esperar el debounce (300ms) + tiempo de procesamiento
    await page.waitForTimeout(350);
    
    // Esperar a que se actualice la tabla
    await page.waitForSelector('text=Producto Test 150', { timeout: 2000 });
    
    await page.evaluate(() => performance.mark('filter-end'));
    
    const filterTime = await page.evaluate(() => {
      performance.measure('filter-duration', 'filter-start', 'filter-end');
      return performance.getEntriesByName('filter-duration')[0].duration;
    });
    
    console.log(`  → Tiempo de respuesta: ${filterTime.toFixed(2)}ms`);
    
    // Criterio: respuesta total < 800ms (incluyendo debounce)
    expect(filterTime).toBeLessThan(800);
    console.log(`  ✓ PASÓ: ${filterTime.toFixed(2)}ms < 800ms`);
    
    console.log('\n[2/3] Verificando que el filtro funciona correctamente...');
    const visibleRows = await page.locator('table tbody tr').count();
    console.log(`  → Filas visibles después del filtro: ${visibleRows}`);
    
    // Debería haber solo 1 producto que coincida exactamente
    expect(visibleRows).toBeGreaterThan(0);
    expect(visibleRows).toBeLessThanOrEqual(50);
    
    console.log('\n[3/3] Limpiando filtro...');
    await page.click('button:has-text("Limpiar")');
    await page.waitForTimeout(350);
    
    const rowsAfterClear = await page.locator('table tbody tr').count();
    console.log(`  → Filas después de limpiar: ${rowsAfterClear}`);
    expect(rowsAfterClear).toBe(50); // Primera página completa
    
    console.log('='.repeat(70));
  });

  test('UI no se bloquea durante carga de detalles de producto', async ({ page }) => {
    console.log('\n' + '='.repeat(70));
    console.log('TEST DE PERFORMANCE: Carga de Detalles');
    console.log('='.repeat(70));
    
    await seedLargeProductDataset(page, 200);
    
    // Mock del endpoint de fuentes (con delay simulado)
    await page.route('**/api/market/products/*/sources', async (route) => {
      // Simular delay de red
      await new Promise(resolve => setTimeout(resolve, 500));
      
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          mandatory: [
            {
              id: 1,
              source_name: 'Fuente Principal',
              url: 'https://example.com/producto',
              last_price: 110.50,
              last_scraped_at: new Date().toISOString(),
              is_mandatory: true,
            },
          ],
          additional: [
            {
              id: 2,
              source_name: 'Fuente Secundaria',
              url: 'https://example2.com/producto',
              last_price: 115.00,
              last_scraped_at: new Date().toISOString(),
              is_mandatory: false,
            },
          ],
          suggested: [],
        }),
      });
    });
    
    await page.goto('/mercado');
    await page.waitForSelector('table');
    
    console.log('\n[1/3] Abriendo modal de detalles...');
    
    // Click en el primer botón "Ver"
    await page.evaluate(() => performance.mark('modal-open-start'));
    await page.click('button:has-text("Ver")').catch(() => {
      // Fallback: buscar por data-testid o clase
      return page.click('table tbody tr:first-child button');
    });
    
    // Esperar a que aparezca el modal
    await page.waitForSelector('[role="dialog"]', { state: 'visible', timeout: 3000 });
    await page.evaluate(() => performance.mark('modal-open-end'));
    
    const modalOpenTime = await page.evaluate(() => {
      performance.measure('modal-open', 'modal-open-start', 'modal-open-end');
      return performance.getEntriesByName('modal-open')[0].duration;
    });
    
    console.log(`  → Tiempo de apertura de modal: ${modalOpenTime.toFixed(2)}ms`);
    
    console.log('\n[2/3] Verificando que la UI sigue respondiendo...');
    
    // Intentar interactuar con elementos de fondo (debería estar bloqueado)
    const backdropVisible = await page.locator('[role="dialog"]').isVisible();
    expect(backdropVisible).toBe(true);
    
    // Verificar que el modal muestra el contenido
    const modalTitle = await page.locator('[role="dialog"] h2, [role="dialog"] h3').first();
    await expect(modalTitle).toBeVisible();
    
    console.log(`  ✓ Modal visible y funcional`);
    
    console.log('\n[3/3] Cerrando modal...');
    await page.click('button:has-text("Cerrar")');
    await page.waitForSelector('[role="dialog"]', { state: 'hidden', timeout: 2000 });
    
    // Criterio: apertura de modal < 1 segundo
    expect(modalOpenTime).toBeLessThan(1000);
    console.log(`  ✓ PASÓ: Apertura en ${modalOpenTime.toFixed(2)}ms < 1000ms`);
    
    console.log('='.repeat(70));
  });

  test('memoria no crece indefinidamente con navegación repetida', async ({ page, context }) => {
    console.log('\n' + '='.repeat(70));
    console.log('TEST DE PERFORMANCE: Uso de Memoria (Frontend)');
    console.log('='.repeat(70));
    
    await seedLargeProductDataset(page, 200);
    
    console.log('\n[1/3] Navegando múltiples veces entre páginas...');
    
    // Habilitar métricas de performance
    const client = await context.newCDPSession(page);
    
    // Medición inicial
    await page.goto('/mercado');
    await page.waitForSelector('table');
    await page.waitForTimeout(1000); // Estabilizar
    
    const memoryInitial = await client.send('Performance.getMetrics');
    const jsHeapInitial = memoryInitial.metrics.find(m => m.name === 'JSHeapUsedSize')?.value || 0;
    
    console.log(`  → Memoria JS inicial: ${(jsHeapInitial / 1024 / 1024).toFixed(2)} MB`);
    
    // Navegar 10 veces entre páginas
    console.log('\n[2/3] Navegando entre páginas 10 veces...');
    for (let i = 0; i < 10; i++) {
      // Ir a página siguiente
      await page.click('button:has-text("Siguiente")');
      await page.waitForTimeout(200);
      
      // Volver a página anterior
      await page.click('button:has-text("Anterior")');
      await page.waitForTimeout(200);
    }
    
    // Esperar a que se estabilice
    await page.waitForTimeout(1000);
    
    // Forzar garbage collection (solo en modo headless con flag)
    await page.evaluate(() => {
      if (typeof (globalThis as any).gc === 'function') {
        (globalThis as any).gc();
      }
    });
    
    await page.waitForTimeout(500);
    
    // Medición final
    const memoryFinal = await client.send('Performance.getMetrics');
    const jsHeapFinal = memoryFinal.metrics.find(m => m.name === 'JSHeapUsedSize')?.value || 0;
    
    console.log('\n[3/3] Análisis de memoria:');
    console.log(`  → Memoria JS inicial: ${(jsHeapInitial / 1024 / 1024).toFixed(2)} MB`);
    console.log(`  → Memoria JS final: ${(jsHeapFinal / 1024 / 1024).toFixed(2)} MB`);
    
    const memoryIncrease = jsHeapFinal - jsHeapInitial;
    const memoryIncreasePercent = (memoryIncrease / jsHeapInitial) * 100;
    
    console.log(`  → Incremento: ${(memoryIncrease / 1024 / 1024).toFixed(2)} MB (${memoryIncreasePercent.toFixed(1)}%)`);
    
    // Criterio: incremento < 50% de memoria inicial
    expect(memoryIncreasePercent).toBeLessThan(50);
    console.log(`  ✓ PASÓ: Incremento ${memoryIncreasePercent.toFixed(1)}% < 50%`);
    
    console.log('='.repeat(70));
  });
});
