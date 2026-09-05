// NG-HEADER: Nombre de archivo: script.js
// NG-HEADER: Ubicación: siyuan-widgets/crono/script.js
// NG-HEADER: Descripción: Controlador del widget Crono y sincronización con Attribute Views de SiYuan.
// NG-HEADER: Lineamientos: Ver AGENTS.md

// Elements
const avIdInput = document.getElementById('av-id');
const btnLoad = document.getElementById('btn-load');
const taskList = document.getElementById('task-list');
const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');

let currentTasks = [];
let columnMinutosId = null;
let columnSegundosId = null;
let columnEstadoId = null;
let columnCategoriaId = null;
let columnCheckId = null;
let intervals = {};

async function siyuanAPI(endpoint, data) {
    const url = `/api/${endpoint}`;
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        const res = await response.json();
        if (res.code !== 0) throw new Error(res.msg || 'Error en la API de SiYuan');
        return res.data;
    } catch (err) {
        console.error('API Error:', err);
        throw err;
    }
}

async function loadTasks() {
    const avId = avIdInput.value.trim();
    if (!avId) return showError('Por favor, ingresa el ID del AV.');

    showLoading();
    try {
        const data = await siyuanAPI('av/renderAttributeView', { id: avId });

        let columns = data.columns || (data.av && data.av.columns) || (data.view && data.view.columns) || (data[0] && data[0].columns);
        let rows = data.rows || (data.av && data.av.rows) || (data.view && data.view.rows) || (data[0] && data[0].rows);

        if (!columns || !rows) {
            const viewKeys = Object.values(data).find(v => v && typeof v === 'object' && v.columns && v.rows);
            if (viewKeys) {
                columns = viewKeys.columns;
                rows = viewKeys.rows;
            } else {
                throw new Error('Estructura inválida. Asegúrate de que el ID es correcto.');
            }
        }

        const minutosCol = columns.find(c => c.name.toLowerCase() === 'minutos' && c.type === 'number');
        if (!minutosCol) throw new Error('No se encontró una columna de tipo "Number" llamada "Minutos".');
        columnMinutosId = minutosCol.id;

        const segundosCol = columns.find(c => c.name.toLowerCase() === 'segundos' && c.type === 'number');
        if (!segundosCol) throw new Error('No se encontró una columna de tipo "Number" llamada "Segundos".');
        columnSegundosId = segundosCol.id;

        const estadoCol = columns.find(c => c.name.toLowerCase() === 'estado' && c.type === 'select');
        if (!estadoCol) throw new Error('No se encontró una columna de tipo "Select" llamada "Estado".');
        columnEstadoId = estadoCol.id;

        const categoriaCol = columns.find(c => c.name.toLowerCase() === 'categoria' && c.type === 'select');
        columnCategoriaId = categoriaCol ? categoriaCol.id : null;

        // Buscar columna checkbox (para autocompletar)
        const checkCol = columns.find(c => c.type === 'checkbox');
        columnCheckId = checkCol ? checkCol.id : null;

        const nameCol = columns.find(c => c.type === 'block');
        const nameColId = nameCol ? nameCol.id : columns[0].id;

        let parsedTasks = rows.map(row => {
            const nameCell = row.cells.find(c => c.value && c.value.keyID === nameColId);
            const name = nameCell && nameCell.value.block ? nameCell.value.block.content : '';

            const minCell = row.cells.find(c => c.value && c.value.keyID === columnMinutosId);
            let currentMinutes = 0;
            if (minCell && minCell.value.number && minCell.value.number.isNotEmpty) {
                currentMinutes = Number(minCell.value.number.content) || 0;
            }

            const secCell = row.cells.find(c => c.value && c.value.keyID === columnSegundosId);
            let currentSeconds = 0;
            if (secCell && secCell.value.number && secCell.value.number.isNotEmpty) {
                currentSeconds = Number(secCell.value.number.content) || 0;
            }

            const statusCell = row.cells.find(c => c.value && c.value.keyID === columnEstadoId);
            const currentStatus = statusCell && statusCell.value.mSelect && statusCell.value.mSelect[0]
                ? statusCell.value.mSelect[0].content
                : '';

            const categoryCell = columnCategoriaId
                ? row.cells.find(c => c.value && c.value.keyID === columnCategoriaId)
                : null;
            const categories = CronoCore.extractCategoryTags(categoryCell && categoryCell.value);

            let isChecked = false;
            if (columnCheckId) {
                const cCell = row.cells.find(c => c.value && c.value.keyID === columnCheckId);
                if (cCell) {
                    if (cCell.value.checkbox && cCell.value.checkbox.checked) isChecked = true;
                    // Alternativa por si SiYuan lo guarda como mCheckbox
                    if (cCell.value.mCheckbox && cCell.value.mCheckbox.length > 0 && cCell.value.mCheckbox[0].checked) isChecked = true;
                }
            }

            return {
                rowId: row.id,
                name,
                currentMinutes,
                currentSeconds,
                currentStatus,
                categories,
                isChecked
            };
        });

        for (const task of parsedTasks) {
            const isTimerActive = localStorage.getItem(`crono_start_${task.rowId}`) !== null;
            const desiredStatus = CronoCore.deriveTaskStatus({
                isTimerActive,
                isChecked: task.isChecked
            });
            if (task.currentStatus !== desiredStatus) {
                await CronoCore.persistTaskStatus({
                    rowId: task.rowId,
                    statusColumnId: columnEstadoId,
                    status: desiredStatus,
                    updateCell: updateCellInSiYuan
                });
                task.currentStatus = desiredStatus;
            }
        }

        // Filtrar tareas vacías y las que ya están marcadas
        currentTasks = parsedTasks.filter(t => t.name.trim() !== '' && !t.isChecked);

        renderTasks();
    } catch (err) {
        showError(err.message);
    } finally {
        hideLoading();
    }
}

