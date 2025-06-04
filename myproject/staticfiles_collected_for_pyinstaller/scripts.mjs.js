// Función para mostrar el mensaje "No hay datos disponibles" en una tabla
function showNoDataMessage(table) {
    const tbody = table.querySelector('tbody');
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="10">No hay datos disponibles</td></tr>';
    }
}

// Función para cargar y parsear datos JSON
function loadJsonData(dataKey) {
    const dataScript = document.getElementById('datos-json');
    if (!dataScript || !dataScript.textContent.trim()) {
        console.error('No se encontraron datos JSON');
        return null;
    }

    const data = getJsonData(dataKey);
    if (!data) {
        showNoDataMessage(table);
        return;
    }
    
    // Si necesitas validar la estructura:
    if (!validateJsonData(data)) {
        console.error('Datos JSON no válidos');
        showNoDataMessage(table);
        return;
    }
    return data;
}

// Función para cargar datos en una tabla
function loadTableData(tableId, dataKey) {
    const table = document.getElementById(tableId);
    if (!table) {
        console.error('No se encontró la tabla con ID:', tableId);
        return;
    }

    const data = loadJsonData(dataKey);
    if (!data || data.length === 0) {
        showNoDataMessage(table);
        return;
    }

    const tbody = table.querySelector('tbody');
    tbody.innerHTML = ''; // Limpiar el contenido anterior

    data.forEach(item => {
        const row = document.createElement('tr');
        Object.values(item).forEach(value => {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.appendChild(cell);
        });
        tbody.appendChild(row);
    });
}

// Función para ordenar la tabla
function sortTable(table, columnIndex) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const th = table.querySelector(`th:nth-child(${columnIndex + 1})`);
    const isAscending = !th.classList.contains('asc');

    // Resetear clases de ordenación en todos los encabezados
    table.querySelectorAll('th').forEach(th => th.classList.remove('asc', 'desc'));

    // Obtener el tipo de dato de la columna (numérico o alfabético)
    const dataType = th.dataset.type || 'text'; // Usamos un atributo data-type en las th

    rows.sort((a, b) => {
        const aValue = a.querySelector(`td:nth-child(${columnIndex + 1})`).textContent.trim();
        const bValue = b.querySelector(`td:nth-child(${columnIndex + 1})`).textContent.trim();

        if (dataType === 'number') {
            const numA = parseFloat(aValue);
            const numB = parseFloat(bValue);
            return isAscending ? numA - numB : numB - numA;
        } else {
            return isAscending ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
        }
    });

    // Actualizar clases de ordenación en el encabezado actual
    th.classList.add(isAscending ? 'asc' : 'desc');

    // Reinsertar filas ordenadas
    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
}

