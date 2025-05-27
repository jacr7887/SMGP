class TableManager {
  constructor() {
    this.table = document.getElementById("data-table");
    this.tbody = this.table.querySelector("tbody");
    this.pageSize = 25;
    this.currentPage = 1;
    this.allData = [];

    this.loadData();
    this.initEvents();
  }

  async loadData() {
    const response = await fetch("/usuarios/");
    this.allData = await response.json();
    this.renderTable();
  }

  renderTable() {
    this.tbody.innerHTML = "";

    const start = (this.currentPage - 1) * this.pageSize;
    const end = start + this.pageSize;

    this.allData.slice(start, end).forEach((item) => {
      const row = this.createRow(item.fields);
      this.tbody.appendChild(row);
    });

    this.updatePagination();
  }

  createRow(data) {
    const tr = document.createElement("tr");
    Object.values(data).forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value;
      tr.appendChild(td);
    });
    return tr;
  }

  sortTable(field, direction = "asc") {
    this.allData.sort((a, b) => {
      const aVal = a.fields[field];
      const bVal = b.fields[field];
      return direction === "asc"
        ? aVal.localeCompare(bVal, "es", { numeric: true })
        : bVal.localeCompare(aVal, "es", { numeric: true });
    });
    this.renderTable();
  }

  initEvents() {
    // Ordenación
    this.table.querySelectorAll("th").forEach((th) => {
      th.addEventListener("click", () => {
        const field = th.dataset.field;
        const direction = th.classList.contains("asc") ? "desc" : "asc";
        this.sortTable(field, direction);
        th.classList.toggle("asc", direction === "asc");
        th.classList.toggle("desc", direction === "desc");
      });
    });

    // Paginación
    document.getElementById("prev").addEventListener("click", () => {
      if (this.currentPage > 1) {
        this.currentPage--;
        this.renderTable();
      }
    });

    document.getElementById("next").addEventListener("click", () => {
      if (this.currentPage < this.totalPages) {
        this.currentPage++;
        this.renderTable();
      }
    });
  }

  get totalPages() {
    return Math.ceil(this.allData.length / this.pageSize);
  }

  updatePagination() {
    document.getElementById(
      "page-indicator"
    ).textContent = `Página ${this.currentPage} de ${this.totalPages}`;
  }
}

// Inicializar
new TableManager();
