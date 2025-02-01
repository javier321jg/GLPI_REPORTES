// Configuración global de Highcharts
Highcharts.setOptions({
    chart: {
      style: {
        fontFamily: 'Inter, system-ui, sans-serif'
      },
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      borderRadius: 20,
      plotBorderWidth: 0
    },
    colors: ['#4caefe', '#3dc3e8', '#2dd9db', '#1feeaf', '#0ff3a0', '#00e887'],
    title: {
      style: {
        color: '#ffffff',
        fontWeight: 'bold'
      }
    },
    legend: {
      itemStyle: {
        color: '#ffffff'
      },
      itemHoverStyle: {
        color: '#4caefe'
      }
    },
    tooltip: {
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      style: {
        color: '#ffffff'
      }
    }
  });
  
  // Variables globales
  let dashboardData = null;
  const charts = {};
  let currentChartType = 'bar';
  
  // Funciones de utilidad
  function showLoading() {
    document.getElementById('loadingOverlay').classList.remove('hidden');
  }
  
  function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
  }
  
  function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
                  <div class="flex items-center gap-2">
                      <i class="fas ${type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
                      ${message}
                  </div>
              `;
    document.body.appendChild(notification);
  
    setTimeout(() => notification.classList.add('show'), 100);
    setTimeout(() => {
      notification.classList.remove('show');
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }
  
  // Función para animar valores
  function animateValue(elementId, endValue, isPercentage = false) {
    const element = document.getElementById(elementId);
    const duration = 1500;
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
    try {
      sessionStorage.setItem('dashboardData', JSON.stringify(data));
      dashboardData = data;
      document.getElementById('dashboardContent').classList.remove('hidden');
  
      const stats = data.dashboard_stats;
  
      // Actualizar estadísticas
      animateValue('totalTickets', stats.total_tickets);
      animateValue('totalTecnicos', stats.total_tecnicos);
      animateValue('ticketsPendientes', stats.tickets_por_estado['Pendiente'] || 0);
  
      const resueltos = stats.tickets_por_estado['Resuelto'] || 0;
      const eficiencia = ((resueltos / stats.total_tickets) * 100);
      animateValue('eficiencia', eficiencia, true);
  
      // Inicializar gráficos principales
      charts.categorias = initializeCategoryChart(stats.tickets_por_categoria);
      charts.estados = initializeStatusChart(stats.tickets_por_estado);
      charts.tendencia = initializeTrendChart(stats.tendencia_mensual);
  
      // Actualizar tabla de técnicos
      updateTechnicianTable(data.technician_stats);
  
      // Inicializar gráfico de técnicos (si existe previamente, lo destruye)
      if (charts.technician) charts.technician.destroy();
      charts.technician = initializeTechnicianChart(data.technician_stats);
    } catch (error) {
      showNotification(error.message, 'error');
    }
  }
  
  // Función para inicializar el gráfico de categorías
  function initializeCategoryChart(data) {
    return Highcharts.chart('categoriasChart', {
      chart: {
        type: currentChartType,
        height: '400px'
      },
      title: {
        text: 'Distribución de Tickets por Categoría',
        align: 'left'
      },
      xAxis: {
        categories: Object.keys(data),
        labels: {
          style: { color: '#ffffff' },
          rotation: -45
        }
      },
      yAxis: {
        title: {
          text: 'Cantidad de Tickets',
          style: { color: '#ffffff' }
        },
        labels: {
          style: { color: '#ffffff' }
        }
      },
      plotOptions: {
        series: {
          borderRadius: 8,
          dataLabels: {
            enabled: true,
            color: '#ffffff',
            style: {
              textOutline: 'none'
            }
          }
        }
      },
      series: [{
        name: 'Tickets',
        data: Object.values(data),
        colorByPoint: true
      }]
    });
  }
  
  // Función para inicializar el gráfico de estados
  function initializeStatusChart(data) {
    return Highcharts.chart('estadosChart', {
      chart: {
        type: 'variablepie'
      },
      title: {
        text: 'Estados de Tickets',
        align: 'left'
      },
      tooltip: {
        pointFormat: '<b>{point.name}</b>: {point.y} tickets<br>({point.percentage:.1f}%)'
      },
      plotOptions: {
        variablepie: {
          allowPointSelect: true,
          cursor: 'pointer',
          dataLabels: {
            enabled: true,
            format: '<b>{point.name}</b>: {point.percentage:.1f}%',
            style: {
              color: 'white',
              textOutline: 'none'
            }
          }
        }
      },
      series: [{
        minPointSize: 100,
        innerSize: '20%',
        zMin: 0,
        name: 'Estados',
        data: Object.entries(data).map(([name, value]) => ({
          name: name,
          y: value,
          z: value
        }))
      }]
    });
  }
  
  // Función para inicializar el gráfico de tendencia
  function initializeTrendChart(data) {
    return Highcharts.chart('tendenciaChart', {
      chart: {
        type: 'areaspline'
      },
      title: {
        text: 'Tendencia Mensual de Tickets',
        align: 'left'
      },
      xAxis: {
        categories: Object.keys(data),
        labels: {
          style: { color: '#ffffff' }
        }
      },
      yAxis: {
        title: {
          text: 'Cantidad de Tickets',
          style: { color: '#ffffff' }
        },
        labels: {
          style: { color: '#ffffff' }
        }
      },
      plotOptions: {
        areaspline: {
          fillOpacity: 0.5,
          marker: {
            radius: 4
          }
        }
      },
      series: [{
        name: 'Tickets',
        data: Object.values(data)
      }]
    });
  }
  
  // Función para inicializar el gráfico de Tickets por Técnico (columna apilada)
  function initializeTechnicianChart(techData) {
    // Determinar los meses activos de los datos de técnicos
    const activeMonths = new Set();
    techData.forEach(tech => {
      Object.keys(tech).forEach(key => {
        if (key !== 'Técnico' && tech[key] > 0) {
          activeMonths.add(key);
        }
      });
    });
    const months = Array.from(activeMonths).sort();
    const technicianNames = techData.map(tech => tech['Técnico']);
  
    // Preparar los datos de las series: para cada mes, un array con los tickets de cada técnico
    const seriesData = months.map(month => ({
      name: month,
      data: techData.map(tech => tech[month] || 0)
    }));
  
    return Highcharts.chart('technicianChart', {
      chart: {
        type: 'column',
        height: 400,
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        borderRadius: 20
      },
      title: {
        text: 'Desglose de Tickets por Técnico (por Mes)',
        align: 'left',
        style: {
          color: '#ffffff',
          fontWeight: 'bold'
        }
      },
      xAxis: {
        categories: technicianNames,
        labels: {
          style: { color: '#ffffff' }
        },
        title: {
          text: 'Técnicos',
          style: { color: '#ffffff' }
        }
      },
      yAxis: {
        min: 0,
        title: {
          text: 'Cantidad de Tickets',
          style: { color: '#ffffff' }
        },
        labels: {
          style: { color: '#ffffff' }
        },
        gridLineColor: 'rgba(255,255,255,0.1)'
      },
      plotOptions: {
        column: {
          stacking: 'normal',
          dataLabels: {
            enabled: true,
            color: '#ffffff',
            style: { textOutline: 'none' }
          }
        }
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        style: { color: '#ffffff' },
        shared: true,
        headerFormat: '<span style="font-size:10px">{point.key}</span><br/>'
      },
      series: seriesData,
      credits: { enabled: false }
    });
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
    thead.innerHTML = `
                  <th class="text-left">
                      <div class="flex items-center gap-2">
                          <i class="fas fa-user-cog"></i>
                          Técnico
                      </div>
                  </th>
              `;
    Array.from(activeMonths).sort().forEach(month => {
      thead.innerHTML += `
                      <th class="text-center">
                          <div class="flex flex-col items-center">
                              <i class="fas fa-calendar-alt mb-1"></i>
                              ${month}
                          </div>
                      </th>
                  `;
    });
    thead.innerHTML += `
                  <th class="text-right">
                      <div class="flex items-center justify-end gap-2">
                          <i class="fas fa-calculator"></i>
                          Total
                      </div>
                  </th>
              `;
  
    // Actualizar filas
    tbody.innerHTML = '';
    const monthTotals = {};
    let grandTotal = 0;
  
    techData.forEach(tech => {
      const row = document.createElement('tr');
      row.className = 'hover:bg-white/5 cursor-pointer transition-all duration-300';
  
      let technicianTotal = 0;
      row.innerHTML = `
                      <td class="font-semibold">
                          <div class="flex items-center gap-2">
                              <i class="fas fa-user"></i>
                              ${tech['Técnico']}
                          </div>
                      </td>
                  `;
  
      Array.from(activeMonths).sort().forEach(month => {
        const tickets = tech[month] || 0;
        technicianTotal += tickets;
        monthTotals[month] = (monthTotals[month] || 0) + tickets;
  
        row.innerHTML += `
                          <td class="text-center ${tickets > 0 ? 'bg-blue-500/10' : ''} transition-all duration-300">
                              ${tickets}
                          </td>
                      `;
      });
  
      grandTotal += technicianTotal;
      row.innerHTML += `
                      <td class="text-right font-bold text-blue-400">
                          ${technicianTotal}
                      </td>
                  `;
  
      row.addEventListener('click', () => showTechnicianDetails(tech));
      tbody.appendChild(row);
    });
  
    // Actualizar footer
    tfoot.innerHTML = `
                  <td class="font-bold text-xl">Total General</td>
                  ${Array.from(activeMonths).sort().map(month => `
                      <td class="text-center font-bold text-xl">${monthTotals[month] || 0}</td>
                  `).join('')}
                  <td class="text-right font-bold text-xl text-blue-400">${grandTotal}</td>
              `;
  }
  
  // Funciones de exportación
  function exportTableToCSV() {
    if (!dashboardData) return;
  
    const rows = [['Técnico']];
    const table = document.getElementById('technicianTable');
    const headers = Array.from(table.querySelectorAll('thead th'))
      .map(th => th.textContent.trim());
  
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
  
    const csvContent = "data:text/csv;charset=utf-8," +
      rows.map(e => e.join(",")).join("\n");
  
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "tickets_por_tecnico.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
  
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
      showNotification('Error al exportar la imagen', 'error');
    }
  }
  
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
  
  function exportChart(chartId) {
    const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === chartId);
    if (chart) {
      chart.exportChart({
        type: 'image/jpeg',
        filename: `chart-${chartId}`
      });
    }
  }
  
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
  
  function toggleChartType(chartId) {
    const chart = charts[chartId];
    if (!chart) return;
  
    currentChartType = currentChartType === 'bar' ? 'column' : 'bar';
    chart.update({
      chart: {
        type: currentChartType
      }
    });
  }
  
  // Funciones de datos
  function reloadData() {
    const savedData = sessionStorage.getItem('dashboardData');
    if (savedData) {
      updateDashboard(JSON.parse(savedData));
    }
  }
  
  function clearData() {
    sessionStorage.removeItem('dashboardData');
    location.reload();
  }
  
  function showTechnicianDetails(tech) {
    window.location.href = `ticket-details.html?tech=${encodeURIComponent(tech['Técnico'])}`;
  }
  
  // Configuración de subida de archivos
  function setupFileUpload() {
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
        processFile(files[0]);
      }
    }
  
    fileInput.addEventListener('change', function () {
      if (this.files.length > 0) {
        processFile(this.files[0]);
      }
    });
  
    document.getElementById('uploadForm').addEventListener('submit', (e) => {
      e.preventDefault();
      const file = fileInput.files[0];
      if (file) {
        processFile(file);
      }
    });
  }
  
  async function processFile(file) {
    showLoading();
    const formData = new FormData();
    formData.append('file', file);
  
    try {
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
      showNotification('Archivo procesado correctamente', 'success');
    } catch (error) {
      showNotification(error.message, 'error');
    } finally {
      hideLoading();
    }
  }
  
  // Inicialización
  document.addEventListener('DOMContentLoaded', function () {
    // Cargar datos guardados
    const savedData = sessionStorage.getItem('dashboardData');
    if (savedData) {
      updateDashboard(JSON.parse(savedData));
    }
  
    // Configurar drag and drop
    setupFileUpload();
  });
  
  // Event listeners globales
  window.addEventListener('resize', function () {
    Object.values(charts).forEach(chart => {
      if (chart && chart.reflow) {
        chart.reflow();
      }
    });
  });
  