// Evento DOMContentLoaded para cargar datos y habilitar ordenación
document.addEventListener('DOMContentLoaded', () => {
    const dataScript = document.getElementById('datos-json');
    if (dataScript && dataScript.textContent.trim()) {
        try {
            jsonData = JSON.parse(dataScript.textContent);
        } catch (error) {
            console.error('Error al parsear JSON:', error);
        }
    } else {
        console.error('No se encontraron datos JSON');
    }
});
    const datos = {
        'contratos_individuales_body': 'contratos_individuales',
        'afiliados_individuales_body': 'afiliados_individuales',
        'referencias_renovaciones_individuales_body': 'referencias_renovaciones_individuales',
        'estatus_contratos_individuales_body': 'estatus_contratos_individuales',
        'estatus_afiliados_individuales_body': 'estatus_afiliados_individuales',
        'estatus_recibos_individuales_body': 'estatus_recibos_individuales',
        'seguimientos_individuales_body': 'seguimientos_individuales',
        'contratos_colectivos_body': 'contratos_colectivos',
        'titular_colectivo_body': 'titular_colectivo',
        'afiliados_colectivos_body': 'afiliados_colectivos',
        'vigencia_renovacion_colectivo_body': 'vigencia_renovacion_colectivo',
        'estatus_contratos_colectivos_body': 'estatus_contratos_colectivos',
        'estatus_afiliados_colectivos_body': 'estatus_afiliados_colectivos',
        'estatus_recibos_colectivos_body': 'estatus_recibos_colectivos',
        'seguimientos_colectivos_body': 'seguimientos_colectivos',
        'contratantes_auxicol_body': 'contratantes_auxicol',
        'contactos_auxicol_body': 'contactos_auxicol',
        'afiliados_auxicol_body': 'afiliados_auxicol',
        'titulares_auxicol_body': 'titulares_auxicol',
        'contratos_recibos_body': 'contratos_recibos',
        'recibos_body': 'recibos',
        'contratantes_recibos_body': 'contratantes_recibos',
        'intermediarios_recibos_body': 'intermediarios_recibos',
        'tarifas_de_importes_0_a_65_body': 'tarifas_de_importes_0_a_65',
        'tarifas_de_importes_66_a_70_body': 'tarifas_de_importes_66_a_70',
        'tarifas_de_importes_76_a_80_body': 'tarifas_de_importes_76_a_80',
        'tarifas_de_importes_81_a_89_body': 'tarifas_de_importes_81_a_89',
        'tarifas_de_importes_90_a_99_body': 'tarifas_de_importes_90_a_99',
        'validaciones_colectivos_body': 'validaciones_colectivos',
        'fechas_colectivos_body': 'fechas_colectivos',
        'planes_colectivos_body': 'planes_colectivos',
        'colectivos_body': 'colectivos',
    };

    function getJsonData(key) {
        if (!jsonData) {
            console.error('Datos JSON no cargados');
            return null;
        }
        if (!jsonData.hasOwnProperty(key)) {
            console.error('Clave no encontrada en datos JSON:', key);
            return null;
        }
        return jsonData[key];
    }
    
    function validateJsonData(data) {
        if (!Array.isArray(data)) {
            console.error("Los datos deben ser un array");
            return false;
        }
    
        for (const item of data) {
            if (typeof item !== "object" || item === null) {
                console.error("Cada elemento debe ser un objeto");
                return false;
            }
    
            if (!item.hasOwnProperty("nombre") || typeof item.nombre !== "string") {
                console.error("Falta la propiedad 'nombre' o no es una cadena");
                return false;
            }
    
            if (!item.hasOwnProperty("edad") || typeof item.edad !== "number") {
                console.error("Falta la propiedad 'edad' o no es un número");
                return false;
            }
        }
    
        return true;
    }


    for (const tableId in datos) {
        loadTableData(tableId, datos[tableId]);
    }

    // Habilitar ordenación de tablas
    if (dataType === 'date') { // Nuevo caso para fechas
        const dateA = new Date(aValue);
        const dateB = new Date(bValue);
        return isAscending ? dateA - dateB : dateB - dateA;
    }

    // Abrir la primera pestaña por defecto al cargar la página
    const firstTabButton = document.querySelector('.tab-button');
    if (firstTabButton) {
        firstTabButton.click(); // Abre la primera pestaña por defecto
    }

    // Renderizar gráficos
    renderAllCharts({
        contratos: JSON.parse(document.getElementById('datos-json').textContent).contratos_individuales,
        afiliados: JSON.parse(document.getElementById('datos-json').textContent).afiliados_individuales,
        estatusContrato: JSON.parse(document.getElementById('datos-json').textContent).estatus_contratos_individuales,
        referenciasRenovacion: JSON.parse(document.getElementById('datos-json').textContent).referencias_renovaciones_individuales
    });

    // Exportar datos a CSV
    document.querySelectorAll('.export-btn').forEach(button => {
        button.addEventListener('click', function() {
            const tableId = this.dataset.table;
            const table = document.querySelector(`#${tableId}`);
            const csv = [];

            // Encabezados
            const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent);
            csv.push(headers.join(','));

            // Filas
            table.querySelectorAll('tbody tr').forEach(tr => {
                const row = Array.from(tr.querySelectorAll('td')).map(td => {
                    let text = td.textContent;
                    // Escapar comas
                    if (text.includes(',')) text = `"${text}"`;
                    return text;
                });
                csv.push(row.join(','));
            });

            // Descargar archivo
            const csvContent = 'data:text/csv;charset=utf-8,' + csv.join('\n');
            const encodedUri = encodeURI(csvContent);
            const link = document.createElement('a');
            link.setAttribute('href', encodedUri);
            link.setAttribute('download', `${tableId}_export.csv`);
            document.body.appendChild(link);
            link.click();
        });
    });

    // Ajustar ancho de las tablas
    adjustTableWidth();

    // Actualizar layouts de gráficos
    updateChartLayouts();


