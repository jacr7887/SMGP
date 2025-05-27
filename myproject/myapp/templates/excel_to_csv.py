import openpyxl
import csv
import os
import time


def sanitizar_nombre(nombre):
    """Limpia caracteres no válidos para nombres de archivo"""
    return "".join(c if c.isalnum() else "_" for c in nombre)


def procesar_excel_grande(archivo_excel, dir_salida):
    """Procesa archivos Excel grandes sin cargar todo en memoria"""

    start = time.time()
    os.makedirs(dir_salida, exist_ok=True)

    # Cargar libro en modo read-only optimizado
    wb = openpyxl.load_workbook(
        filename=archivo_excel,
        read_only=True,
        data_only=True,
        keep_links=False
    )

    for hoja in wb.worksheets:
        print(f"\nProcesando hoja: {hoja.title}")
        nombre_hoja = sanitizar_nombre(hoja.title)

        # Generar archivo CSV por hoja
        with open(f"{dir_salida}/{nombre_hoja}.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=',')

            # Iterar por filas directamente desde disco
            for fila in hoja.iter_rows(values_only=True):
                writer.writerow(fila)

    print(f"\nTiempo total: {time.time() - start:.2f} segundos")


# Uso
procesar_excel_grande(
    archivo_excel="tu_archivo_grande.xlsx",
    dir_salida="resultados_csv"
)
