// Función para abrir pestañas principales
function openTab(tabName) {
  // Ocultar todas las pestañas
  var tabPanes = document.getElementsByClassName("tab_pane");
  for (var i = 0; i < tabPanes.length; i++) {
    tabPanes[i].classList.remove("active");
  }

  // Desactivar todas las pestañas
  var tabs = document.getElementsByClassName("tab");
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].classList.remove("active");
  }

  // Activar la pestaña seleccionada
  document.getElementById(tabName).classList.add("active");

  // Activar el botón de la pestaña
  var activeTabButton = document.querySelector(
    ".tab[onclick=\"openTab('" + tabName + "')\"]"
  );
  if (activeTabButton) {
    activeTabButton.classList.add("active");
  }

  // Actualizar la URL con el parámetro de la pestaña
  var currentUrl = new URL(window.location.href);
  currentUrl.searchParams.set("tab", tabName);
  window.history.replaceState({}, "", currentUrl.toString());
}

// Función para moverse en el carrusel
function moveCarousel(direction) {
  var carousel = document.getElementById("charts_carousel");
  var items = carousel.getElementsByClassName("carousel_item");
  var activeIndex = -1;

  // Encontrar el índice del elemento activo
  for (var i = 0; i < items.length; i++) {
    if (items[i].classList.contains("active")) {
      activeIndex = i;
      items[i].classList.remove("active");
      break;
    }
  }

  // Calcular nuevo índice
  var newIndex = activeIndex + direction;
  if (newIndex < 0) {
    newIndex = items.length - 1;
  } else if (newIndex >= items.length) {
    newIndex = 0;
  }

  // Activar nuevo elemento
  items[newIndex].classList.add("active");

  // Actualizar indicadores
  updateIndicators(newIndex);
}

// Función para ir a una gráfica específica
function goToChart(index) {
  var carousel = document.getElementById("charts_carousel");
  var items = carousel.getElementsByClassName("carousel_item");

  // Desactivar todos los elementos
  for (var i = 0; i < items.length; i++) {
    items[i].classList.remove("active");
  }

  // Activar el elemento seleccionado
  items[index].classList.add("active");

  // Actualizar indicadores
  updateIndicators(index);
}

// Función para actualizar los indicadores
function updateIndicators(activeIndex) {
  var indicators = document.getElementsByClassName("chart_indicator");

  for (var i = 0; i < indicators.length; i++) {
    indicators[i].classList.remove("active");
  }

  indicators[activeIndex].classList.add("active");
}

// Función para filtrar modelos
function filterModels() {
  var input = document.getElementById("model_search");
  var filter = input.value.toLowerCase();
  var models = document.getElementsByClassName("model_card");

  for (var i = 0; i < models.length; i++) {
    var modelData = models[i].getAttribute("data-name").toLowerCase();
    if (modelData.indexOf(filter) > -1) {
      models[i].style.display = "";
    } else {
      models[i].style.display = "none";
    }
  }
}

// Función para filtrar gráficas
function filterCharts() {
  var input = document.getElementById("chart_search");
  var filter = input.value.toLowerCase();
  var chartItems = document.getElementsByClassName("chart_item");
  var carouselItems = document.getElementsByClassName("carousel_item");

  // Filtrar en la lista de gráficas
  for (var i = 0; i < chartItems.length; i++) {
    var chartData = chartItems[i].getAttribute("data-name");
    if (chartData.indexOf(filter) > -1) {
      chartItems[i].style.display = "";
    } else {
      chartItems[i].style.display = "none";
    }
  }

  // Filtrar en el carrusel
  var foundMatch = false;
  for (var i = 0; i < carouselItems.length; i++) {
    var carouselData = carouselItems[i].getAttribute("data-name");
    if (carouselData.indexOf(filter) > -1) {
      carouselItems[i].style.display = "";
      // Activar la primera gráfica que coincida con el filtro
      if (filter !== "" && !foundMatch) {
        goToChart(i);
        foundMatch = true;
      }
    } else {
      carouselItems[i].style.display = "none";
    }
  }
}

// Función para redimensionar las gráficas cuando cambia el tamaño de la ventana
window.addEventListener("resize", function () {
  var chartDivs = document.querySelectorAll(".plotly_chart");
  for (var i = 0; i < chartDivs.length; i++) {
    if (window.Plotly) {
      window.Plotly.Plots.resize(chartDivs[i]);
    }
  }
});

// Inicializar la página cuando se carga
document.addEventListener("DOMContentLoaded", function () {
  // Obtener parámetros de la URL
  var urlParams = new URLSearchParams(window.location.search);
  var tab = urlParams.get("tab");

  // Activar la pestaña correspondiente
  if (tab) {
    openTab(tab);
  }
});