// Función para manejar las pestañas
function openTab(event, tabName) {
    // Oculta todas las pestañas
    const tabContents = document.querySelectorAll('.tab-pane');
    tabContents.forEach(content => {
        content.style.display = 'none';
    });

    // Muestra el contenido de la pestaña actual
    const activeTab = document.getElementById(tabName);
    if (activeTab) {
        activeTab.style.display = 'block';
    }

    // Agrega la clase "active" al botón que abrió la pestaña
    if (event.currentTarget) {
        event.currentTarget.classList.add('active');
    }
}

// Carrusel de gráficos
let currentSlide = 0;
const carruselItems = document.querySelectorAll('.carrusel-item');
const totalSlides = carruselItems.length;

function showSlide(index) {
    if (index < 0) {
        currentSlide = totalSlides - 1;
    } else if (index >= totalSlides) {
        currentSlide = 0;
    } else {
        currentSlide = index;
    }
    const offset = -currentSlide * 100;
    document.querySelector('.carrusel-inner').style.transform = `translateX(${offset}%)`;
}

document.querySelector('.carrusel-btn.prev').addEventListener('click', () => {
    showSlide(currentSlide - 1);
});

document.querySelector('.carrusel-btn.next').addEventListener('click', () => {
    showSlide(currentSlide + 1);
});

// Auto-avance cada 5 segundos
setInterval(() => {
    showSlide(currentSlide + 1);
}, 5000);

// Búsqueda en tiempo real
document.getElementById('searchInput').addEventListener('input', function() {
    const searchTerm = this.value.toLowerCase();
    const tables = document.querySelectorAll('.table-container table');

    tables.forEach(table => {
        const tbody = table.querySelector('tbody');
        const rows = tbody.querySelectorAll('tr');
        let hasVisibleRows = false;

        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            const matches = Array.from(cells).some(cell =>
                cell.textContent.toLowerCase().includes(searchTerm)
            );
            row.style.display = matches ? '' : 'none';
            if (matches) hasVisibleRows = true;
        });

        // Mostrar mensaje si no hay resultados
        const noDataRow = tbody.querySelector('.no-data');
        if (!hasVisibleRows) {
            if (!noDataRow) {
                const tr = document.createElement('tr');
                const td = document.createElement('td');
                td.colSpan = table.querySelectorAll('th').length;
                td.textContent = 'No hay resultados';
                tr.classList.add('no-data');
                tr.appendChild(td);
                tbody.appendChild(tr);
            }
        } else if (noDataRow) {
            noDataRow.remove();
        }
    });
});

// Función para renderizar todos los gráficos
function renderAllCharts(data) {
    renderPlanDistributionChart(data);
    renderAgeDistributionChart(data);
    renderContractStatusChart(data);
    renderAnnualIncomeChart(data);
    renderGenderDistributionChart(data);
    renderRiskByAgeChart(data);
    renderBudgetByPlanChart(data);
    renderContractSeniorityChart(data);
    renderGenderMaritalStatusChart(data);
    renderCommissionsByIntermediaryChart(data);
}

