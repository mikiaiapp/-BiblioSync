// JavaScript client application for BiblioSync

// Application state
let socket = null;
let currentSettings = {
    main_library_path: "",
    scan_folders: [],
    destination_folder: "",
    last_comparison_method: "Name & Size"
};
let isProcessing = false;

// Directory explorer state
let currentBrowserTarget = ""; // 'lib-path', 'dest-path', or 'add-scan-folder'
let currentBrowserPath = "";
let selectedFolderInBrowser = "";

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
    loadSettings();
    loadHistory();
    connectWebSocket();
    setupEventListeners();
});

// Setup event listeners for inputs to auto-save settings
function setupEventListeners() {
    const libPathInput = document.getElementById("lib-path");
    const destPathInput = document.getElementById("dest-path");
    const strategySelect = document.getElementById("strategy-select");

    libPathInput.addEventListener("blur", saveSettingsFromUI);
    destPathInput.addEventListener("blur", saveSettingsFromUI);
    strategySelect.addEventListener("change", saveSettingsFromUI);
}

// REST: Load configurations
async function loadSettings() {
    try {
        const response = await fetch("/api/settings");
        if (response.ok) {
            currentSettings = await response.json();
            
            // Populate inputs
            document.getElementById("lib-path").value = currentSettings.main_library_path;
            document.getElementById("dest-path").value = currentSettings.destination_folder;
            document.getElementById("strategy-select").value = currentSettings.last_comparison_method;
            
            renderScanFolders();
        }
    } catch (err) {
        console.error("Error al cargar configuración:", err);
    }
}

// REST: Save configurations to backend
async function saveSettingsFromUI() {
    currentSettings.main_library_path = document.getElementById("lib-path").value.trim();
    currentSettings.destination_folder = document.getElementById("dest-path").value.trim();
    currentSettings.last_comparison_method = document.getElementById("strategy-select").value;

    try {
        const response = await fetch("/api/settings", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(currentSettings)
        });
        if (!response.ok) {
            console.error("Error al guardar configuración");
        }
    } catch (err) {
        console.error("Error al conectar con la API de configuración:", err);
    }
}

// Scan Folders UI Render
function renderScanFolders() {
    const listContainer = document.getElementById("scan-folders-list");
    listContainer.innerHTML = "";

    if (currentSettings.scan_folders.length === 0) {
        listContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; padding: 10px;">No hay carpetas configuradas. Pulsa en "Añadir Carpeta".</div>';
        return;
    }

    currentSettings.scan_folders.forEach((folder, index) => {
        const row = document.createElement("div");
        row.className = "scan-folder-row";
        row.innerHTML = `
            <span class="folder-name">${folder}</span>
            <button class="btn-delete" onclick="removeScanFolder(${index})" title="Eliminar">&times;</button>
        `;
        listContainer.appendChild(row);
    });
}

// Add/Remove scan folders
async function removeScanFolder(index) {
    if (isProcessing) return;
    currentSettings.scan_folders.splice(index, 1);
    renderScanFolders();
    await saveSettingsFromUI();
}

// WebSocket Connection
function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    const statusIndicator = document.getElementById("connection-status");
    const statusText = statusIndicator.querySelector(".status-text");

    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        statusIndicator.className = "status-indicator connected";
        statusText.innerText = "Conectado";
        appendLog("[WEB] Conectado con el servidor web en tiempo real.");
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "log") {
            appendLog(data.line);
        } else if (data.type === "progress") {
            updateProgressUI(data.val, data.text);
        }
    };

    socket.onclose = () => {
        statusIndicator.className = "status-indicator disconnected";
        statusText.innerText = "Desconectado";
        appendLog("[WEB] Conexión perdida. Intentando reconectar en 3 segundos...");
        setTimeout(connectWebSocket, 3000);
    };

    socket.onerror = (err) => {
        console.error("Error en WebSocket:", err);
    };
}

// Append log helper
function appendLog(line) {
    const consoleEl = document.getElementById("log-console");
    if (consoleEl.innerText === "Cargando consola...") {
        consoleEl.innerText = "";
    }
    consoleEl.innerText += line + "\n";
    
    // Auto scroll to bottom
    const wrapper = consoleEl.parentElement;
    wrapper.scrollTop = wrapper.scrollHeight;
}

// Update progress bar
function updateProgressUI(val, text) {
    const fill = document.getElementById("progress-fill");
    const textEl = document.getElementById("progress-text");
    const percentEl = document.getElementById("progress-percent");

    const percent = Math.round(val * 100);
    fill.style.width = `${percent}%`;
    percentEl.innerText = `${percent}%`;
    textEl.innerText = text;

    if (val >= 1.0) {
        setProcessingState(false);
        loadHistory(); // Reload history table after task finish
    }
}

// Deactivate controls during execution
function setProcessingState(processing) {
    isProcessing = processing;
    document.getElementById("btn-analyze").disabled = processing;
    document.getElementById("btn-copy").disabled = processing;
    document.getElementById("lib-path").disabled = processing;
    document.getElementById("dest-path").disabled = processing;
    document.getElementById("strategy-select").disabled = processing;
    
    const browseButtons = document.querySelectorAll(".btn-browse");
    browseButtons.forEach(btn => btn.disabled = processing);
}

