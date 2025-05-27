const loadTemplate = async (tab, subtab) => {
    try {
        const url = Config.SUBTABS[tab][subtab];
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Error HTTP! estado: ${response.status}`);
        const html = await response.text();
        document.getElementById('tabla-contenedor').innerHTML = html;
        initSorting();
        initSearch();
        ChartManager.renderAllCharts(Config.CHARTS);
    } catch (error) {
        console.error('Error cargando plantilla:', error);
        document.getElementById('tabla-contenedor').innerHTML = `
            <p>Error cargando datos: ${error.message}</p>
        `;
    }
};