// Variables globales
let dashboardData = null;
const charts = {};

// Funciones de utilidad
function showLoading() {
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

// Función para animar valores
function animateValue(elementId, endValue, isPercentage = false) {
    const element = document.getElementById(elementId);
    const duration = 1000;
    const startValue = 0;
    const range = endValue - startValue;
    const increment = range / (duration / 16);
    let currentValue = startValue;

    const animate = () => {
        currentValue += increment;
        if (currentValue >= endValue) {
            currentValue = endValue;
            element.textContent = isPercentage ?
                `${endValue.toFixed(1)}%` :
                Math.round(endValue).toLocaleString();
            return;
        }

        element.textContent = isPercentage ?
            `${currentValue.toFixed(1)}%` :
            Math.round(currentValue).toLocaleString();
        requestAnimationFrame(animate);
    };

    animate();
}

// Función para actualizar el dashboard
function updateDashboard(data) {
    // Guardar datos en sessionStorage
    sessionStorage.setItem('dashboardData', JSON.stringify(data));
    
    dashboardData = data;
    document.getElementById('dashboardContent').classList.remove('hidden');

    // Actualizar estadísticas
    const stats = data.dashboard_stats;
    animateValue('totalTickets', stats.total_tickets);
    animateValue('totalTecnicos', stats.total_tecnicos);
    animateValue('ticketsPendientes', stats.tickets_por_estado['Pendiente'] || 0);

    const resueltos = stats.tickets_por_estado['Resuelto'] || 0;
    const eficiencia = ((resueltos / stats.total_tickets) * 100).toFixed(1);
    animateValue('eficiencia', parseFloat(eficiencia), true);

    // Inicializar gráficos
    charts.categorias = initializeCategoryChart(stats.tickets_por_categoria);
    charts.estados = initializeStatusChart(stats.tickets_por_estado);
    charts.tendencia = initializeTrendChart(stats.tendencia_mensual);

    // Actualizar tabla
    updateTechnicianTable(data.technician_stats);
}

// Función para actualizar la tabla de técnicos
function updateTechnicianTable(techData) {
    const table = document.getElementById('technicianTable');
    const thead = table.querySelector('thead tr');
    const tbody = table.querySelector('tbody');
    const tfoot = table.querySelector('tfoot tr');

    // Obtener meses activos
    const activeMonths = new Set();
    techData.forEach(tech => {
        Object.keys(tech).forEach(key => {
            if (key !== 'Técnico' && tech[key] > 0) {
                activeMonths.add(key);
            }
        });
    });

    // Actualizar encabezados
    thead.innerHTML = '<th class="text-left"><i class="fas fa-user-cog mr-2"></i>Técnico</th>';
    Array.from(activeMonths).sort().forEach(month => {
        thead.innerHTML += `<th class="text-center">${month}</th>`;
    });
    thead.innerHTML += '<th class="text-right">Total</th>';

    // Actualizar filas y calcular totales
    tbody.innerHTML = '';
    const monthTotals = {};
    let grandTotal = 0;

    techData.forEach(tech => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-white/5 cursor-pointer';

        let technicianTotal = 0;
        row.innerHTML = `<td class="font-semibold">
            <i class="fas fa-user mr-2"></i>${tech['Técnico']}
        </td>`;

        Array.from(activeMonths).sort().forEach(month => {
            const tickets = tech[month] || 0;
            technicianTotal += tickets;
            monthTotals[month] = (monthTotals[month] || 0) + tickets;

            row.innerHTML += `<td class="text-center ${tickets > 0 ? 'bg-blue-500/10' : ''}">${tickets}</td>`;
        });

        grandTotal += technicianTotal;
        row.innerHTML += `<td class="text-right font-bold text-blue-400">${technicianTotal}</td>`;

        tbody.appendChild(row);
    });

    // Actualizar footer con totales
    tfoot.innerHTML = '<td class="font-bold text-xl">Total General</td>';
    Array.from(activeMonths).sort().forEach(month => {
        tfoot.innerHTML += `<td class="text-center font-bold text-xl">${monthTotals[month] || 0}</td>`;
    });
    tfoot.innerHTML += `<td class="text-right font-bold text-xl text-blue-400">${grandTotal}</td>`;
}

