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

// Función para inicializar el gráfico de categorías
function initializeCategoryChart(data) {
    return Highcharts.chart('categoriasChart', {
        chart: {
            type: 'bar',
            height: '400px'
        },
        title: {
            text: 'Distribución de Tickets por Categoría'
        },
        xAxis: {
            categories: Object.keys(data),
            labels: {
                style: { color: '#ffffff' }
            },
            gridLineWidth: 0
        },
        yAxis: {
            title: {
                text: 'Cantidad de Tickets',
                style: { color: '#ffffff' }
            },
            labels: {
                style: { color: '#ffffff' }
            },
            gridLineColor: 'rgba(255, 255, 255, 0.1)'
        },
        plotOptions: {
            bar: {
                borderRadius: 8,
                dataLabels: {
                    enabled: true,
                    color: '#ffffff',
                    style: {
                        textOutline: 'none'
                    }
                },
                groupPadding: 0.1
            }
        },
        series: [{
            name: 'Tickets',
            data: Object.values(data)
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
            text: 'Estados de Tickets'
        },
        tooltip: {
            headerFormat: '',
            pointFormat: '<span style="color:{point.color}">\u25CF</span> <b>{point.name}</b><br/>' +
                'Tickets: <b>{point.y}</b><br/>' +
                'Porcentaje: <b>{point.percentage:.1f}%</b>'
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
            borderRadius: 5,
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
    const categories = Object.keys(data);
    const values = Object.values(data);

    return Highcharts.chart('tendenciaChart', {
        chart: {
            type: 'areaspline'
        },
        title: {
            text: 'Tendencia Mensual de Tickets'
        },
        xAxis: {
            categories: categories,
            labels: {
                style: { color: '#ffffff' }
            },
            gridLineWidth: 0
        },
        yAxis: {
            title: {
                text: 'Cantidad de Tickets',
                style: { color: '#ffffff' }
            },
            labels: {
                style: { color: '#ffffff' }
            },
            gridLineColor: 'rgba(255, 255, 255, 0.1)'
        },
        plotOptions: {
            areaspline: {
                fillOpacity: 0.5,
                marker: {
                    radius: 4,
                    lineColor: '#666666',
                    lineWidth: 1
                }
            }
        },
        series: [{
            name: 'Tickets',
            data: values
        }]
    });
}

// Función para exportar gráficos
function exportChart(chartId) {
    const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === chartId);
    if (chart) {
        chart.exportChart({
            type: 'image/jpeg',
            filename: `chart-${chartId}`
        });
    }
}