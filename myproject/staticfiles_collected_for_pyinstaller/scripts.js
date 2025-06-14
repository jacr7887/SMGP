/* ======================
    CONFIGURACIÓN GLOBAL
====================== */
const AppConfig = {
    currentSortField: null,
    currentSortOrder: 'asc',
    searchTerm: '',
    currentPage: 1,
    decimales: 2
};

// Prevención de ataques XSS
function sanitizeHTML(str) {
    const temp = document.createElement("div");
    temp.textContent = str;
    return temp.innerHTML;
}

// Función auxiliar para normalizar texto (quitar acentos y a minúsculas)
function normalizeText(text) {
    if (!text) return '';
    return text
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
}

// Funciones Loading
function showLoading(){ const l=document.getElementById("loadingIndicator"); if(l)l.style.display="flex"; }
function hideLoading(){ const l=document.getElementById("loadingIndicator"); if(l)l.style.display="none"; }

// Gestión de pestañas
function initTabs() {
    const tabButtons = document.querySelectorAll(".tab-button");
    if (!tabButtons.length) return;
    tabButtons.forEach((button) => {
        button.addEventListener("click", function (e) {
            e.preventDefault();
            const tabId = this.getAttribute("data-tab");
            if (!tabId) return;
            const url = new URL(window.location);
            url.searchParams.set("tab", tabId);
            window.history.replaceState({}, "", url);
            const form = document.createElement("form");
            form.method = "GET";
            form.action = window.location.pathname;
            const currentParams = new URLSearchParams(window.location.search);
            currentParams.forEach((value, key) => { if (key !== 'tab') { const h=document.createElement("input"); h.type="hidden"; h.name=key; h.value=value; form.appendChild(h); } });
            const i = document.createElement("input"); i.type="hidden"; i.name="tab"; i.value=tabId; form.appendChild(i);
            document.body.appendChild(form); showLoading(); form.submit();
        });
    });
}


// ======================
//    PLOTLY RESIZE (Revisado)
// ======================
function triggerPlotlyResize(activeItem) {
    if (!activeItem) {
        console.warn("triggerPlotlyResize llamado sin activeItem.");
        return;
    }

    const plotlyDiv = activeItem.querySelector('.plotly-graph-div');

    if (plotlyDiv && typeof Plotly !== 'undefined' && Plotly.Plots && Plotly.Plots.resize) {
        // Asegurar que el elemento es visible y tiene dimensiones
        // offsetParent !== null es una buena heurística para visibilidad
        if (plotlyDiv.offsetParent !== null && plotlyDiv.offsetWidth > 0 && plotlyDiv.offsetHeight > 0) {
            try {
                Plotly.Plots.resize(plotlyDiv);
                console.log("Plotly.Plots.resize CALLED ON:", plotlyDiv.id || plotlyDiv);
            } catch (e) {
                console.error("Error resizing Plotly:", e, plotlyDiv);
            }
        } else {
            // Si no es visible, intentarlo una vez más después de un breve delay
            // Esto puede ayudar si la visibilidad se está estableciendo justo ahora.
            console.warn("Plotly div not immediately visible or has no dimensions, trying once more with a short delay:", plotlyDiv.id || plotlyDiv);
            setTimeout(() => {
                if (plotlyDiv.offsetParent !== null && plotlyDiv.offsetWidth > 0 && plotlyDiv.offsetHeight > 0) {
                    try {
                        Plotly.Plots.resize(plotlyDiv);
                        console.log("Plotly.Plots.resize CALLED ON (after delay):", plotlyDiv.id || plotlyDiv);
                    } catch (e) {
                        console.error("Error resizing Plotly (after delay):", e, plotlyDiv);
                    }
                } else {
                     console.warn("Plotly div STILL not visible or has no dimensions after delay:", plotlyDiv.id || plotlyDiv);
                }
            }, 50); // Un delay muy corto para este reintento. El delay principal está en el llamador.
        }
    } else {
        if (!plotlyDiv) console.error("Plotly div not found in activeItem:", activeItem);
        if (typeof Plotly === 'undefined' || !Plotly.Plots || !Plotly.Plots.resize) {
            console.error("Plotly library, Plotly.Plots, or Plotly.Plots.resize not available.");
        }
    }
}

window.addEventListener('resize', debounce(function() {
    console.log("Window resized, attempting to resize active Plotly graph.");
    if (carouselInstance) { // Si el carrusel está inicializado
        const activeCarouselItem = document.querySelector('.carousel-item.active');
        if (activeCarouselItem) {
            triggerPlotlyResize(activeCarouselItem);
        }
    }
    // Para otras gráficas Plotly fuera del carrusel que necesiten redimensionarse:
    document.querySelectorAll('.otra-clase-de-grafica-plotly .plotly-graph-div').forEach(plotlyDiv => {
        if (plotlyDiv.offsetParent !== null && Plotly && Plotly.Plots) {
            Plotly.Plots.resize(plotlyDiv);
        }
    });
}, 250)); // Debounce para evitar llamadas excesivas 