// Gráfico de Distribución de Planes Contratados
function renderPlanDistributionChart(data) {
    if (!data.contratos || data.contratos.length === 0) return;

    const plans = data.contratos.reduce((acc, contrato) => {
        acc[contrato.plan_contratado] = (acc[contrato.plan_contratado] || 0) + 1;
        return acc;
    }, {});

    const trace = {
        x: Object.keys(plans),
        y: Object.values(plans),
        type: 'bar',
        marker: {
            color: 'rgba(75, 192, 192, 0.2)',
            line: {
                color: 'rgba(75, 192, 192, 1)',
                width: 1
            }
        }
    };

    const layout = {
        title: 'Distribución de Planes Contratados',
        xaxis: { title: 'Planes' },
        yaxis: { title: 'Número de Contratos' },
        plot_bgcolor: 'rgba(0, 0, 0, 0)', // Fondo transparente
        paper_bgcolor: 'rgba(0, 0, 0, 0)' // Fondo transparente
    };

    Plotly.newPlot('planDistributionChart', [trace], layout);
}

// Gráfico de Distribución de Edades de Afiliados
function renderAgeDistributionChart(data) {
    if (!data.afiliados || data.afiliados.length === 0) return;

    const ages = data.afiliados.map(afiliado => afiliado.edad).sort((a, b) => a - b);

    const trace = {
        x: ages,
        y: ages,
        type: 'scatter',
        mode: 'lines',
        line: {
            color: 'rgba(153, 102, 255, 1)',
            shape: 'spline'
        }
    };

    const layout = {
        title: 'Distribución de Edades de Afiliados',
        xaxis: { title: 'Edad' },
        yaxis: { title: 'Número de Afiliados' },
        plot_bgcolor: 'rgba(0, 0, 0, 0)', // Fondo transparente
        paper_bgcolor: 'rgba(0, 0, 0, 0)' // Fondo transparente
    };

    Plotly.newPlot('ageDistributionChart', [trace], layout);
}

// Gráfico de Estado de los Contratos
function renderContractStatusChart(data) {
    if (!data.estatusContrato || data.estatusContrato.length === 0) return;

    const statuses = data.estatusContrato.reduce((acc, estatus) => {
        acc[estatus.estatus_vigencia] = (acc[estatus.estatus_vigencia] || 0) + 1;
        return acc;
    }, {});

    const trace = {
        labels: Object.keys(statuses),
        values: Object.values(statuses),
        type: 'pie',
        marker: {
            colors: [
                'rgba(255, 99, 132, 0.2)',
                'rgba(54, 162, 235, 0.2)',
                'rgba(255, 206, 86, 0.2)',
                'rgba(75, 192, 192, 0.2)',
                'rgba(153, 102, 255, 0.2)',
                'rgba(255, 159, 64, 0.2)'
            ],
            line: {
                color: [
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(75, 192, 192, 1)',
                    'rgba(153, 102, 255, 1)',
                    'rgba(255, 159, 64, 1)'
                ],
                width: 1
            }
        }
    };

    const layout = {
        title: 'Estado de los Contratos',
        plot_bgcolor: 'rgba(0, 0, 0, 0)', // Fondo transparente
        paper_bgcolor: 'rgba(0, 0, 0, 0)' // Fondo transparente
    };

    Plotly.newPlot('contractStatusChart', [trace], layout);
}

// Gráfico de Ingresos Anuales por Contrato
function renderAnnualIncomeChart(data) {
    if (!data.contratos || data.contratos.length === 0) return;

    const incomes = data.contratos.map(contrato => contrato.ingresos_anuales);

    const trace = {
        x: data.contratos.map(contrato => contrato.contrato_no),
        y: incomes,
        type: 'bar',
        marker: {
            color: 'rgba(255, 159, 64, 0.2)',
            line: {
                color: 'rgba(255, 159, 64, 1)',
                width: 1
            }
        }
    };

    const layout = {
        title: 'Ingresos Anuales por Contrato',
        xaxis: { title: 'Número de Contrato' },
        yaxis: { title: 'Ingresos Anuales' },
        plot_bgcolor: 'rgba(0, 0, 0, 0)', // Fondo transparente
        paper_bgcolor: 'rgba(0, 0, 0, 0)' // Fondo transparente
    };

    Plotly.newPlot('annualIncomeChart', [trace], layout);
}

