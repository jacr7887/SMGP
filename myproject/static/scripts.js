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
        .normalize("NFD") // Separa caracteres base de diacríticos
        .replace(/[\u0300-\u036f]/g, ""); // Elimina los diacríticos
}

// Debounce (Función de Utilidad)
function debounce(fn, delay = 300) {
    let timeoutId;
    return function(...args) { clearTimeout(timeoutId); timeoutId = setTimeout(() => { fn.apply(this, args); }, delay); };
}

// Funciones Loading
function showLoading(){ const l=document.getElementById("loadingIndicator"); if(l)l.style.display="flex"; }
function hideLoading(){ const l=document.getElementById("loadingIndicator"); if(l)l.style.display="none"; }

// Gestión de pestañas
function initTabs() {
    const tabButtons = document.querySelectorAll(".tab-button");
    if (!tabButtons.length) return;
    console.log("[UI] Inicializando Tabs..."); // Añadido log
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
    console.log("[UI] Tabs inicializados."); // Añadido log
}

// Búsqueda en gráficas
let carouselInstance = null; // Definir ANTES de usarla
function initGraphSearch() {
    console.log("[GraphSearch] Inicializando...");
    const searchInput = document.querySelector('.search-form input[name="graph_search"]');
    const carouselContainer = document.querySelector(".graphs-carousel-container");
    const carouselInner = carouselContainer?.querySelector(".carousel-inner"); // Optional chaining

    if (!searchInput || !carouselInner) {
        console.warn("[GraphSearch] Input de búsqueda o contenedor de carrusel no encontrados.");
        return;
    }
    console.log("[GraphSearch] Elementos OK. Añadiendo listener con debounce...");

    searchInput.addEventListener("input", debounce(function(e) {
        const normalizedSearchTerm = normalizeText(sanitizeHTML(e.target.value).trim());
        console.log(`[GraphSearch] Buscando: "${normalizedSearchTerm}"`);

        const allOriginalItems = Array.from(carouselInner.querySelectorAll(".carousel-item"));
        if (!allOriginalItems.length) return;

        let itemsShown = 0;
        let firstVisibleIndex = -1;

        allOriginalItems.forEach((item, index) => {
            const titleElement = item.querySelector(".graph-title");
            const normalizedTitle = normalizeText(titleElement ? titleElement.textContent.trim() : '');
            const shouldShow = normalizedTitle.includes(normalizedSearchTerm);

            // Usar una clase para ocultar en lugar de display:none directamente
            // Esto permite animaciones CSS y facilita la lógica del carrusel
            item.classList.toggle('search-hidden', !shouldShow);
            item.classList.remove('active'); // Desactivar todos primero

            if (shouldShow) {
                itemsShown++;
                if (firstVisibleIndex === -1) {
                    firstVisibleIndex = index; // Guardar índice original
                }
            }
        });

        // Reactivar el primer elemento visible
        if (firstVisibleIndex !== -1) {
             allOriginalItems[firstVisibleIndex].classList.add('active');
        }

        console.log(`[GraphSearch] Filtrado completo. Items visibles: ${itemsShown}`);

        // Actualizar la UI del carrusel (botones/indicadores) usando su método
        if (carouselInstance && typeof carouselInstance.updateVisibleItems === 'function') {
            console.log("[GraphSearch] Llamando a carouselInstance.updateVisibleItems() para refrescar UI...");
            try {
                carouselInstance.updateVisibleItems(); // Llama a la función del carrusel
                // Opcional: Redimensionar Plotly del slide que quedó activo después de la actualización
                setTimeout(() => {
                    const activeItemAfterUpdate = carouselInner.querySelector('.carousel-item.active');
                    if(activeItemAfterUpdate) triggerPlotlyResize(activeItemAfterUpdate);
                }, 100); // Pequeño delay
            } catch (error) {
                console.error("[GraphSearch] ERROR al llamar a updateVisibleItems:", error);
            }
        } else if(itemsShown > 0 || normalizedSearchTerm === '') {
            console.warn("[GraphSearch] Instancia carrusel o updateVisibleItems no disponible.");
        }

    }, 300)); // Fin debounce

    console.log("[GraphSearch] Listener añadido.");
}