function renderTasks() {
    taskList.innerHTML = '';
    currentTasks.forEach(task => {
        const li = document.createElement('li');

        const info = document.createElement('div');
        info.className = 'task-info';

        const nameEl = document.createElement('div');
        nameEl.className = 'task-name';
        nameEl.textContent = task.name;

        const timeEl = document.createElement('div');
        timeEl.className = 'task-time';
        timeEl.textContent = `Registrado: ${task.currentMinutes} min ${task.currentSeconds} s`;
        timeEl.id = `registered-${task.rowId}`;

        info.appendChild(nameEl);
        info.appendChild(timeEl);

        const categoryEl = document.createElement('div');
        categoryEl.className = 'task-category';
        categoryEl.setAttribute('aria-label', 'Categoría');
        task.categories.forEach(category => {
            const tag = document.createElement('span');
            tag.className = 'category-tag';
            tag.dataset.color = category.color;
            tag.textContent = category.content;
            categoryEl.appendChild(tag);
        });

        const actions = document.createElement('div');
        actions.className = 'task-actions';

        const timerDisplay = document.createElement('div');
        timerDisplay.className = 'timer-display';
        timerDisplay.id = `timer-${task.rowId}`;
        timerDisplay.textContent = '00:00';

        const btnAction = document.createElement('button');

        const startTime = localStorage.getItem(`crono_start_${task.rowId}`);
        if (startTime) {
            btnAction.textContent = 'Stop';
            btnAction.className = 'btn-stop';
            startTimerDisplay(task.rowId, parseInt(startTime, 10));
        } else {
            btnAction.textContent = 'Play';
            btnAction.className = 'btn-play';
        }

        btnAction.onclick = () => toggleTimer(task, btnAction);

        actions.appendChild(timerDisplay);
        actions.appendChild(btnAction);
        li.appendChild(info);
        li.appendChild(categoryEl);
        li.appendChild(actions);
        taskList.appendChild(li);
    });
}

async function toggleTimer(task, btn) {
    const isPlaying = localStorage.getItem(`crono_start_${task.rowId}`) !== null;
    if (isPlaying) {
        await stopTimer(task, btn);
    } else {
        btn.disabled = true;
        try {
            await CronoCore.persistTaskStatus({
                rowId: task.rowId,
                statusColumnId: columnEstadoId,
                status: 'Iniciada',
                updateCell: updateCellInSiYuan
            });
            task.currentStatus = 'Iniciada';
            const now = Date.now();
            localStorage.setItem(`crono_start_${task.rowId}`, now);
            btn.textContent = 'Stop';
            btn.className = 'btn-stop';
            startTimerDisplay(task.rowId, now);
        } catch (err) {
            console.error('[Crono] Error al iniciar:', err);
            showError(`Error al iniciar: ${err.message}`);
        } finally {
            btn.disabled = false;
        }
    }
}

