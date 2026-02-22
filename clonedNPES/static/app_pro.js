/**
 * ANPR Pro - Professional JavaScript
 * Real-time updates, smooth animations, and interactive features
 */

// ===================================
// State Management
// ===================================

const state = {
    currentPage: 1,
    itemsPerPage: 12,
    viewMode: 'cards',
    filters: {
        plate: '',
        date: ''
    },
    allPlates: [],
    isRunning: false,
    refreshInterval: null
};

// ===================================
// Initialization
// ===================================

document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadData();
    startAutoRefresh();
    checkSystemStatus();
});

// ===================================
// Event Listeners
// ===================================

function initializeEventListeners() {
    // Control buttons
    document.getElementById('startBtn')?.addEventListener('click', startDetection);
    document.getElementById('stopBtn')?.addEventListener('click', stopDetection);
    document.getElementById('refreshBtn')?.addEventListener('click', () => {
        loadData();
        showNotification('Data refreshed', 'success');
    });

    // Logs and export
    document.getElementById('logsBtn')?.addEventListener('click', showLogs);
    document.getElementById('exportBtn')?.addEventListener('click', exportData);

    // Filters
    document.getElementById('plateFilter')?.addEventListener('input', debounce(handleFilterChange, 300));
    document.getElementById('dateFilter')?.addEventListener('change', handleFilterChange);

    // View toggle
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const view = e.currentTarget.dataset.view;
            switchView(view);
        });
    });

    // Pagination
    document.getElementById('prevPage')?.addEventListener('click', () => changePage(-1));
    document.getElementById('nextPage')?.addEventListener('click', () => changePage(1));

    // Video controls
    document.getElementById('toggleVideoBtn')?.addEventListener('click', toggleVideoFeed);
    document.getElementById('fullscreenBtn')?.addEventListener('click', toggleFullscreen);
}

// ===================================
// System Control
// ===================================

async function startDetection() {
    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.status === 'started' || data.status === 'already_running') {
            state.isRunning = true;
            updateSystemStatus(true);
            showNotification('Detection system started successfully', 'success');
        } else if (data.status === 'error') {
            // Show detailed error from backend
            console.error('Backend Detail:', data.details);
            showNotification(`Error: ${data.error}`, 'error');
        } else if (data.status === 'unauthorized') {
            showNotification('Unauthorized. Please login.', 'error');
        } else {
            showNotification('Failed to start: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error starting detection:', error);
        showNotification('Connection Error: Check server logs', 'error');
    }
}

async function stopDetection() {
    try {
        const response = await fetch('/api/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.status === 'stopped' || data.status === 'not_running') {
            state.isRunning = false;
            updateSystemStatus(false);
            showNotification('Detection system stopped', 'info');
        } else {
            showNotification('Failed to stop detection system', 'error');
        }
    } catch (error) {
        console.error('Error stopping detection:', error);
        showNotification('Error stopping detection system', 'error');
    }
}

async function checkSystemStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        state.isRunning = data.running;
        updateSystemStatus(data.running);

        // Update video stats if available
        if (data.stats) {
            updateVideoStats(data.stats);
        }
    } catch (error) {
        console.error('Error checking status:', error);
    }
}

function updateSystemStatus(isRunning) {
    const statusIndicator = document.getElementById('systemStatus');
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const videoSection = document.getElementById('videoSection');
    const videoPlaceholder = document.getElementById('videoPlaceholder');

    if (isRunning) {
        statusIndicator.innerHTML = `
            <span class="status-dot status-running"></span>
            <span class="status-text">System Running</span>
        `;
        startBtn.style.display = 'none';
        stopBtn.style.display = 'inline-flex';

        // Show video feed, hide placeholder
        if (videoSection) {
            videoSection.classList.add('active');
        }
        if (videoPlaceholder) {
            videoPlaceholder.style.display = 'none';
        }
    } else {
        statusIndicator.innerHTML = `
            <span class="status-dot status-stopped"></span>
            <span class="status-text">System Stopped</span>
        `;
        startBtn.style.display = 'inline-flex';
        stopBtn.style.display = 'none';

        // Hide video feed, show placeholder
        if (videoSection) {
            videoSection.classList.remove('active');
        }
        if (videoPlaceholder) {
            videoPlaceholder.style.display = 'flex';
        }
    }
}