// Popups Exportar/Importar
function initExportPopup() {
    // console.log("[Popup Final] Buscando .export-menu...");
    const menuItems = document.querySelectorAll('.nav_item.export-menu');

    if (!menuItems.length) { return; }

    menuItems.forEach(menuItem => {
        const trigger = menuItem.querySelector('a.export-trigger');
        const popup = menuItem.querySelector('ul.submenu.export-options');
        const menuItemId = menuItem.id || 'menu-item-no-id';

        if (!trigger || !popup) {
            // console.warn(`[Popup Final] Faltan trigger/popup para ${menuItemId}.`);
            return;
        }

        let closeTimer = null;
        const CLOSE_DELAY = 1500; // Delay para cerrar

        // --- Función para ABRIR este popup ---
        const openPopup = () => {
            // console.log(`[Popup Final ${menuItemId}] openPopup`);
            clearTimeout(closeTimer); // Cancelar cierre pendiente

            // Cerrar OTROS popups
            document.querySelectorAll('.export-menu .submenu.export-options.active').forEach(otherPopup => {
                if (otherPopup !== popup) {
                    const otherParent = otherPopup.closest('.export-menu');
                    const otherTrigger = otherParent ? otherParent.querySelector('.export-trigger') : null;
                    otherPopup.classList.remove('active'); // Ocultar vía CSS
                    if (otherTrigger) otherTrigger.classList.remove('active');
                }
            });

            // Calcular posición SOLO si es necesario (ej. ajuste vertical)
            // Primero mostramos con clases y dejamos que CSS posicione por defecto
            popup.classList.add('active');
            trigger.classList.add('active');

            // Ajuste vertical (opcional, si el CSS base no es suficiente)
            // Este cálculo es más propenso a errores, usar con cautela
            requestAnimationFrame(() => {
                const popupRect = popup.getBoundingClientRect();
                const menuItemRect = menuItem.getBoundingClientRect();
                const viewportHeight = window.innerHeight;

                 // Si se sale por abajo, intentar subirlo
                 if (menuItemRect.top + popupRect.height > viewportHeight - 10) {
                    let newTop = viewportHeight - popupRect.height - 10; // Pegar abajo
                    // Pero no subir más arriba que el top del item del menú
                    newTop = Math.min(menuItemRect.top, Math.max(10, newTop));
                    // Aplicar solo si es diferente a la posición por defecto (evitar style innecesario)
                    // Convertimos a position fixed para cálculo relativo a viewport
                    popup.style.position = 'fixed';
                    popup.style.top = `${newTop}px`;
                    // Aseguramos que left/right se mantengan según CSS (no los tocamos aquí)
                    popup.style.left = ''; // Dejar que CSS maneje left/right
                    popup.style.right = '';
                 } else {
                    // Si cabe, quitamos estilos inline por si acaso
                    popup.style.position = '';
                    popup.style.top = '';
                 }
            });


            startCloseTimer(); // Iniciar timer de auto-cierre
        };

        // --- Función para CERRAR este popup ---
        const closePopup = () => {
            // console.log(`[Popup Final ${menuItemId}] closePopup`);
            clearTimeout(closeTimer);
            popup.classList.remove('active');
            trigger.classList.remove('active');
            // Resetear estilos inline que podríamos haber añadido
            popup.style.position = '';
            popup.style.top = '';
            popup.style.left = '';
            popup.style.right = '';
        };

        // --- Función para INICIAR el timer de cierre ---
        const startCloseTimer = () => {
            clearTimeout(closeTimer);
            if (popup.classList.contains('active')) {
                // console.log(`[Popup Final ${menuItemId}] Iniciando timer cierre`);
                closeTimer = setTimeout(closePopup, CLOSE_DELAY);
            }
        };

        // --- Event Listeners ---
        trigger.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            if (popup.classList.contains('active')) {
                closePopup();
            } else {
                openPopup();
            }
        });

        // Mantener abierto con hover
        menuItem.addEventListener('mouseenter', () => { clearTimeout(closeTimer); });
        menuItem.addEventListener('mouseleave', startCloseTimer);

    }); // Fin forEach

    // --- Listener Global para Clic Fuera ---
    document.addEventListener('click', function(event) {
         document.querySelectorAll('.export-menu .submenu.export-options.active').forEach(activePopup => {
            const parentMenuItem = activePopup.closest('.export-menu');
            if (parentMenuItem && !parentMenuItem.contains(event.target)) {
                // console.log(`[Global Click Final] Cerrando popup ${parentMenuItem.id || ''}`);
                activePopup.classList.remove('active');
                const activeTrigger = parentMenuItem.querySelector('.export-trigger');
                if (activeTrigger) activeTrigger.classList.remove('active');
                // Resetear estilos por si acaso
                activePopup.style.position = ''; activePopup.style.top = '';
                activePopup.style.left = ''; activePopup.style.right = '';
            }
         });
    });

    // console.log("[Popup Final] Inicialización completada.");
}
// Comportamientos de Formularios
function initFormBehaviors() {
    console.log("[Form] Inicializando comportamientos...");
    document.addEventListener('input', e => { if (e.target.matches('[required]') && e.target.closest('.dark-group.error')) { if (e.target.value.trim()) { const g=e.target.closest('.dark-group'); g.classList.remove('error'); e.target.classList.remove('is-invalid'); g.querySelector('.error-messages')?.remove(); } } });
    document.addEventListener('submit', e => { const form = e.target.closest('form'); if (!form || form.noValidate || form.dataset.noValidate === 'true') return; let isValid = true; form.querySelectorAll('.dark-group.error').forEach(g => g.classList.remove('error')); form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid')); form.querySelectorAll('.error-messages').forEach(el => el.remove()); form.querySelectorAll('[required]').forEach(i => { let ok=true; if(i.type==='checkbox'&&!i.checked)ok=false; else if(i.matches('select')&&!i.value)ok=false; else if(!i.matches('select')&&i.type!=='checkbox'&&!i.value.trim())ok=false; if(!ok){isValid=false; const g=i.closest('.dark-group'); if(g){ g.classList.add('error'); let ec=g.querySelector('.error-messages'); if(!ec){ec=document.createElement('ul'); ec.className='error-messages'; i.parentNode.insertBefore(ec,i.nextSibling);} ec.innerHTML='<li>Obligatorio.</li>';} else i.classList.add('is-invalid');}}); if (!isValid) { e.preventDefault(); alert('Complete los campos requeridos.'); form.querySelector('.error input, .error select, .error textarea, .is-invalid')?.focus(); } else { showLoading(); } });
    console.log("[Form] Comportamientos inicializados.");
}

// Confirmaciones
function handleFormConfirmations() {
    console.log("[Confirm] Inicializando confirmaciones...");
    document.addEventListener('click', e => { const b=e.target.closest('button[data-confirm], a[data-confirm]'); if(!b)return; const m=(b.dataset.confirm==='true'||b.dataset.confirm==='')?'¿Está seguro?':b.dataset.confirm; if(!confirm(m))e.preventDefault(); else if(b.matches('button[type="submit"]'))showLoading(); });
    console.log("[Confirm] Confirmaciones inicializadas.");
}

// Carrusel de Gráficas
function initCarousel() {
    console.log("[Carousel] Inicializando...");
    const carouselContainer = document.querySelector(".graphs-carousel-container");
    if (!carouselContainer) { console.warn("[Carousel] Contenedor no encontrado."); return null; }
    const carouselInner = carouselContainer.querySelector(".carousel-inner");
    const indicatorsContainer = carouselContainer.querySelector(".carousel-indicators");
    const prevBtn = carouselContainer.querySelector(".carousel-control.carousel-prev");
    const nextBtn = carouselContainer.querySelector(".carousel-control.carousel-next");
    if (!carouselInner) { console.error("[Carousel] Inner no encontrado."); return null; }
    const originalItems = Array.from(carouselInner.querySelectorAll(".carousel-item"));
    if (originalItems.length === 0) { console.warn("[Carousel] No hay items."); return null; }
    let visibleItems = []; let currentVisibleIndex = -1; let indicators = [];

    function updateVisibleItemsList() {
        const previouslyActiveItem = (currentVisibleIndex >= 0 && currentVisibleIndex < visibleItems.length) ? visibleItems[currentVisibleIndex] : null;
        // Ahora filtramos por la clase añadida en la búsqueda Y por display (por si acaso)
        visibleItems = originalItems.filter(item => !item.classList.contains('search-hidden') && item.style.display !== 'none');
        console.log(`[Carousel] updateVisibleItemsList: ${visibleItems.length} items visibles.`);

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
        if (previouslyActiveItem && visibleItems.includes(previouslyActiveItem)) { nextIdx = visibleItems.indexOf(previouslyActiveItem); }
        nextIdx = Math.max(0, Math.min(nextIdx, visibleItems.length - 1));

        originalItems.forEach(i => i.classList.remove('active'));
        indicators.forEach(ind => ind.classList.remove('active'));
        showSlide(nextIdx, true); // Forzar la muestra inicial o después del filtro
    }

    function showSlide(targetVisibleIndex, forceUpdate = false) {
        if (visibleItems.length === 0 || targetVisibleIndex < 0 || targetVisibleIndex >= visibleItems.length) return;
        if (!forceUpdate && currentVisibleIndex === targetVisibleIndex) { triggerPlotlyResize(visibleItems[targetVisibleIndex]); return; } // Ya está activo, solo resize

        if (currentVisibleIndex >= 0 && currentVisibleIndex < visibleItems.length) { visibleItems[currentVisibleIndex]?.classList.remove("active"); indicators[currentVisibleIndex]?.classList.remove("active"); }
        const newItem = visibleItems[targetVisibleIndex]; if (!newItem) return;
        newItem.classList.add("active"); indicators[targetVisibleIndex]?.classList.add("active");
        currentVisibleIndex = targetVisibleIndex;
        triggerPlotlyResize(newItem);
    }

    function triggerPlotlyResize(activeItem) { /* ... tu código para redimensionar Plotly ... */ }
    function prevSlideHandler() { const ni = (currentVisibleIndex - 1 + visibleItems.length) % visibleItems.length; showSlide(ni); }
    function nextSlideHandler() { const ni = (currentVisibleIndex + 1) % visibleItems.length; showSlide(ni); }

    if (prevBtn) { prevBtn.removeEventListener("click", prevSlideHandler); prevBtn.addEventListener("click", prevSlideHandler); }
    if (nextBtn) { nextBtn.removeEventListener("click", nextSlideHandler); nextBtn.addEventListener("click", nextSlideHandler); }

    updateVisibleItemsList(); // Inicializar
    console.log("[Carousel] Inicializado OK.");
    return { updateVisibleItems: updateVisibleItemsList }; // Devolver la función pública
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

            if (event.target.files.length > 0) {
                display.textContent = Array.from(event.target.files).map(f => f.name).join(', ');
            } else {
                display.textContent = defaultText;
            }
        }
    });

    document.body.addEventListener('click', function(event) {
        if (event.target.matches('.file-button-trigger')) {
             const wrapper = event.target.closest('.custom-file-input-wrapper');
             const input = wrapper ? wrapper.querySelector('input[type="file"].custom-file-actual-input') : null;
             if (input) {
                 input.click();
             }
        }
    });
     // HTML Ejemplo:
     // <div class="custom-file-input-wrapper dark-group">
     //   <label class="dark-label">...</label>
     //   <div class="custom-file-input">
     //       <input type="file" class="custom-file-actual-input" id="..." name="..." style="opacity:0; position:absolute; z-index:-1;">
     //       <button type="button" class="file-button-trigger btn btn-secondary">...</button>
     //       <span class="selected-file-display" data-default-text="...">...</span>
     //   </div>
     // </div>
}