async function stopTimer(task, btn) {
    const startTime = parseInt(localStorage.getItem(`crono_start_${task.rowId}`), 10);
    localStorage.removeItem(`crono_start_${task.rowId}`);

    clearInterval(intervals[task.rowId]);
    document.getElementById(`timer-${task.rowId}`).textContent = '00:00';

    btn.disabled = true;
    btn.textContent = 'Guardando...';

    const elapsedMs = Date.now() - startTime;
    console.log(`[Crono] Stop: elapsed=${elapsedMs}ms, task=${task.name}`);

    try {
        const totals = await CronoCore.persistElapsedTime({
            elapsedMs,
            currentMinutes: task.currentMinutes,
            currentSeconds: task.currentSeconds,
            rowId: task.rowId,
            minutesColumnId: columnMinutosId,
            secondsColumnId: columnSegundosId,
            updateCell: updateCellInSiYuan
        });
        task.currentMinutes = totals.minutes;
        task.currentSeconds = totals.seconds;
        console.log(`[Crono] Tiempo guardado: ${totals.minutes}min ${totals.seconds}s`);

        await CronoCore.persistTaskStatus({
            rowId: task.rowId,
            statusColumnId: columnEstadoId,
            status: 'Completada',
            updateCell: updateCellInSiYuan
        });
        task.currentStatus = 'Completada';
        console.log('[Crono] Estado guardado: Completada');

        // Autocompletar Checkbox SIEMPRE (independiente de los minutos)
        if (columnCheckId) {
            console.log(`[Crono] Marcando checkbox...`);
            await updateCellInSiYuan(task.rowId, columnCheckId, "checkbox", {
                checked: true
            });
        }

        console.log(`[Crono] Guardado exitoso. Recargando...`);

        // Recargar la lista del widget para que desaparezca la tarea completada
        await loadTasks();
    } catch (err) {
        console.error(`[Crono] Error:`, err);
        showError(`Error al guardar: ${err.message}`);
        btn.textContent = 'Play';
        btn.className = 'btn-play';
        btn.disabled = false;
    }
}

function startTimerDisplay(rowId, startTime) {
    if (intervals[rowId]) clearInterval(intervals[rowId]);
    const updateDisplay = () => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const m = Math.floor(elapsed / 60).toString().padStart(2, '0');
        const s = (elapsed % 60).toString().padStart(2, '0');
        const display = document.getElementById(`timer-${rowId}`);
        if (display) display.textContent = `${m}:${s}`;
    };
    updateDisplay();
    intervals[rowId] = setInterval(updateDisplay, 1000);
}

async function updateCellInSiYuan(rowId, keyId, type, typeValueObj) {
    // El endpoint correcto es /api/av/setAttributeViewBlockAttr
    // con "itemID" (no rowID ni blockID) y el valor envuelto en el tipo
    const payload = {
        avID: avIdInput.value.trim(),
        keyID: keyId,
        itemID: rowId,
        value: CronoCore.buildAttributeValue(type, typeValueObj)
    };

    console.log(`[Crono] Payload:`, JSON.stringify(payload));

    const res = await fetch('/api/av/setAttributeViewBlockAttr', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const json = await res.json();
    console.log(`[Crono] Response:`, JSON.stringify(json));
    if (json.code !== 0) throw new Error(json.msg || "Error al actualizar celda");
    return json.data;
}

function showLoading() { loadingEl.classList.remove('hidden'); errorEl.classList.add('hidden'); }
function hideLoading() { loadingEl.classList.add('hidden'); }
function showError(msg) { errorEl.textContent = msg; errorEl.classList.remove('hidden'); }

btnLoad.addEventListener('click', loadTasks);
if (avIdInput.value) loadTasks();