function updateVideoStats(stats) {
    // Update video mode
    const videoMode = document.getElementById('videoMode');
    if (videoMode) {
        videoMode.textContent = stats.is_demo ? 'DEMO MODE' : 'LIVE CAMERA';
    }

    // Update FPS
    const videoFPS = document.getElementById('videoFPS');
    if (videoFPS && stats.fps !== undefined) {
        videoFPS.textContent = `${stats.fps.toFixed(1)} FPS`;
    }

    // Update detections count
    const videoDetections = document.getElementById('videoDetections');
    if (videoDetections && stats.detections !== undefined) {
        videoDetections.textContent = `${stats.detections} Detections`;
    }
}

// ===================================
// Video Controls
// ===================================

function toggleVideoFeed() {
    const videoContainer = document.getElementById('videoContainer');
    const toggleBtn = document.getElementById('toggleVideoBtn');

    if (videoContainer.style.display === 'none') {
        videoContainer.style.display = 'block';
        toggleBtn.innerHTML = '<i class="fas fa-eye"></i><span>Hide Feed</span>';
    } else {
        videoContainer.style.display = 'none';
        toggleBtn.innerHTML = '<i class="fas fa-eye-slash"></i><span>Show Feed</span>';
    }
}

function toggleFullscreen() {
    const videoContainer = document.getElementById('videoContainer');
    const fullscreenBtn = document.getElementById('fullscreenBtn');

    if (!document.fullscreenElement) {
        videoContainer.requestFullscreen().catch(err => {
            console.error('Error attempting to enable fullscreen:', err);
        });
        fullscreenBtn.innerHTML = '<i class="fas fa-compress"></i><span>Exit Fullscreen</span>';
    } else {
        document.exitFullscreen();
        fullscreenBtn.innerHTML = '<i class="fas fa-expand"></i><span>Fullscreen</span>';
    }
}

// Listen for fullscreen changes
document.addEventListener('fullscreenchange', () => {
    const fullscreenBtn = document.getElementById('fullscreenBtn');
    if (!document.fullscreenElement && fullscreenBtn) {
        fullscreenBtn.innerHTML = '<i class="fas fa-expand"></i><span>Fullscreen</span>';
    }
});

// ===================================
// Data Loading
// ===================================

async function loadData() {
    try {
        // Load plates data
        const platesResponse = await fetch(`/api/plates?plate=${state.filters.plate}&date=${state.filters.date}`);
        state.allPlates = await platesResponse.json();

        // Load summary statistics
        const summaryResponse = await fetch('/api/summary');
        const summary = await summaryResponse.json();

        updateStatistics(summary);
        renderPlates();
    } catch (error) {
        console.error('Error loading data:', error);
        showNotification('Error loading data', 'error');
    }
}

function updateStatistics(summary) {
    document.getElementById('statTotal').textContent = summary.total || 0;
    document.getElementById('statUnique').textContent = summary.unique || 0;
    document.getElementById('statImages').textContent = summary.total || 0;

    // Calculate average response time (simulated for now)
    const avgTime = Math.floor(Math.random() * 100) + 50;
    document.getElementById('statPerformance').textContent = `${avgTime}ms`;
}

// ===================================
// Rendering
// ===================================

function renderPlates() {
    const start = (state.currentPage - 1) * state.itemsPerPage;
    const end = start + state.itemsPerPage;
    const paginated = state.allPlates.slice(start, end);

    if (state.viewMode === 'cards') {
        renderCards(paginated);
    } else {
        renderTable(paginated);
    }

    updatePagination();
}

function renderCards(plates) {
    const container = document.getElementById('cardsView');

    if (plates.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--text-secondary);">
                <i class="fas fa-inbox" style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.3;"></i>
                <p>No detections found</p>
            </div>
        `;
        return;
    }

    container.innerHTML = plates.map(plate => `
        <div class="detection-card animate-fade-in">
            <img 
                src="/snapshots/${plate.image}" 
                alt="Plate ${plate.plate}"
                class="card-image"
                onclick="showImageModal('/snapshots/${plate.image}')"
                onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22300%22 height=%22150%22%3E%3Crect fill=%22%23151932%22 width=%22300%22 height=%22150%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 fill=%22%236b7280%22 font-family=%22Arial%22%3ENo Image%3C/text%3E%3C/svg%3E'"
            >
            <div class="card-content">
                <div class="card-plate">${plate.plate}</div>
                <div class="card-meta">
                    <div class="card-meta-item">
                        <i class="fas fa-calendar"></i>
                        <span>${plate.date}</span>
                    </div>
                    <div class="card-meta-item">
                        <i class="fas fa-clock"></i>
                        <span>${plate.time}</span>
                    </div>
                    ${plate.user ? `
                    <div class="card-meta-item">
                        <i class="fas fa-user"></i>
                        <span>${plate.user}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
        </div>
    `).join('');
}

