// NG-HEADER: Nombre de archivo: crono-core.test.cjs
// NG-HEADER: Ubicación: siyuan-widgets/crono/tests/crono-core.test.cjs
// NG-HEADER: Descripción: Pruebas de regresión para la persistencia del tiempo del widget Crono.
// NG-HEADER: Lineamientos: Ver AGENTS.md

const assert = require('node:assert/strict');
const test = require('node:test');

async function loadCronoCore() {
    try {
        return require('../crono-core.js');
    } catch (error) {
        assert.fail(`El módulo de persistencia de Crono no está disponible: ${error.message}`);
    }
}

test('convierte una ejecución menor a un minuto en segundos persistibles', async () => {
    const { calculateElapsedTotals } = await loadCronoCore();

    assert.deepEqual(calculateElapsedTotals(3_721, 0, 0), {
        minutes: 0,
        seconds: 3
    });
});

test('normaliza segundos acumulados al sumar una ejecución', async () => {
    const { calculateElapsedTotals } = await loadCronoCore();

    assert.deepEqual(calculateElapsedTotals(2_000, 1, 59), {
        minutes: 2,
        seconds: 1
    });
});

test('persiste minutos y segundos antes de completar la tarea', async () => {
    const { persistElapsedTime } = await loadCronoCore();
    const writes = [];

    const totals = await persistElapsedTime({
        elapsedMs: 3_721,
        currentMinutes: 0,
        currentSeconds: 0,
        rowId: 'row-1',
        minutesColumnId: 'minutes-key',
        secondsColumnId: 'seconds-key',
        updateCell: async (...args) => writes.push(args)
    });

    assert.deepEqual(totals, { minutes: 0, seconds: 3 });
    assert.deepEqual(writes, [
        ['row-1', 'minutes-key', 'number', { content: 0, isNotEmpty: true }],
        ['row-1', 'seconds-key', 'number', { content: 3, isNotEmpty: true }]
    ]);
});

test('deriva el estado desde el cronómetro y el checkbox', async () => {
    const { deriveTaskStatus } = await loadCronoCore();

    assert.equal(deriveTaskStatus({ isTimerActive: false, isChecked: false }), 'Sin iniciar');
    assert.equal(deriveTaskStatus({ isTimerActive: true, isChecked: false }), 'Iniciada');
    assert.equal(deriveTaskStatus({ isTimerActive: false, isChecked: true }), 'Completada');
    assert.equal(deriveTaskStatus({ isTimerActive: true, isChecked: true }), 'Completada');
});

test('persiste el estado como un valor select de SiYuan', async () => {
    const { persistTaskStatus } = await loadCronoCore();
    const writes = [];

    await persistTaskStatus({
        rowId: 'row-1',
        statusColumnId: 'status-key',
        status: 'Iniciada',
        updateCell: async (...args) => writes.push(args)
    });

    assert.deepEqual(writes, [
        ['row-1', 'status-key', 'select', { content: 'Iniciada', color: '1' }]
    ]);
});

test('construye el payload especial requerido por una columna select', async () => {
    const { buildAttributeValue } = await loadCronoCore();

    assert.deepEqual(
        buildAttributeValue('select', { content: 'Completada', color: '1' }),
        {
            type: 'select',
            mSelect: [{ content: 'Completada', color: '1' }]
        }
    );
});

test('conserva el payload existente para números y checkbox', async () => {
    const { buildAttributeValue } = await loadCronoCore();

    assert.deepEqual(
        buildAttributeValue('number', { content: 2, isNotEmpty: true }),
        { number: { content: 2, isNotEmpty: true } }
    );
    assert.deepEqual(
        buildAttributeValue('checkbox', { checked: true }),
        { checkbox: { checked: true } }
    );
});

test('extrae categorías con el color configurado en SiYuan', async () => {
    const { extractCategoryTags } = await loadCronoCore();

    assert.deepEqual(
        extractCategoryTags({
            mSelect: [
                { content: 'Bienestar financiero', color: '3' },
                { content: 'Hogar', color: '1' }
            ]
        }),
        [
            { content: 'Bienestar financiero', color: '3' },
            { content: 'Hogar', color: '1' }
        ]
    );
    assert.deepEqual(extractCategoryTags({ mSelect: [] }), []);
    assert.deepEqual(extractCategoryTags(undefined), []);
});