// Búsqueda en gráficas
let carouselInstance = null;
function initGraphSearch() {
    const searchInput = document.querySelector('.search-form input[name="graph_search"]');
    const carouselContainer = document.querySelector(".graphs-carousel-container");
    const carouselInner = carouselContainer?.querySelector(".carousel-inner");

    if (!searchInput || !carouselInner) return;

    searchInput.addEventListener("input", debounce(function(e) {
        const normalizedSearchTerm = normalizeText(sanitizeHTML(e.target.value).trim());
        const allOriginalItems = Array.from(carouselInner.querySelectorAll(".carousel-item"));
        if (!allOriginalItems.length) return;

        let itemsShown = 0;
        let firstVisibleIndex = -1;

        allOriginalItems.forEach((item, index) => {
            const titleElement = item.querySelector(".graph-title");
            const normalizedTitle = normalizeText(titleElement ? titleElement.textContent.trim() : '');
            const shouldShow = normalizedTitle.includes(normalizedSearchTerm);
            item.classList.toggle('search-hidden', !shouldShow);
            item.classList.remove('active');
            if (shouldShow) {
                itemsShown++;
                if (firstVisibleIndex === -1) firstVisibleIndex = index;
            }
        });

        if (firstVisibleIndex !== -1) allOriginalItems[firstVisibleIndex].classList.add('active');

        if (carouselInstance && typeof carouselInstance.updateVisibleItems === 'function') {
            try {
                carouselInstance.updateVisibleItems();
                setTimeout(() => {
                    const activeItemAfterUpdate = carouselInner.querySelector('.carousel-item.active');
                    if(activeItemAfterUpdate && typeof triggerPlotlyResize === 'function') triggerPlotlyResize(activeItemAfterUpdate);
                }, 100);
            } catch (error) {
                console.error("[GraphSearch] ERROR al llamar a updateVisibleItems:", error);
            }
        }
    }, 300));
}

// Popups Exportar/Importar
function initExportPopup() {
    const menuItems = document.querySelectorAll('.nav_item.export-menu');
    if (!menuItems.length) return;

    menuItems.forEach(menuItem => {
        const trigger = menuItem.querySelector('a.export-trigger');
        const popup = menuItem.querySelector('ul.submenu.export-options');
        if (!trigger || !popup) return;

        let closeTimer = null;
        const CLOSE_DELAY = 1500;

        const openPopup = () => {
            clearTimeout(closeTimer);
            document.querySelectorAll('.export-menu .submenu.export-options.active').forEach(otherPopup => {
                if (otherPopup !== popup) {
                    const otherParent = otherPopup.closest('.export-menu');
                    const otherTrigger = otherParent ? otherParent.querySelector('.export-trigger') : null;
                    otherPopup.classList.remove('active');
                    if (otherTrigger) otherTrigger.classList.remove('active');
                }
            });
            popup.classList.add('active');
            trigger.classList.add('active');
            requestAnimationFrame(() => {
                const popupRect = popup.getBoundingClientRect();
                const menuItemRect = menuItem.getBoundingClientRect();
                const viewportHeight = window.innerHeight;
                 if (menuItemRect.top + popupRect.height > viewportHeight - 10) {
                    let newTop = viewportHeight - popupRect.height - 10;
                    newTop = Math.min(menuItemRect.top, Math.max(10, newTop));
                    popup.style.position = 'fixed';
                    popup.style.top = `${newTop}px`;
                    popup.style.left = ''; popup.style.right = '';
                 } else {
                    popup.style.position = ''; popup.style.top = '';
                 }
            });
            startCloseTimer();
        };

        const closePopup = () => {
            clearTimeout(closeTimer);
            popup.classList.remove('active');
            trigger.classList.remove('active');
            popup.style.position = ''; popup.style.top = ''; popup.style.left = ''; popup.style.right = '';
        };

        const startCloseTimer = () => {
            clearTimeout(closeTimer);
            if (popup.classList.contains('active')) closeTimer = setTimeout(closePopup, CLOSE_DELAY);
        };

        trigger.addEventListener('click', (event) => {
            event.preventDefault(); event.stopPropagation();
            if (popup.classList.contains('active')) closePopup();
            else openPopup();
        });
        menuItem.addEventListener('mouseenter', () => clearTimeout(closeTimer));
        menuItem.addEventListener('mouseleave', startCloseTimer);
    });

    document.addEventListener('click', function(event) {
         document.querySelectorAll('.export-menu .submenu.export-options.active').forEach(activePopup => {
            const parentMenuItem = activePopup.closest('.export-menu');
            if (parentMenuItem && !parentMenuItem.contains(event.target)) {
                activePopup.classList.remove('active');
                const activeTrigger = parentMenuItem.querySelector('.export-trigger');
                if (activeTrigger) activeTrigger.classList.remove('active');
                activePopup.style.position = ''; activePopup.style.top = '';
                activePopup.style.left = ''; activePopup.style.right = '';
            }
         });
    });
}


/* ======================
    VISUALIZADOR DE ARCHIVOS (POPUP)
====================== */
/**
 * Abre una URL en una ventana emergente (popup) centrada.
 * @param {string} url - La URL del archivo a mostrar.
 * @param {string} title - El título de la ventana emergente.
 */
function openFilePopup(url, title) {
    const width = 800;
    const height = 600;
    const left = (screen.width / 2) - (width / 2);
    const top = (screen.height / 2) - (height / 2);
    const windowFeatures = `width=${width},height=${height},top=${top},left=${left},resizable=yes,scrollbars=yes,status=yes`;
    
    window.open(url, title, windowFeatures);
}

// NUEVA FUNCIÓN DE INICIALIZACIÓN
function initFilePopups() {
    document.body.addEventListener('click', function(event) {
        const fileLink = event.target.closest('a.file-popup-trigger');
        if (fileLink) {
            event.preventDefault(); // Prevenimos la navegación normal
            const url = fileLink.href;
            const title = fileLink.dataset.popupTitle || 'Visor de Documento';
            openFilePopup(url, title);
        }
    });
    console.log("Manejador de popups para archivos inicializado.");
}