// Gráfico de Distribución de Género de Afiliados
function renderGenderDistributionChart(data) {
    if (!data.afiliados || data.afiliados.length === 0) return;

    const genders = data.afiliados.reduce((acc, afiliado) => {
        acc[afiliado.sexo] = (acc[afiliado.sexo] || 0) + 1;
        return acc;
    }, {});

    const trace = {
        labels: Object.keys(genders),
        values: Object.values(genders),
        type: 'pie',
        marker: {
            colors: [
                'rgba(255, 99, 132, 0.2)',
                'rgba(54, 162, 235, 0.2)',
                'rgba(255, 206, 86, 0.2)'
            ],
            line: {
                color: [
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)'
                ],
                width: 1
            }
        }
    };

    const layout = {
        title: 'Distribución de Género de Afiliados',
        plot_bgcolor: 'rgba(0, 0, 0, 0)', // Fondo transparente
        paper_bgcolor: 'rgba(0, 0, 0, 0)' // Fondo transparente
    };

    Plotly.newPlot('genderDistributionChart', [trace], layout);
}

// Gráfico de Distribución de Edades para Gestión de Riesgos
function renderRiskByAgeChart(data) {
    if (!data.afiliados || data.afiliados.length === 0) return;

    const ages = data.afiliados.map(afiliado => afiliado.edad);

    const ageRanges = {
        '0-20': ages.filter(age => age <= 20).length,
        '21-40': ages.filter(age => age > 20 && age <= 40).length,
        '41-60': ages.filter(age => age > 40 && age <= 60).length,
        '61+': ages.filter(age => age > 60).length,
    };

    const trace = {
        x: Object.keys(ageRanges),
        y: Object.values(ageRanges),
        type: 'bar',
        marker: {
            color: 'rgba(255, 99, 132, 0.2)',
            line: {
                color: 'rgba(255, 99, 132, 1)',
                width: 1
            }
        }
    };

    const layout = {
        title: 'Distribución de Edades para Gestión de Riesgos',
        xaxis: { title: 'Rango de Edades' },
        yaxis: { title: 'Número de Afiliados' },
        plot_bgcolor: 'rgba(0, 0, 0, 0)', // Fondo transparente
        paper_bgcolor: 'rgba(0, 0, 0, 0)' // Fondo transparente
    };

    Plotly.newPlot('riskByAgeChart', [trace], layout);
}

// Gráfico de Presupuesto por Plan Contratado
function renderBudgetByPlanChart(data) {
    if (!data.contratos || data.contratos.length === 0) return;

    const plans = data.contratos.reduce((acc, contrato) => {
        if (!acc[contrato.plan_contratado]) {
            acc[contrato.plan_contratado] = 0;
        }
        acc[contrato.plan_contratado] += parseFloat(contrato.ingresos_anuales);
        return acc;
    }, {});

    const trace = {
        x: Object.keys(plans),
        y: Object.values(plans),
        type: 'bar',
        marker: {
            color: 'rgba(54, 162, 235, 0.2)',
            line: {
                color: 'rgba(54, 162, 235, 1)',
                width: 1
            }
        }
    };

    const layout = {
        title: 'Presupuesto por Plan Contratado',
        xaxis: { title: 'Plan Contratado' },
        yaxis: { title: 'Ingresos Anuales' },
        plot_bgcolor: 'rgba(0, 0, 0, 0)', // Fondo transparente
        paper_bgcolor: 'rgba(0, 0, 0, 0)' // Fondo transparente
    };

    Plotly.newPlot('budgetByPlanChart', [trace], layout);
}

