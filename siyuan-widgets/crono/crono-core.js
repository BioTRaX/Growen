// NG-HEADER: Nombre de archivo: crono-core.js
// NG-HEADER: Ubicación: siyuan-widgets/crono/crono-core.js
// NG-HEADER: Descripción: Cálculo y persistencia del tiempo registrado por el widget Crono.
// NG-HEADER: Lineamientos: Ver AGENTS.md

(function exposeCronoCore(root) {
    function normalizeNonNegativeInteger(value) {
        const number = Number(value);
        return Number.isFinite(number) ? Math.max(0, Math.floor(number)) : 0;
    }

    function calculateElapsedTotals(elapsedMs, currentMinutes, currentSeconds) {
        const previousSeconds = (
            normalizeNonNegativeInteger(currentMinutes) * 60
            + normalizeNonNegativeInteger(currentSeconds)
        );
        const elapsedSeconds = Math.max(0, Math.floor(Number(elapsedMs) / 1000) || 0);
        const totalSeconds = previousSeconds + elapsedSeconds;

        return {
            minutes: Math.floor(totalSeconds / 60),
            seconds: totalSeconds % 60
        };
    }

    async function persistElapsedTime({
        elapsedMs,
        currentMinutes,
        currentSeconds,
        rowId,
        minutesColumnId,
        secondsColumnId,
        updateCell
    }) {
        const totals = calculateElapsedTotals(elapsedMs, currentMinutes, currentSeconds);

        await updateCell(rowId, minutesColumnId, 'number', {
            content: totals.minutes,
            isNotEmpty: true
        });
        await updateCell(rowId, secondsColumnId, 'number', {
            content: totals.seconds,
            isNotEmpty: true
        });

        return totals;
    }

    function deriveTaskStatus({ isTimerActive, isChecked }) {
        if (isChecked) return 'Completada';
        return isTimerActive ? 'Iniciada' : 'Sin iniciar';
    }

    async function persistTaskStatus({
        rowId,
        statusColumnId,
        status,
        updateCell
    }) {
        await updateCell(rowId, statusColumnId, 'select', {
            content: status,
            color: '1'
        });
    }

    function buildAttributeValue(type, typeValueObj) {
        if (type === 'select') {
            return {
                type: 'select',
                mSelect: [typeValueObj]
            };
        }
        return { [type]: typeValueObj };
    }

    function extractCategoryTags(cellValue) {
        if (!cellValue || !Array.isArray(cellValue.mSelect)) return [];
        return cellValue.mSelect
            .filter(item => item && String(item.content || '').trim() !== '')
            .map(item => ({
                content: String(item.content).trim(),
                color: String(item.color || '1')
            }));
    }

    const api = {
        buildAttributeValue,
        calculateElapsedTotals,
        deriveTaskStatus,
        extractCategoryTags,
        persistElapsedTime,
        persistTaskStatus
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    root.CronoCore = api;
}(typeof globalThis !== 'undefined' ? globalThis : window));