// Comportamientos de Formularios
function initFormBehaviors() {
    document.addEventListener('input', e => { if (e.target.matches('[required]') && e.target.closest('.dark-group.error')) { if (e.target.value.trim()) { const g=e.target.closest('.dark-group'); g.classList.remove('error'); e.target.classList.remove('is-invalid'); g.querySelector('.error-messages')?.remove(); } } });
    document.addEventListener('submit', e => { const form = e.target.closest('form'); if (!form || form.noValidate || form.dataset.noValidate === 'true') return; let isValid = true; form.querySelectorAll('.dark-group.error').forEach(g => g.classList.remove('error')); form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid')); form.querySelectorAll('.error-messages').forEach(el => el.remove()); form.querySelectorAll('[required]').forEach(i => { let ok=true; if(i.type==='checkbox'&&!i.checked)ok=false; else if(i.matches('select')&&!i.value)ok=false; else if(!i.matches('select')&&i.type!=='checkbox'&&!i.value.trim())ok=false; if(!ok){isValid=false; const g=i.closest('.dark-group'); if(g){ g.classList.add('error'); let ec=g.querySelector('.error-messages'); if(!ec){ec=document.createElement('ul'); ec.className='error-messages'; i.parentNode.insertBefore(ec,i.nextSibling);} ec.innerHTML='<li>Obligatorio.</li>';} else i.classList.add('is-invalid');}}); if (!isValid) { e.preventDefault(); alert('Complete los campos requeridos.'); form.querySelector('.error input, .error select, .error textarea, .is-invalid')?.focus(); } else { showLoading(); } });
}

// Confirmaciones
function handleFormConfirmations() {
    document.addEventListener('click', e => { const b=e.target.closest('button[data-confirm], a[data-confirm]'); if(!b)return; const m=(b.dataset.confirm==='true'||b.dataset.confirm==='')?'¿Está seguro?':b.dataset.confirm; if(!confirm(m))e.preventDefault(); else if(b.matches('button[type="submit"]'))showLoading(); });
}

// Carrusel de Gráficas
function initCarousel() {
    const carouselContainer = document.querySelector(".graphs-carousel-container");
    if (!carouselContainer) return null;
    const carouselInner = carouselContainer.querySelector(".carousel-inner");
    const indicatorsContainer = carouselContainer.querySelector(".carousel-indicators");
    const prevBtn = carouselContainer.querySelector(".carousel-control.carousel-prev");
    const nextBtn = carouselContainer.querySelector(".carousel-control.carousel-next");
    if (!carouselInner) return null;
    const originalItems = Array.from(carouselInner.querySelectorAll(".carousel-item"));
    if (originalItems.length === 0) return null;
    let visibleItems = []; let currentVisibleIndex = -1; let indicators = [];

    function updateVisibleItemsList() {
        const previouslyActiveItem = (currentVisibleIndex >= 0 && currentVisibleIndex < visibleItems.length) ? visibleItems[currentVisibleIndex] : null;
        visibleItems = originalItems.filter(item => !item.classList.contains('search-hidden') && item.style.display !== 'none');
        if (indicatorsContainer) {
            indicatorsContainer.innerHTML = ''; indicators = [];
            visibleItems.forEach((item, idx) => { const btn = document.createElement('button'); btn.className='carousel-indicator'; btn.type='button'; btn.dataset.slideToVisible=idx; btn.setAttribute('aria-label',`Gráfica ${originalItems.indexOf(item)+1}`); btn.onclick=()=>showSlide(idx); indicatorsContainer.appendChild(btn); indicators.push(btn); });
        }
        const hasVisible = visibleItems.length > 0;
        if(prevBtn) prevBtn.style.visibility = hasVisible ? 'visible' : 'hidden';
        if(nextBtn) nextBtn.style.visibility = hasVisible ? 'visible' : 'hidden';
        if(indicatorsContainer) indicatorsContainer.style.visibility = hasVisible ? 'visible' : 'hidden';
        let nextIdx = 0;
        if (!hasVisible) { originalItems.forEach(i => i.classList.remove('active')); currentVisibleIndex = -1; return; }
        if (previouslyActiveItem && visibleItems.includes(previouslyActiveItem)) nextIdx = visibleItems.indexOf(previouslyActiveItem);
        nextIdx = Math.max(0, Math.min(nextIdx, visibleItems.length - 1));
        originalItems.forEach(i => i.classList.remove('active'));
        indicators.forEach(ind => ind.classList.remove('active'));
        showSlide(nextIdx, true);
    }

    function showSlide(targetVisibleIndex, forceUpdate = false) {
        if (visibleItems.length === 0 || targetVisibleIndex < 0 || targetVisibleIndex >= visibleItems.length) return;
        const activeItemForResize = visibleItems[targetVisibleIndex];

        // Si no es forzado y es el mismo índice, aún así llama a resize por si acaso el contenedor cambió
        if (!forceUpdate && currentVisibleIndex === targetVisibleIndex) {
            if (activeItemForResize && typeof triggerPlotlyResize === 'function') {
                // Igual llamar con un pequeño delay por si el contenedor padre cambió de tamaño
                // por alguna otra razón (ej. sidebar colapsando)
                setTimeout(() => { // <--- AÑADIR DELAY AQUÍ TAMBIÉN
                     triggerPlotlyResize(activeItemForResize);
                }, 50); // Delay pequeño
            }
            return;
        }

        if (currentVisibleIndex >= 0 && currentVisibleIndex < visibleItems.length) {
            visibleItems[currentVisibleIndex]?.classList.remove("active");
            if (indicators[currentVisibleIndex]) indicators[currentVisibleIndex].classList.remove("active");
        }
        
        const newItem = visibleItems[targetVisibleIndex];
        if (!newItem) return;
        
        newItem.classList.add("active");
        if (indicators[targetVisibleIndex]) indicators[targetVisibleIndex].classList.add("active");
        
        currentVisibleIndex = targetVisibleIndex;

        if (activeItemForResize && typeof triggerPlotlyResize === 'function') {
            // MODIFICACIÓN: Usar setTimeout para asegurar que el DOM está listo
            setTimeout(() => {
                triggerPlotlyResize(activeItemForResize);
            }, 100); // Prueba con 50, 100, o 150. 100 es un buen punto de partida.
        }
    }

    // function triggerPlotlyResize(activeItem) { /* Tu código Plotly aquí */ } // Asegúrate que esta función exista si la llamas
    if (prevBtn) { prevBtn.removeEventListener("click", prevSlideHandler); prevBtn.addEventListener("click", prevSlideHandler); }
    if (nextBtn) { nextBtn.removeEventListener("click", nextSlideHandler); nextBtn.addEventListener("click", nextSlideHandler); }
    function prevSlideHandler() { const ni = (currentVisibleIndex - 1 + visibleItems.length) % visibleItems.length; showSlide(ni); }
    function nextSlideHandler() { const ni = (currentVisibleIndex + 1) % visibleItems.length; showSlide(ni); }
    updateVisibleItemsList();
    return { updateVisibleItems: updateVisibleItemsList };
}

/* ======================
    GESTIÓN DE ARCHIVOS (Usando Delegación)
====================== */
function initFileUploads() {
    document.body.addEventListener('change', function(event) {
        if (event.target.matches('input[type="file"].custom-file-actual-input')) {
            const wrapper = event.target.closest('.custom-file-input-wrapper');
            if (!wrapper) return;
            const display = wrapper.querySelector('.selected-file-display');
            if (!display) return;
            const defaultText = display.dataset.defaultText || 'Ningún archivo seleccionado';
            if (event.target.files && event.target.files.length > 0) {
                display.textContent = Array.from(event.target.files).map(f => f.name).join(', ');
            } else {
                display.textContent = defaultText;
            }
        }
    });

    document.body.addEventListener('click', function(event) {
        // ANTES: if (event.target.matches('.file-button-trigger')) {
    
        // AHORA: Verificar si el elemento clickeado o un ancestro es el botón
        const clickedButton = event.target.closest('.file-button-trigger');
    
        if (clickedButton) { // Si se encontró el botón (o se hizo clic en él o en un hijo)
            console.log("--- DEBUG FILE UPLOAD CLICK ---");
            console.log("Elemento clickeado que activó esto (clickedButton):", clickedButton);
    
            // El wrapper se busca a partir del botón encontrado, no del event.target original
            const wrapper = clickedButton.closest('.custom-file-input-wrapper');
            console.log("Wrapper encontrado:", wrapper);
    
            if (!wrapper) {
                console.log("Wrapper NO encontrado a partir del botón.");
                return;
            }
    
            // Usaremos el selector que busca en profundidad, ya que es más robusto
            const input = wrapper.querySelector('.custom-file-actual-input');
            console.log("Input encontrado con selector profundo:", input);
    
            if (input) {
                if (input.disabled) {
                    console.log("Input está deshabilitado.");
                } else {
                    console.log("Input NO está deshabilitado. Ejecutando input.click().");
                    input.click();
                }
            } else {
                console.log("Input NO encontrado con selector profundo DENTRO del wrapper.");
            }
        }
    });
}

/* ======================
    CÁLCULOS (Implementación nativa)
====================== */
function initCalculations() {
    const calculators = document.querySelectorAll('[data-calculate]');
    if (!calculators.length) return;
    calculators.forEach(calculator => {
        const targetId = calculator.dataset.calculate;
        const target = document.getElementById(targetId);
        if (!target) return;
        const precision = parseInt(calculator.dataset.precision) || AppConfig.decimales || 2;
        const multiplier = parseFloat(calculator.dataset.multiplier || 1);
        const calculateAndUpdate = () => {
            const cleanedValue = String(calculator.value).replace(/,/g, '.').replace(/[^\d.-]/g, '');
            const value = parseFloat(cleanedValue) || 0;
            const result = value * multiplier;
            target.value = result.toLocaleString(undefined, {
                 minimumFractionDigits: precision,
                 maximumFractionDigits: precision
             });
        };
        calculator.addEventListener('input', calculateAndUpdate);
        if (calculator.value) calculateAndUpdate();
    });
}

/**
 * Calcula el número de cuotas y el monto por cuota basado en los parámetros del contrato.
 * @param {number} montoTotalContrato - El monto total del contrato.
 * @param {string} formaPago - El código de la forma de pago (ej. 'MENSUAL', 'TRIMESTRAL').
 * @param {number} periodoVigenciaMeses - La duración del contrato en meses.
 * @returns {object} Un objeto con { numeroCuotas, montoCuota }.
 */
function calcularDetallesCuotas(montoTotalContrato, formaPago, periodoVigenciaMeses) {
    let numeroCuotas = 0;
    let montoCuota = 0;

    const montoTotal = parseFloat(String(montoTotalContrato).replace(/[^\d,.-]/g, '').replace(',', '.')) || 0;
    const periodoMeses = parseInt(periodoVigenciaMeses) || 0;

    if (montoTotal <= 0) {
        return { numeroCuotas: 0, montoCuota: 0, montoTotalCalculado: montoTotal };
    }

    // Si la forma de pago es periódica, el periodo en meses debe ser positivo
    if (formaPago !== 'CONTADO' && periodoMeses <= 0) {
        return { numeroCuotas: 0, montoCuota: 0, montoTotalCalculado: montoTotal };
    }

    switch (formaPago) {
        case 'CONTADO':
            numeroCuotas = 1;
            montoCuota = montoTotal;
            break;
        case 'MENSUAL':
            numeroCuotas = periodoMeses;
            montoCuota = numeroCuotas > 0 ? montoTotal / numeroCuotas : 0;
            break;
        case 'TRIMESTRAL':
            numeroCuotas = Math.ceil(periodoMeses / 3);
            montoCuota = numeroCuotas > 0 ? montoTotal / numeroCuotas : 0;
            break;
        case 'SEMESTRAL':
            numeroCuotas = Math.ceil(periodoMeses / 6);
            montoCuota = numeroCuotas > 0 ? montoTotal / numeroCuotas : 0;
            break;
        case 'ANUAL':
            numeroCuotas = Math.ceil(periodoMeses / 12);
            montoCuota = numeroCuotas > 0 ? montoTotal / numeroCuotas : 0;
            break;
        default:
            // Si la forma de pago no es reconocida, no se puede calcular
            return { numeroCuotas: 0, montoCuota: 0, montoTotalCalculado: montoTotal };
    }
    
    return { 
        numeroCuotas: numeroCuotas > 0 ? numeroCuotas : 0, 
        montoCuota: parseFloat(montoCuota.toFixed(2)), // Redondear a 2 decimales
        montoTotalCalculado: montoTotal // Devolver el monto total parseado
    };
}

/**
 * Calcula la diferencia en días entre dos fechas.
 * @param {string} fechaDesdeStr - Fecha de inicio en formato DD/MM/YYYY.
 * @param {string} fechaHastaStr - Fecha de fin en formato DD/MM/YYYY.
 * @returns {number|null} Número de días o null si las fechas son inválidas.
 */
function calcularDiasEntreFechas(fechaDesdeStr, fechaHastaStr) {
    // Función para parsear DD/MM/YYYY a un objeto Date
    function parseDMY(dateString) {
        if (!dateString || typeof dateString !== 'string') return null;
        const parts = dateString.split('/');
        if (parts.length === 3) {
            const day = parseInt(parts[0], 10);
            const month = parseInt(parts[1], 10) - 1; // Meses en JS son 0-indexados
            const year = parseInt(parts[2], 10);
            if (!isNaN(day) && !isNaN(month) && !isNaN(year)) {
                const dateObj = new Date(year, month, day);
                // Verificar si el objeto Date es válido y corresponde a la entrada
                if (dateObj.getFullYear() === year && dateObj.getMonth() === month && dateObj.getDate() === day) {
                    return dateObj;
                }
            }
        }
        return null;
    }

    const fechaDesde = parseDMY(fechaDesdeStr);
    const fechaHasta = parseDMY(fechaHastaStr);

    if (fechaDesde && fechaHasta && fechaHasta >= fechaDesde) {
        const diffTime = Math.abs(fechaHasta - fechaDesde);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1; // +1 para incluir ambos días
        return diffDays;
    }
    return null; // O 0 si prefieres
}

/**
 * Inicializa los cálculos y pre-llenados en el formulario de Factura.
 */
// EN TU ARCHIVO scripts.js
// Asunciones:
// - jQuery ($) está disponible globalmente ANTES de que este script se ejecute.
// - Select2 está inicializado en los campos de contrato (id_contrato_individual, id_contrato_colectivo)
//   por django-select2 o similar ANTES de que DOMContentLoaded se dispare completamente.
// - Las funciones calcularDiasEntreFechas, showLoading, hideLoading, y el objeto AppConfig están definidos.
// - La variable global window.URL_GET_CONTRATO_MONTO_CUOTA se define en tu plantilla HTML ANTES de este script.

function initFacturaFormCalculations() {
    const facturaFormElement = document.getElementById('facturaForm'); 
    const isEditingMode = facturaFormElement ? (facturaFormElement.dataset.isEditing === 'true') : false;

    const vigenciaDesdeInput = document.getElementById('id_vigencia_recibo_desde');
    const vigenciaHastaInput = document.getElementById('id_vigencia_recibo_hasta');
    const diasPeriodoInput = document.getElementById('id_dias_periodo_cobro');
    
    const contratoIndividualSelect = document.getElementById('id_contrato_individual');
    const contratoColectivoSelect = document.getElementById('id_contrato_colectivo');
    const montoInput = document.getElementById('id_monto');
    const saldoContratoDisplay = document.getElementById('id_saldo_contrato_display'); 
    
    const urlApiContratoMonto = window.URL_GET_CONTRATO_MONTO_CUOTA;

    if (!urlApiContratoMonto) {
        console.error("FacturaFormCalculations: URL_GET_CONTRATO_MONTO_CUOTA no está definida.");
    }
    if (!contratoIndividualSelect || !contratoColectivoSelect || !montoInput || !saldoContratoDisplay) {
        // No es un error crítico si algunos elementos no están, la función podría ser llamada en otras páginas.
        // Pero si estamos en factura_form.html y faltan, es un problema de la plantilla.
        // console.warn("FacturaFormCalculations: Uno o más elementos del DOM (contratos, monto, saldo) no fueron encontrados.");
    }


    function actualizarDiasPeriodo() {
        if (!vigenciaDesdeInput || !vigenciaHastaInput || !diasPeriodoInput) return;
        const dias = calcularDiasEntreFechas(vigenciaDesdeInput.value, vigenciaHastaInput.value);
        diasPeriodoInput.value = dias !== null ? dias : '';
    }

    async function fetchContratoData(contratoId, tipoContrato, esCambioHechoPorUsuario) {
        if (!contratoId || !tipoContrato || !urlApiContratoMonto) {
            if (montoInput) montoInput.value = '';
            if (saldoContratoDisplay) saldoContratoDisplay.textContent = '0.00';
            return;
        }
        if (!montoInput && !saldoContratoDisplay) return;

        if (typeof showLoading === 'function') showLoading();

        try {
            const queryParams = new URLSearchParams({
                tipo_contrato: tipoContrato,
                contrato_id: contratoId
            });
            const response = await fetch(`${urlApiContratoMonto}?${queryParams.toString()}`);
            
            if (!response.ok) {
                let errorMsg = `Error ${response.status}: ${response.statusText}`;
                try { const errData = await response.json(); errorMsg = errData.error || errorMsg; } catch (e) {}
                throw new Error(errorMsg);
            }

            const data = await response.json();
            const decimales = (typeof AppConfig !== 'undefined' && AppConfig.decimales) ? AppConfig.decimales : 2;

            if (montoInput) {
                if (data.monto_factura_sugerido !== undefined && data.monto_factura_sugerido !== null) {
                    montoInput.value = parseFloat(data.monto_factura_sugerido).toFixed(decimales);
                } else {
                    montoInput.value = '';
                }
            }

            if (saldoContratoDisplay) {
                if (data.saldo_total_contrato_pendiente !== undefined && data.saldo_total_contrato_pendiente !== null) {
                    saldoContratoDisplay.textContent = parseFloat(data.saldo_total_contrato_pendiente).toFixed(decimales);
                } else {
                    saldoContratoDisplay.textContent = '0.00';
                }
            }
            if(data.error) console.error('API devolvió un error al obtener datos del contrato:', data.error);

        } catch (error) {
            console.error('Fallo al obtener datos del contrato:', error.message);
            if (montoInput) montoInput.value = ''; 
            if (saldoContratoDisplay) saldoContratoDisplay.textContent = '0.00';
        } finally {
            if (typeof hideLoading === 'function') hideLoading();
        }
    }

    if (vigenciaDesdeInput) vigenciaDesdeInput.addEventListener('change', actualizarDiasPeriodo);
    if (vigenciaHastaInput) vigenciaHastaInput.addEventListener('change', actualizarDiasPeriodo);
    
    if (contratoIndividualSelect && contratoColectivoSelect) {
        if (typeof $ === 'function') { 
            $(contratoIndividualSelect).on('select2:select select2:clear', function (e) {
                const value = $(this).val(); 
                if (value) {
                    if ($(contratoColectivoSelect).val()) { 
                        if ($(contratoColectivoSelect).data('select2')) {
                            $(contratoColectivoSelect).val(null).trigger('change.select2').trigger('change');
                        } else { 
                             contratoColectivoSelect.value = ''; 
                        }
                    }
                    fetchContratoData(value, 'individual', true);
                } else if (!$(contratoColectivoSelect).val()) { 
                    if (montoInput) montoInput.value = '';
                    if (saldoContratoDisplay) saldoContratoDisplay.textContent = '0.00';
                }
            });

            $(contratoColectivoSelect).on('select2:select select2:clear', function (e) {
                const value = $(this).val();
                if (value) {
                    if ($(contratoIndividualSelect).val()) {
                        if ($(contratoIndividualSelect).data('select2')) {
                            $(contratoIndividualSelect).val(null).trigger('change.select2').trigger('change');
                        } else {
                            contratoIndividualSelect.value = ''; 
                        }
                    }
                    fetchContratoData(value, 'colectivo', true);
                } else if (!$(contratoIndividualSelect).val()) {
                    if (montoInput) montoInput.value = '';
                    if (saldoContratoDisplay) saldoContratoDisplay.textContent = '0.00';
                }
            });
        } else { 
            console.error("jQuery no está disponible; los listeners de Select2 para cálculo de monto en factura pueden no funcionar.");
            // Considerar añadir listeners nativos como fallback si jQuery es opcional
        }
    }

    actualizarDiasPeriodo();
    
    let contratoInicialId = null;
    let contratoInicialTipo = null;

    if (contratoIndividualSelect && contratoIndividualSelect.value) {
       contratoInicialId = contratoIndividualSelect.value;
       contratoInicialTipo = 'individual';
    } else if (contratoColectivoSelect && contratoColectivoSelect.value) {
       contratoInicialId = contratoColectivoSelect.value;
       contratoInicialTipo = 'colectivo';
    }

    if (contratoInicialId) {
        fetchContratoData(contratoInicialId, contratoInicialTipo, false);
    } else {
        if (montoInput && !montoInput.value && saldoContratoDisplay) {
             if (!isEditingMode || (isEditingMode && saldoContratoDisplay.textContent.trim() === '' )) {
                saldoContratoDisplay.textContent = '0.00';
             }
        } else if (montoInput && montoInput.value && saldoContratoDisplay && !isEditingMode){
             saldoContratoDisplay.textContent = montoInput.value;
        }
    }
    console.log("Factura form calculations initialized (monto y saldo contrato).");
}

/**
 * Inicializa los cálculos dinámicos de cuotas en los formularios de contrato.
 */
function initContratoCuotasCalculator() {
    // IDs de los campos en el formulario de Contrato (Individual o Colectivo)
    // Asegúrate que estos IDs coincidan con los generados por Django o los que asignes.
    const montoTotalInput = document.getElementById('id_monto_total'); // Campo donde se ingresa/calcula el monto total del contrato
    const formaPagoSelect = document.getElementById('id_forma_pago');
    const periodoInput = document.getElementById('id_periodo_vigencia_meses');
    
    // IDs de los campos (readonly) donde se mostrarán los resultados
    const cantidadCuotasDisplay = document.getElementById('id_cantidad_cuotas_display'); // Necesitas añadir este campo al form
    const montoCuotaDisplay = document.getElementById('id_monto_cuota_display');       // Necesitas añadir este campo al form

    // Si alguno de los elementos cruciales no existe, no hacer nada.
    if (!montoTotalInput || !formaPagoSelect || !periodoInput || !cantidadCuotasDisplay || !montoCuotaDisplay) {
        // console.warn("Calculadora de cuotas: Faltan elementos del DOM. IDs esperados: id_monto_total, id_forma_pago, id_periodo_vigencia_meses, id_cantidad_cuotas_display, id_monto_cuota_display");
        return;
    }

    function actualizarCamposCalculados() {
        const montoTotalValue = montoTotalInput.value;
        const formaPagoValue = formaPagoSelect.value;
        const periodoMesesValue = periodoInput.value;

        const resultado = calcularDetallesCuotas(montoTotalValue, formaPagoValue, periodoMesesValue);

        cantidadCuotasDisplay.value = resultado.numeroCuotas;
        
        // Formatear para mostrar con símbolo de moneda y separadores locales
        // Asumiendo que AppConfig.decimales está disponible o usa un default
        const decimales = (typeof AppConfig !== 'undefined' && AppConfig.decimales) ? AppConfig.decimales : 2;
        montoCuotaDisplay.value = resultado.montoCuota > 0 
            ? `$${resultado.montoCuota.toLocaleString(undefined, { minimumFractionDigits: decimales, maximumFractionDigits: decimales })}` 
            : '$0.00';
    }

    // Añadir event listeners a los campos que disparan el cálculo
    montoTotalInput.addEventListener('input', actualizarCamposCalculados);
    formaPagoSelect.addEventListener('change', actualizarCamposCalculados);
    periodoInput.addEventListener('input', actualizarCamposCalculados);

    // Calcular al cargar la página si los campos ya tienen valores (modo edición)
    actualizarCamposCalculados();
    
    console.log("Calculadora de cuotas para contratos inicializada.");
}



/* ======================
    FUNCIONES UTILITARIAS
====================== */
function debounce(fn, delay = 300) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            fn.apply(this, args);
        }, delay);
    };
}