// Gráfico de Antigüedad de Contratos
function renderContractSeniorityChart(data) {
    if (!data.estatusContrato || data.estatusContrato.length === 0) return;

    const seniority = data.estatusContrato.map(estatus => estatus.anos_antiguedad_contrato).sort((a, b) => a - b);

    const trace = {
        x: seniority,
        y: seniority,
        type: 'scatter',
        mode: 'lines',
        line: {
            color: 'rgba(75, 192, 192, 1)',
            shape: 'spline'
        }
    };

    const layout = {
        title: 'Antigüedad de Contratos',
        xaxis: { title: 'Años de Antigüedad' },
        yaxis: { title: 'Número de Contratos' },
        plot_bgcolor: 'rgba(0, 0, 0, 0)', // Fondo transparente
        paper_bgcolor: 'rgba(0, 0, 0, 0)' // Fondo transparente
    };

    Plotly.newPlot('contractSeniorityChart', [trace], layout);
}

// Gráfico de Distribución de Género y Estado Civil
function renderGenderMaritalStatusChart(data) {
    if (!data.afiliados || data.afiliados.length === 0) return;

    const genderMaritalStatus = data.afiliados.reduce((acc, afiliado) => {
        const key = `${afiliado.sexo} - ${afiliado.estado_civil}`;
        acc[key] = (acc[key] || 0) + 1;
        return acc;
    }, {});

    const trace = {
        labels: Object.keys(genderMaritalStatus),
        values: Object.values(genderMaritalStatus),
        type: 'pie',
        marker: {
            colors: [
                'rgba(255, 99, 132, 0.2)',
                'rgba(54, 162, 235, 0.2)',
                'rgba(255, 206, 86, 0.2)',
                'rgba(75, 192, 192, 0.2)',
                'rgba(153, 102, 255, 0.2)'
            ],
            line: {
                color: [
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(75, 192, 192, 1)',
                    'rgba(153, 102, 255, 1)'
                ],
                width: 1
            }
        }
    };

    const layout = {
        title: 'Distribución de Género y Estado Civil',
        plot_bgcolor: 'rgba(0, 0, 0, 0)', // Fondo transparente
        paper_bgcolor: 'rgba(0, 0, 0, 0)' // Fondo transparente
    };

    Plotly.newPlot('genderMaritalStatusChart', [trace], layout);
}

// Gráfico de Comisiones por Intermediario
function renderCommissionsByIntermediaryChart(data) {
    if (!data.referenciasRenovacion || data.referenciasRenovacion.length === 0) return;

    const commissions = data.referenciasRenovacion.reduce((acc, referencia) => {
        acc[referencia.intermediarios_codigo] = parseFloat(referencia.comision);
        return acc;
    }, {});

    const trace = {
        x: Object.keys(commissions),
        y: Object.values(commissions),
        type: 'bar',
        marker: {
            color: 'rgba(153, 102, 255, 0.2)',
            line: {
                color: 'rgba(153, 102, 255, 1)',
                width: 1
            }
        }
    };

    const layout = {
        title: 'Comisiones por Intermediario',
        xaxis: { title: 'Intermediario' },
        yaxis: { title: 'Comisiones' },
        plot_bgcolor: 'rgba(0, 0, 0, 0)', // Fondo transparente
        paper_bgcolor: 'rgba(0, 0, 0, 0)' // Fondo transparente
    };

    Plotly.newPlot('commissionsByIntermediaryChart', [trace], layout);
}

// Función para ajustar el ancho de las tablas
function adjustTableWidth() {
    document.querySelectorAll('.table-container').forEach(container => {
        const table = container.querySelector('table');
        container.style.width = `${table.offsetWidth}px`;
    });
}

// Configuración responsive para Plotly
const plotlyConfig = {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'],
    displayModeBar: true
};

// Actualizar todos los layouts de gráficos
function updateChartLayouts() {
    const layoutUpdates = {
        plot_bgcolor: 'rgba(0, 0, 0, 0)',
        paper_bgcolor: 'rgba(0, 0, 0, 0)',
        autosize: true,
        margin: {
            l: 50,
            r: 50,
            b: 50,
            t: 50,
            pad: 4
        }
    };

    document.querySelectorAll('.plotly-graph-div').forEach(chart => {
        Plotly.relayout(chart, layoutUpdates);
    });
}

window.addEventListener('resize', updateChartLayouts);