// Action triggers
async function triggerAnalyze() {
    if (isProcessing) return;
    
    // Auto-save changes first
    await saveSettingsFromUI();

    if (!currentSettings.main_library_path) {
        appendLog("[WARNING] Debe configurar la ruta de la biblioteca Calibre.");
        return;
    }
    if (currentSettings.scan_folders.length === 0) {
        appendLog("[WARNING] Debe añadir al menos una carpeta de origen a analizar.");
        return;
    }

    setProcessingState(true);
    updateProgressUI(0, "Iniciando análisis...");
    socket.send(JSON.stringify({ action: "analyze" }));
}

async function triggerCopy() {
    if (isProcessing) return;

    // Auto-save changes first
    await saveSettingsFromUI();

    if (!currentSettings.destination_folder) {
        appendLog("[WARNING] Debe configurar la ruta de la carpeta de destino.");
        return;
    }

    setProcessingState(true);
    updateProgressUI(0, "Iniciando copia...");
    socket.send(JSON.stringify({ action: "copy" }));
}

// REST: Load history table
async function loadHistory() {
    try {
        const response = await fetch("/api/history");
        if (response.ok) {
            const data = await response.json();
            const tbody = document.getElementById("history-tbody");
            tbody.innerHTML = "";

            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No hay registros de sincronización disponibles.</td></tr>';
                return;
            }

            data.forEach(row => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${row.timestamp}</td>
                    <td style="color: #3fb950; font-weight: 500;">+ ${row.files_copied}</td>
                    <td style="color: ${row.errors_encountered > 0 ? '#ff7b72' : 'var(--text-muted)'}">${row.errors_encountered}</td>
                    <td>${row.summary}</td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error("Error al cargar historial:", err);
    }
}

// Directory Browser Logic (Server-side Explorer modal)
function openFolderBrowser(targetInputId) {
    if (isProcessing) return;
    currentBrowserTarget = targetInputId;
    
    // Select path starting point
    let initialPath = "";
    if (targetInputId === 'lib-path') {
        initialPath = document.getElementById("lib-path").value;
    } else if (targetInputId === 'dest-path') {
        initialPath = document.getElementById("dest-path").value;
    }
    
    // Trigger modal rendering
    document.getElementById("folder-modal").classList.add("active");
    navigateFolder(initialPath);
}

function closeFolderBrowser() {
    document.getElementById("folder-modal").classList.remove("active");
    selectedFolderInBrowser = "";
}

async function navigateFolder(targetPath) {
    try {
        const response = await fetch(`/api/browse?path=${encodeURIComponent(targetPath || '')}`);
        if (response.ok) {
            const data = await response.json();
            
            if (data.error) {
                // If path not found or error, try default navigate
                console.warn(data.error);
                if (targetPath) {
                    navigateFolder(""); // Fallback to root
                }
                return;
            }

            currentBrowserPath = data.current_path;
            selectedFolderInBrowser = data.current_path;
            document.getElementById("modal-path-input").value = data.current_path;

            // Handle parent directory item
            const parentItem = document.getElementById("modal-parent-item");
            if (data.parent_path) {
                parentItem.style.display = "flex";
                parentItem.onclick = () => navigateFolder(data.parent_path);
            } else {
                parentItem.style.display = "none";
            }

            // Render subdirectories
            const itemsContainer = document.getElementById("modal-folder-items");
            itemsContainer.innerHTML = "";

            if (data.directories.length === 0) {
                itemsContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; padding: 15px;">Esta carpeta no contiene subdirectorios.</div>';
                return;
            }

            data.directories.forEach(dir => {
                const div = document.createElement("div");
                div.className = "folder-item";
                div.innerHTML = `
                    <span class="folder-icon">📁</span>
                    <span class="folder-name">${dir.name}</span>
                `;
                div.onclick = (e) => {
                    // Double click to navigate in
                    if (div.classList.contains("selected")) {
                        navigateFolder(dir.path);
                    } else {
                        // Single click to select
                        document.querySelectorAll(".folder-item").forEach(el => el.classList.remove("selected"));
                        div.classList.add("selected");
                        selectedFolderInBrowser = dir.path;
                    }
                };
                itemsContainer.appendChild(div);
            });
        }
    } catch (err) {
        console.error("Error al explorar carpeta:", err);
    }
}

// Confirm button selection inside folder explorer modal
async function confirmFolderSelection() {
    if (!selectedFolderInBrowser) return;

    if (currentBrowserTarget === 'lib-path') {
        document.getElementById("lib-path").value = selectedFolderInBrowser;
        await saveSettingsFromUI();
    } else if (currentBrowserTarget === 'dest-path') {
        document.getElementById("dest-path").value = selectedFolderInBrowser;
        await saveSettingsFromUI();
    } else if (currentBrowserTarget === 'add-scan-folder') {
        if (!currentSettings.scan_folders.includes(selectedFolderInBrowser)) {
            currentSettings.scan_folders.push(selectedFolderInBrowser);
            renderScanFolders();
            await saveSettingsFromUI();
            appendLog(`[WEB] Añadida carpeta de origen: ${selectedFolderInBrowser}`);
        }
    }

    closeFolderBrowser();
}