/* ======================
    SELECTS CON CHOICES.JS
====================== */
function initCustomSelects() {
    if (typeof Choices === 'undefined') return;
    const defaultChoicesOptions = {
        searchEnabled: true, shouldSort: false, itemSelectText: '', loadingText: 'Cargando...',
        noResultsText: 'No se encontraron resultados', noChoicesText: 'No hay más opciones',
        fuseOptions: { threshold: 0.3 },
        classNames: {
            containerOuter: 'choices', containerInner: 'choices__inner', input: 'choices__input',
            inputCloned: 'choices__input--cloned', list: 'choices__list', listItems: 'choices__list--items',
            listSingle: 'choices__list--single', listDropdown: 'choices__list--dropdown',
            item: 'choices__item', itemSelectable: 'choices__item--selectable',
            itemDisabled: 'choices__item--disabled', itemChoice: 'choices__item--choice',
            placeholder: 'choices__placeholder', group: 'choices__group',
            groupHeading: 'choices__heading', button: 'choices__button',
        }
    };
    document.querySelectorAll('select.select-field:not([multiple]):not(.choices__input)').forEach(select => {
        if (select.choicesInstance) return;
        try {
            const specificOptions = { ...defaultChoicesOptions };
            if (select.dataset.searchable === 'false') specificOptions.searchEnabled = false;
            select.choicesInstance = new Choices(select, specificOptions);
        } catch (error) { console.error("Error inicializando Choices.js en select simple:", select, error); }
    });
    document.querySelectorAll('select.select-field[multiple]:not(.choices__input)').forEach(select => {
        if (select.choicesInstance) return;
         try {
            const specificOptions = { ...defaultChoicesOptions, removeItemButton: true, classNames: { ...defaultChoicesOptions.classNames, listItems: 'choices__list--multiple', button: 'choices__button' } };
            if (select.dataset.searchable === 'false') specificOptions.searchEnabled = false;
            select.choicesInstance = new Choices(select, specificOptions);
         } catch (error) { console.error("Error inicializando Choices.js en select múltiple:", select, error); }
    });
}