/* ======================
    CÁLCULOS (Implementación nativa)
====================== */
function initCalculations() {
    document.querySelectorAll('[data-calculate]').forEach(calculator => {
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
        if (calculator.value) calculateAndUpdate(); // Ejecutar al inicio si hay valor
    });
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
    SELECTS CON CHOICES.JS (ÚNICA DEFINICIÓN CORRECTA)
====================== */
function initCustomSelects() {
    if (typeof Choices === 'undefined') {
         console.warn("Choices.js no está definido. Saltando inicialización de selects.");
         return;
    }

    const defaultChoicesOptions = {
        searchEnabled: true,
        shouldSort: false,
        itemSelectText: '',
        loadingText: 'Cargando...',
        noResultsText: 'No se encontraron resultados',
        noChoicesText: 'No hay más opciones',
        fuseOptions: { threshold: 0.3 },
        classNames: {
            containerOuter: 'choices',
            containerInner: 'choices__inner',
            input: 'choices__input',
            inputCloned: 'choices__input--cloned',
            list: 'choices__list',
            listItems: 'choices__list--items',
            listSingle: 'choices__list--single',
            listDropdown: 'choices__list--dropdown',
            item: 'choices__item',
            itemSelectable: 'choices__item--selectable',
            itemDisabled: 'choices__item--disabled',
            itemChoice: 'choices__item--choice',
            placeholder: 'choices__placeholder',
            group: 'choices__group',
            groupHeading: 'choices__heading',
            button: 'choices__button',
        }
    };

    // Selects simples
    document.querySelectorAll('select.select-field:not([multiple]):not(.choices__input)').forEach(select => {
        if (select.choices) return; // Evitar reinicializar
        try {
            const specificOptions = { ...defaultChoicesOptions };
            if (select.dataset.searchable === 'false') {
                specificOptions.searchEnabled = false;
            }
            new Choices(select, specificOptions);
        } catch (error) {
             console.error("Error inicializando Choices.js en select simple:", select, error);
        }
    });

    // Selects múltiples
    document.querySelectorAll('select.select-field[multiple]:not(.choices__input)').forEach(select => {
        if (select.choices) return;
         try {
            const specificOptions = {
                ...defaultChoicesOptions,
                removeItemButton: true,
                classNames: {
                    ...defaultChoicesOptions.classNames,
                     listItems: 'choices__list--multiple',
                     button: 'choices__button',
                }
            };
             if (select.dataset.searchable === 'false') {
                specificOptions.searchEnabled = false;
            }
            new Choices(select, specificOptions);
         } catch (error) {
             console.error("Error inicializando Choices.js en select múltiple:", select, error);
         }
    });
}


/* ======================
    FUNCIONES DE CÁLCULO TARIFA (Versión final única)
====================== */
function inicializarCalculosTarifa(opciones = {}) {
    const config = {
        decimales: AppConfig.decimales || 2,
        ids: {
            anual: 'id_monto_anual',
            semestral: 'id_monto_semestral',
            trimestral: 'id_monto_trimestral',
            mensual: 'id_monto_mensual'
        },
        locale: document.documentElement.lang || 'es-ES',
        ...opciones
    };

    const campos = {
        anual: document.getElementById(config.ids.anual),
        semestral: document.getElementById(config.ids.semestral),
        trimestral: document.getElementById(config.ids.trimestral),
        mensual: document.getElementById(config.ids.mensual)
    };

    if (Object.values(campos).some(campo => !campo)) {
        // console.warn('Faltan campos para cálculo de tarifa.');
        return;
    }

    const formatearNumero = (valor) => {
        const numero = parseFloat(valor) || 0;
        return numero.toLocaleString(config.locale, {
            minimumFractionDigits: config.decimales,
            maximumFractionDigits: config.decimales
        });
    };

    const limpiarNumero = (valor) => {
        return String(valor).replace(/[.'\s]/g, '').replace(',', '.');
    };

    const calcularMontos = (valorAnual) => {
        const anual = parseFloat(valorAnual) || 0;
        if (isNaN(anual)) return { semestral: 0, trimestral: 0, mensual: 0 };
        return {
            semestral: anual / 2,
            trimestral: anual / 4, // Corregido
            mensual: anual / 12
        };
    };

    const actualizarCampos = () => {
        const valorLimpio = limpiarNumero(campos.anual.value);
        if (isNaN(parseFloat(valorLimpio))) {
             campos.semestral.value = formatearNumero(0);
             campos.trimestral.value = formatearNumero(0);
             campos.mensual.value = formatearNumero(0);
             return;
        }
        const montos = calcularMontos(valorLimpio);
        campos.semestral.value = formatearNumero(montos.semestral);
        campos.trimestral.value = formatearNumero(montos.trimestral);
        campos.mensual.value = formatearNumero(montos.mensual);
    };

    campos.anual.addEventListener('input', actualizarCampos);
    campos.anual.addEventListener('blur', () => {
        const valorLimpio = limpiarNumero(campos.anual.value);
        if (!isNaN(parseFloat(valorLimpio))) {
            campos.anual.value = formatearNumero(valorLimpio);
        }
    });

    if (campos.anual.value) {
         actualizarCampos();
         const valorLimpioInicial = limpiarNumero(campos.anual.value);
          if (!isNaN(parseFloat(valorLimpioInicial))) {
            campos.anual.value = formatearNumero(valorLimpioInicial);
          }
    }
}

// Funciones de loading
function showLoading() {
    const indicator = document.getElementById('loadingIndicator');
    if (indicator) indicator.style.display = 'flex';
}
function hideLoading() {
     const indicator = document.getElementById('loadingIndicator');
     if (indicator) indicator.style.display = 'none';
}

// ==================================================
// === INICIALIZACIÓN DE DATATABLES (AÑADIDA) ===
// ==================================================
function initTableInteractions() {
    console.log("[TableInteractions] Inicializando listeners para ordenación/paginación Django...");

    // Usar delegación de eventos en el body para manejar clics
    document.body.addEventListener('click', function(e) {

        // --- Manejo de Clic en Cabecera Ordenable ---
        const sortHeaderLink = e.target.closest('.sort-header a'); // Busca el ENLACE dentro del TH
        if (sortHeaderLink && sortHeaderLink.hasAttribute('href')) {
            console.log("[TableInteractions] Clic en cabecera ordenable.");
            e.preventDefault(); // Prevenir la navegación normal del enlace
            showLoading();      // Mostrar indicador de carga
            // Ir a la URL del enlace (que ya contiene los parámetros sort/order)
            window.location.href = sortHeaderLink.href;
            return; // Salir para no procesar también como enlace de paginación
        }

        // --- Manejo de Clic en Enlace de Paginación ---
        const pageLink = e.target.closest('.django-pagination a'); // Busca enlace DENTRO del contenedor de paginación
        if (pageLink && pageLink.hasAttribute('href')) {
            console.log("[TableInteractions] Clic en enlace de paginación.");
            e.preventDefault(); // Prevenir la navegación normal
            showLoading();      // Mostrar indicador de carga
            window.location.href = pageLink.href;
            return;
        }
    });

    // --- Búsqueda Principal (como la tenías) ---
    const mainSearchForm = document.querySelector('form.search-form:not(.graph-search-form)');
    if (mainSearchForm) {
        console.log("[TableInteractions] Añadiendo listener a búsqueda principal.");
        mainSearchForm.addEventListener('submit', e => {
            e.preventDefault();
            const searchInput = mainSearchForm.querySelector('.search-input');
            if (!searchInput) return;
            const url = new URL(window.location.href);
            url.searchParams.set('search', searchInput.value);
            url.searchParams.set('page', '1'); // Resetear a página 1
            showLoading();
            window.location.href = url.toString();
        });
    } else {
         console.log("[TableInteractions] No se encontró form de búsqueda principal.");
    }

    console.log("[TableInteractions] Listeners de tabla inicializados.");
}

/* =======================================
    INICIALIZACIÓN PRINCIPAL (DOMContentLoaded)
======================================= */
document.addEventListener("DOMContentLoaded", () => {
    console.log("DOM Cargado. Inicializando scripts...");   

    // 1. Inicializar UI y Componentes Básicos
    initTabs();
    carouselInstance = initCarousel(); // Guardar instancia para búsqueda
    initFormBehaviors();
    initFileUploads();
    initCalculations();
    initCustomSelects();
    handleFormConfirmations();
    initGraphSearch(); // Después de initCarousel
    initExportPopup();
    if (document.getElementById('id_monto_anual')) {
         inicializarCalculosTarifa();
    }

    // // 2. Inicializar DataTables (usando jQuery)
    // //    Asegurarse que jQuery esté cargado y listo
    // if (typeof jQuery !== 'undefined') {
    //     $(document).ready(function() { // Doble seguridad con jQuery ready
    //         console.log("[jQuery Ready] Inicializando DataTables...");
    //         inicializarDataTables('#tablaPagos', { "order": [[ 3, "desc" ]] });
    //         inicializarDataTables('#tablaFacturas', { "order": [[ 0, "desc" ]] });
    //         inicializarDataTables('#tablaContratosIndividuales', { "order": [[ 6, "desc" ]] });
    //         inicializarDataTables('#tablaContratosColectivos', { "order": [[ 6, "desc" ]] });
    //         inicializarDataTables('#tablaAfiliadosIndividuales', { "order": [[ 2, "asc" ]] });
    //         inicializarDataTables('#tablaAfiliadosColectivos', { "order": [[ 3, "asc" ]] });
    //         inicializarDataTables('#tablaIntermediarios', { "order": [[ 2, "asc" ]] });
    //         inicializarDataTables('#tablaReclamaciones', { "order": [[ 6, "desc" ]] });
    //         inicializarDataTables('#tablaTarifas', { "order": [[ 2, "asc" ]] });
    //     });
    // } else {
    //     console.error("jQuery no está definido al intentar inicializar DataTables.");
    // }

    // // 3. Lógica de interacción de tabla ANTIGUA (SI LA NECESITAS PARA ALGO MÁS QUE ORDEN/PAG)
    initTableInteractions(); // Comentada porque DataTables maneja orden/paginación

    // console.log("Scripts inicializados.");
}); // Fin DOMContentLoaded