// Función para exportar tabla a CSV
function exportTableToCSV() {
    if (!dashboardData) return;

    const rows = [['Técnico']];
    const table = document.getElementById('technicianTable');
    const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent.trim());
    rows[0].push(...headers.slice(1));

    dashboardData.technician_stats.forEach(tech => {
        const row = [tech['Técnico']];
        headers.slice(1, -1).forEach(month => {
            row.push(tech[month] || 0);
        });
        const total = row.slice(1).reduce((a, b) => a + b, 0);
        row.push(total);
        rows.push(row);
    });

    const csvContent = "data:text/csv;charset=utf-8," + rows.map(e => e.join(",")).join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "tickets_por_tecnico.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Función para exportar tabla a JPG
async function exportTableToJPG() {
    const tableContainer = document.querySelector('.table-container');
    try {
        const canvas = await html2canvas(tableContainer, {
            scale: 2,
            backgroundColor: '#1a1a1a',
            logging: false,
            useCORS: true,
            allowTaint: true
        });
        
        const link = document.createElement('a');
        link.download = 'tickets_por_tecnico.jpg';
        link.href = canvas.toDataURL('image/jpeg', 1.0);
        link.click();
    } catch (error) {
        console.error('Error al exportar como JPG:', error);
        alert('Error al exportar la imagen. Por favor, intente nuevamente.');
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    // Intentar cargar datos de sessionStorage
    const savedData = sessionStorage.getItem('dashboardData');
    if (savedData) {
        updateDashboard(JSON.parse(savedData));
    }

    // Event listener para el formulario
    document.getElementById('uploadForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        showLoading();

        try {
            const formData = new FormData(e.target);
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if (!data.success) {
                throw new Error(data.error || 'Error procesando el archivo');
            }

            // Limpiar gráficos existentes
            Object.values(charts).forEach(chart => chart?.destroy?.());

            // Actualizar dashboard
            updateDashboard(data.data);
        } catch (error) {
            console.error('Error:', error);
            alert('Error al procesar el archivo: ' + error.message);
        } finally {
            hideLoading();
        }
    });

    // Drag and drop
    const uploadZone = document.querySelector('.upload-zone');
    const fileInput = document.getElementById('fileInput');

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        uploadZone.classList.add('bg-white/10');
    }

    function unhighlight(e) {
        uploadZone.classList.remove('bg-white/10');
    }

    uploadZone.addEventListener('drop', handleDrop, false);
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        fileInput.files = files;

        if (files.length > 0) {
            document.getElementById('uploadForm').dispatchEvent(new Event('submit'));
        }
    }

    fileInput.addEventListener('change', function(e) {
        if (this.files.length > 0) {
            document.getElementById('uploadForm').dispatchEvent(new Event('submit'));
        }
    });
});

// Función para exportar a PDF
function exportTableToPDF() {
    if (!dashboardData) return;

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    const table = document.getElementById('technicianTable');
    const headers = Array.from(table.querySelectorAll('thead th'))
        .map(th => th.textContent.trim());

    const rows = dashboardData.technician_stats.map(tech => {
        const row = [tech['Técnico']];
        headers.slice(1, -1).forEach(month => {
            row.push(tech[month] || 0);
        });
        const total = row.slice(1).reduce((a, b) => a + b, 0);
        row.push(total);
        return row;
    });

    doc.autoTable({
        head: [headers],
        body: rows,
        theme: 'grid',
        styles: {
            fontSize: 8,
            cellPadding: 2,
        },
        headStyles: {
            fillColor: [76, 174, 254],
            textColor: 255
        },
        alternateRowStyles: {
            fillColor: [245, 245, 245]
        }
    });

    doc.save('tickets_por_tecnico.pdf');
}

// Función para exportar todos los gráficos
function exportAllCharts() {
    Object.entries(charts).forEach(([key, chart]) => {
        if (chart) {
            chart.exportChart({
                type: 'image/jpeg',
                filename: `chart-${key}`
            });
        }
    });
}

// Función para recargar datos
function reloadData() {
    const savedData = sessionStorage.getItem('dashboardData');
    if (savedData) {
        updateDashboard(JSON.parse(savedData));
    }
}

// Función para limpiar datos
function clearData() {
    sessionStorage.removeItem('dashboardData');
    location.reload();
}

// Agregar event listeners para los clics en las cards
document.querySelectorAll('.stats-card').forEach(card => {
    card.addEventListener('click', function() {
        const type = this.getAttribute('data-type');
        window.location.href = `ticket-details.html?type=${type}`;
    });
});

// Función para actualizar charts cuando cambia el tamaño de la ventana
window.addEventListener('resize', function() {
    Object.values(charts).forEach(chart => {
        if (chart && chart.reflow) {
            chart.reflow();
        }
    });
});