/* ======================
    FUNCIONES DE CÁLCULO TARIFA
====================== */
function inicializarCalculosTarifa(opciones = {}) {
    const config = {
        decimales: AppConfig.decimales || 2,
        ids: { anual: 'id_monto_anual', semestral: 'id_monto_semestral', trimestral: 'id_monto_trimestral', mensual: 'id_monto_mensual' },
        locale: document.documentElement.lang || 'es-ES', ...opciones
    };
    const campos = { anual: document.getElementById(config.ids.anual), semestral: document.getElementById(config.ids.semestral), trimestral: document.getElementById(config.ids.trimestral), mensual: document.getElementById(config.ids.mensual) };
    if (Object.values(campos).some(campo => !campo)) return;
    const formatearNumero = (valor) => { const numero = parseFloat(valor) || 0; return numero.toLocaleString(config.locale, { minimumFractionDigits: config.decimales, maximumFractionDigits: config.decimales }); };
    const limpiarNumero = (valor) => { return String(valor).replace(/[.'\s]/g, '').replace(',', '.'); };
    const calcularMontos = (valorAnual) => { const anual = parseFloat(valorAnual) || 0; if (isNaN(anual)) return { semestral: 0, trimestral: 0, mensual: 0 }; return { semestral: anual / 2, trimestral: anual / 4, mensual: anual / 12 }; };
    const actualizarCampos = () => {
        const valorLimpio = limpiarNumero(campos.anual.value);
        if (isNaN(parseFloat(valorLimpio))) { campos.semestral.value = formatearNumero(0); campos.trimestral.value = formatearNumero(0); campos.mensual.value = formatearNumero(0); return; }
        const montos = calcularMontos(valorLimpio);
        campos.semestral.value = formatearNumero(montos.semestral); campos.trimestral.value = formatearNumero(montos.trimestral); campos.mensual.value = formatearNumero(montos.mensual);
    };
    campos.anual.addEventListener('input', actualizarCampos);
    campos.anual.addEventListener('blur', () => { const valorLimpio = limpiarNumero(campos.anual.value); if (!isNaN(parseFloat(valorLimpio))) campos.anual.value = formatearNumero(valorLimpio); });
    if (campos.anual.value) { actualizarCampos(); const valorLimpioInicial = limpiarNumero(campos.anual.value); if (!isNaN(parseFloat(valorLimpioInicial))) campos.anual.value = formatearNumero(valorLimpioInicial); }
}

/**
 * Función para aplicar un retardo a la ejecución de otra función.
 * Útil para eventos como 'input' o 'resize'.
 */
function debounce(fn, delay = 300) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            fn.apply(this, args);
        }, delay);
    };
}


