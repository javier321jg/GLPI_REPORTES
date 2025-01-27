document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const technician = urlParams.get('technician');
    
    if (technician) {
        loadTechnicianDetails(technician);
    } else {
        showError('No se especificó un técnico');
    }
});

async function loadTechnicianDetails(technician) {
    try {
        showLoading();
        
        const response = await fetch(`/api/tickets/filter?type=tech&value=${encodeURIComponent(technician)}`);
        const result = await response.json();
        
        if (result.success) {
            updateDetailsView(technician, result.data.tickets);
        } else {
            showError('Error al cargar los detalles: ' + result.error);
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Error al cargar los detalles del técnico');
    } finally {
        hideLoading();
    }
}

function updateDetailsView(technician, tickets) {
    // Actualizar título
    document.getElementById('technicianName').textContent = technician;
    
    // Actualizar estadísticas
    updateStatistics(tickets);
    
    // Actualizar tabla de tickets
    updateTicketsTable(tickets);
    
    // Mostrar contenido
    document.getElementById('detailsContent').classList.remove('hidden');
}

function updateStatistics(tickets) {
    const stats = {
        total: tickets.length,
        pendientes: tickets.filter(t => t.status === 'Pendiente').length,
        resueltos: tickets.filter(t => t.status === 'Resuelto').length
    };
    
    stats.eficiencia = stats.total > 0 ? 
        ((stats.resueltos / stats.total) * 100).toFixed(1) : 0;
    
    document.getElementById('totalTickets').textContent = stats.total;
    document.getElementById('ticketsPendientes').textContent = stats.pendientes;
    document.getElementById('ticketsResueltos').textContent = stats.resueltos;
    document.getElementById('eficiencia').textContent = `${stats.eficiencia}%`;
}

function updateTicketsTable(tickets) {
    const tbody = document.querySelector('#ticketsTable tbody');
    tbody.innerHTML = '';
    
    tickets.forEach(ticket => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-700/30 transition-all duration-200';
        
        row.innerHTML = `
            <td class="p-3">${ticket.id}</td>
            <td class="p-3">${ticket.title}</td>
            <td class="p-3">${ticket.category}</td>
            <td class="p-3">${ticket.status}</td>
            <td class="p-3">${formatDate(ticket.date)}</td>
            <td class="p-3 text-center">
                <button onclick="showTicketDetails(${ticket.id})" 
                        class="btn-primary text-sm">
                    <i class="fas fa-eye mr-2"></i>Ver
                </button>
            </td>
        `;
        
        tbody.appendChild(row);
    });
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('es-ES', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

function showTicketDetails(ticketId) {
    // Implementar vista detallada del ticket
    window.location.href = `/ticket.html?id=${ticketId}`;
}

function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
}

function showLoading() {
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

// Exportar funciones necesarias
window.showTicketDetails = showTicketDetails;