// Manejo de datos JSON en tablas
const dataScript = document.getElementById('datos-json');
if (!dataScript || !dataScript.textContent.trim()) { // Verifica si dataScript existe y tiene contenido
    console.error('No se encontró el elemento con ID: datos-json o está vacío');

    // Mostrar mensaje "sin datos" en TODAS las tablas
    const datos = { // Objeto con los IDs de las tablas
        'contratos_individuales_body': 'contratos_individuales',
        'afiliados_individuales_body': 'afiliados_individuales',
        'referencias_renovaciones_individuales_body': 'referencias_renovaciones_individuales',
        'estatus_contratos_individuales_body': 'estatus_contratos_individuales',
        'estatus_afiliados_individuales_body': 'estatus_afiliados_individuales',
        'estatus_recibos_individuales_body': 'estatus_recibos_individuales',
        'seguimientos_individuales_body': 'seguimientos_individuales',
        'contratos_colectivos_body': 'contratos_colectivos',
        'titular_colectivo_body': 'titular_colectivo',
        'afiliados_colectivos_body': 'afiliados_colectivos',
        'vigencia_renovacion_colectivo_body': 'vigencia_renovacion_colectivo',
        'estatus_contratos_colectivos_body': 'estatus_contratos_colectivos',
        'estatus_afiliados_colectivos_body': 'estatus_afiliados_colectivos',
        'estatus_recibos_colectivos_body': 'estatus_recibos_colectivos',
        'seguimientos_colectivos_body': 'seguimientos_colectivos',
        'contratantes_auxicol_body': 'contratantes_auxicol',
        'contactos_auxicol_body': 'contactos_auxicol',
        'afiliados_auxicol_body': 'afiliados_auxicol',
        'titulares_auxicol_body': 'titulares_auxicol',
        'contratos_recibos_body': 'contratos_recibos',
        'recibos_body': 'recibos',
        'contratantes_recibos_body': 'contratantes_recibos',
        'intermediarios_recibos_body': 'intermediarios_recibos',
        'tarifas_de_importes_0_a_65_body': 'tarifas_de_importes_0_a_65',
        'tarifas_de_importes_66_a_70_body': 'tarifas_de_importes_66_a_70',
        'tarifas_de_importes_76_a_80_body': 'tarifas_de_importes_76_a_80',
        'tarifas_de_importes_81_a_89_body': 'tarifas_de_importes_81_a_89',
        'tarifas_de_importes_90_a_99_body': 'tarifas_de_importes_90_a_99',
        'validaciones_colectivos_body': 'validaciones_colectivos',
        'fechas_colectivos_body': 'fechas_colectivos',
        'planes_colectivos_body': 'planes_colectivos',
        'colectivos_body': 'colectivos',
    };

    for (const tableId in datos) {
        const table = document.getElementById(tableId);
        if (table) {
            const tbody = table.querySelector('tbody');
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="10">No se encontraron datos JSON</td></tr>';
            }
        }
    }
    return;
}

    const jsonContent = dataScript.textContent.trim();
    if (!jsonContent) {
        console.error('El elemento datos-json está vacío');
        table.querySelector('tbody').innerHTML = '<tr><td colspan="10">No hay datos disponibles</td></tr>';
        return;
    }

    try {
        const datosJson = JSON.parse(jsonContent);
        const data = datosJson[dataKey];

        if (!data || data.length === 0) {
            table.querySelector('tbody').innerHTML = '<tr><td colspan="10">No hay datos disponibles</td></tr>';
            return;
        }

        const tbody = table.querySelector('tbody');
        tbody.innerHTML = ''; // Limpiar el contenido anterior

        data.forEach(item => {
            const row = document.createElement('tr');
            Object.values(item).forEach(value => {
                const cell = document.createElement('td');
                cell.textContent = value;
                row.appendChild(cell);
            });
            tbody.appendChild(row);
        });

    } catch (error) {
        console.error('Error al cargar o parsear los datos:', error);
        table.querySelector('tbody').innerHTML = '<tr><td colspan="10">Error al cargar los datos</td></tr>';
    }