function renderTable(plates) {
    const tbody = document.getElementById('tableBody');

    if (plates.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; padding: 3rem; color: var(--text-secondary);">
                    <i class="fas fa-inbox" style="font-size: 2rem; margin-bottom: 1rem; opacity: 0.3; display: block;"></i>
                    No detections found
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = plates.map(plate => `
        <tr class="animate-fade-in">
            <td class="table-plate">${plate.plate}</td>
            <td>${plate.date}</td>
            <td>${plate.time}</td>
            <td>
                <img 
                    src="/snapshots/${plate.image}" 
                    alt="Plate ${plate.plate}"
                    class="table-image"
                    onclick="showImageModal('/snapshots/${plate.image}')"
                    onerror="this.style.display='none'"
                >
            </td>
            <td>${plate.user || '-'}</td>
        </tr>
    `).join('');
}

function updatePagination() {
    const totalPages = Math.ceil(state.allPlates.length / state.itemsPerPage);
    const info = document.getElementById('paginationInfo');

    if (totalPages === 0) {
        info.textContent = 'No results';
    } else {
        info.textContent = `Page ${state.currentPage} of ${totalPages}`;
    }

    document.getElementById('prevPage').disabled = state.currentPage === 1;
    document.getElementById('nextPage').disabled = state.currentPage >= totalPages;
}

// ===================================
// View Switching
// ===================================

function switchView(view) {
    state.viewMode = view;

    // Update button states
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });

    // Show/hide views
    const cardsView = document.getElementById('cardsView');
    const tableView = document.getElementById('tableView');

    if (view === 'cards') {
        cardsView.style.display = 'grid';
        tableView.style.display = 'none';
    } else {
        cardsView.style.display = 'none';
        tableView.style.display = 'block';
    }

    renderPlates();
}

// ===================================
// Filtering
// ===================================

function handleFilterChange() {
    state.filters.plate = document.getElementById('plateFilter').value;
    state.filters.date = document.getElementById('dateFilter').value;
    state.currentPage = 1;
    loadData();
}

// ===================================
// Pagination
// ===================================

function changePage(delta) {
    const totalPages = Math.ceil(state.allPlates.length / state.itemsPerPage);
    const newPage = state.currentPage + delta;

    if (newPage >= 1 && newPage <= totalPages) {
        state.currentPage = newPage;
        renderPlates();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

// ===================================
// Modals
// ===================================

function showImageModal(imageSrc) {
    const modal = document.getElementById('imageModal');
    const img = document.getElementById('modalImage');
    img.src = imageSrc;
    modal.classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

async function showLogs() {
    try {
        const response = await fetch('/api/logs');
        const data = await response.json();

        const logsContent = document.getElementById('logsContent');
        logsContent.textContent = data.lines.join('\n');

        document.getElementById('logsModal').classList.add('active');
    } catch (error) {
        console.error('Error loading logs:', error);
        showNotification('Error loading logs', 'error');
    }
}

// Close modals on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.classList.remove('active');
        });
    }
});

// ===================================
// Export
// ===================================

async function exportData() {
    try {
        const format = 'xlsx'; // Can be made configurable
        window.location.href = `/api/export?format=${format}`;
        showNotification('Exporting data...', 'success');
    } catch (error) {
        console.error('Error exporting data:', error);
        showNotification('Error exporting data', 'error');
    }
}

// ===================================
// Auto Refresh
// ===================================

function startAutoRefresh() {
    state.refreshInterval = setInterval(() => {
        loadData();
    }, 5000); // Refresh every 5 seconds
}

function stopAutoRefresh() {
    if (state.refreshInterval) {
        clearInterval(state.refreshInterval);
    }
}

// ===================================
// Notifications
// ===================================

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} animate-slide-down`;
    notification.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 3000; max-width: 400px;';

    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        info: 'fa-info-circle',
        warning: 'fa-exclamation-triangle'
    };

    notification.innerHTML = `
        <i class="fas ${icons[type] || icons.info}"></i>
        <span>${message}</span>
        <button class="alert-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;

    document.body.appendChild(notification);

    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(400px)';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

// ===================================
// Utility Functions
// ===================================

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ===================================
// Cleanup on page unload
// ===================================

window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
});