/**
 * Inicializa la calculadora de vista previa para el monto total del contrato.
 * Escucha cambios en la tarifa y el período para actualizar el monto en tiempo real.
 */
function initContratoMontoCalculator() {
    // Usamos selectores de jQuery para ser compatibles con Select2
    const $tarifaSelect = $('#id_tarifa_aplicada');
    const $periodoInput = $('#id_periodo_vigencia_meses');
    const $montoDisplay = $('#monto-total-display');

    // Si alguno de los elementos no existe en la página, no hacemos nada.
    if ($tarifaSelect.length === 0 || $periodoInput.length === 0 || $montoDisplay.length === 0) {
        return; 
    }

    const actualizarMonto = () => {
        // Encontramos la opción seleccionada dentro del select original
        const selectedOption = $tarifaSelect.find('option:selected');
        const periodoMeses = parseInt($periodoInput.val(), 10);

        // Leemos el atributo data-monto-anual de la opción seleccionada.
        // Gracias al widget personalizado, este atributo ahora existe.
        const montoAnualStr = selectedOption.data('monto-anual');

        // Validamos que tengamos los datos necesarios
        if (!montoAnualStr || isNaN(periodoMeses) || periodoMeses <= 0) {
            $montoDisplay.text('$0.00'); // Valor por defecto si no se puede calcular
            return;
        }

        const montoAnual = parseFloat(montoAnualStr);
        
        if (!isNaN(montoAnual) && montoAnual > 0) {
            // Realizamos el cálculo
            const montoCalculado = (montoAnual / 12) * periodoMeses;
            
            // Actualizamos el texto del span, formateado como moneda.
            // 'es-VE' es para Venezuela, puedes usar 'en-US' o el locale que prefieras.
            $montoDisplay.text(
                `$${montoCalculado.toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
            );
        } else {
            $montoDisplay.text('$0.00');
        }
    };

    // --- Event Listeners ---
    // Usamos el evento 'change' de jQuery, que Select2 dispara correctamente en el select original.
    $tarifaSelect.on('change', actualizarMonto);
    
    // Para el campo de meses, usamos 'input' con un debounce para no calcular en cada tecla.
    $periodoInput.on('input', debounce(actualizarMonto, 300));

    // Ejecutar al cargar la página por si hay valores iniciales (modo edición).
    // Esperamos un poco para que Select2 termine de inicializarse completamente.
    setTimeout(actualizarMonto, 200);
    
    console.log("Calculadora de monto para contratos (con Select2 y data-attributes) inicializada.");
}
// ==================================================
// === INICIALIZACIÓN DE INTERACCIONES DE TABLA (NO DATATABLES) ===
// ==================================================
function initTableInteractions() {
    document.body.addEventListener('click', function(e) {
        const sortHeaderLink = e.target.closest('.sort-header a');
        if (sortHeaderLink && sortHeaderLink.hasAttribute('href')) {
            e.preventDefault(); showLoading(); window.location.href = sortHeaderLink.href; return;
        }
        const pageLink = e.target.closest('.django-pagination a');
        if (pageLink && pageLink.hasAttribute('href')) {
            e.preventDefault(); showLoading(); window.location.href = pageLink.href; return;
        }
    });
    const mainSearchForm = document.querySelector('form.search-form:not(.graph-search-form)');
    if (mainSearchForm) {
        mainSearchForm.addEventListener('submit', e => {
            e.preventDefault();
            const searchInput = mainSearchForm.querySelector('.search-input');
            if (!searchInput) return;
            const url = new URL(window.location.href);
            url.searchParams.set('search', searchInput.value); url.searchParams.set('page', '1');
            showLoading(); window.location.href = url.toString();
        });
    }
}

/* =======================================
    INICIALIZACIÓN PRINCIPAL (DOMContentLoaded)
======================================= */
document.addEventListener("DOMContentLoaded", () => {

    document.body.addEventListener('click', function(event) {
        const fileLink = event.target.closest('a.file-popup-trigger');
        if (fileLink) {
            event.preventDefault(); // Prevenimos la navegación normal
            const url = fileLink.href;
            const title = fileLink.dataset.popupTitle || 'Visor de Documento';
            openFilePopup(url, title);
        }
    });

    try { initTabs(); } catch (e) { console.error("Error en initTabs:", e); }
    try { carouselInstance = initCarousel(); } catch (e) { console.error("Error en initCarousel:", e); }
    try { initFormBehaviors(); } catch (e) { console.error("Error en initFormBehaviors:", e); }
    try { initFileUploads(); } catch (e) { console.error("ERROR FATAL llamando o dentro de initFileUploads:", e); }
    try { initCalculations(); } catch (e) { console.error("Error en initCalculations:", e); }
    try { initCustomSelects(); } catch (e) { console.error("Error en initCustomSelects:", e); }
    try { handleFormConfirmations(); } catch (e) { console.error("Error en handleFormConfirmations:", e); }
    try { initGraphSearch(); } catch (e) { console.error("Error en initGraphSearch:", e); }
    try { initExportPopup(); } catch (e) { console.error("Error en initExportPopup:", e); }
    try { if (document.getElementById('id_monto_anual')) inicializarCalculosTarifa(); } catch (e) { console.error("Error en inicializarCalculosTarifa:", e); }
    try { initTableInteractions(); } catch (e) { console.error("Error en initTableInteractions:", e); }
    try { if (document.getElementById('id_monto_total') && document.getElementById('id_forma_pago')) {initContratoCuotasCalculator();}} catch (e) { console.error("Error en initContratoCuotasCalculator:", e); }
    try { if (document.getElementById('id_contrato_individual') || document.getElementById('id_contrato_colectivo')) {initFacturaFormCalculations();}} catch (e) {console.error("Error en initFacturaFormCalculations:", e);}
    try { initFilePopups(); } catch (e) { console.error("Error en initFilePopups:", e); }
    try { initContratoMontoCalculator(); } catch (e) { console.error("Error en initContratoMontoCalculator:", e); }

});



