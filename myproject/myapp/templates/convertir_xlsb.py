from pyxlsb import open_workbook
import csv
import os
import time
from tqdm import tqdm  # Para barra de progreso (opcional: pip install tqdm)


def convertir_xlsb_ultrafast(archivo_xlsb, dir_salida, batch_size=100000):
    """Conversión de XLSB a CSV con optimizaciones extremas"""

    os.makedirs(dir_salida, exist_ok=True)

    # Lector binario de alta velocidad
    with open_workbook(archivo_xlsb) as wb:
        for sheet_name in wb.sheets:
            start_time = time.time()

            with wb.get_sheet(sheet_name) as sheet:
                # Generar CSV
                nombre_csv = f"{dir_salida}/{sheet_name}.csv"
                with open(nombre_csv, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)

                    batch = []
                    for i, row in enumerate(tqdm(sheet.rows(), desc=f"Sheet: {sheet_name}")):
                        if i == 0:
                            headers = [item.v for item in row]
                            writer.writerow(headers)
                            continue

                        batch.append([item.v for item in row])

                        # Escritura por bloques (reduce I/O)
                        if len(batch) >= batch_size:
                            writer.writerows(batch)
                            batch = []

                    # Último lote
                    if batch:
                        writer.writerows(batch)

            print(f"\n[{sheet_name}] Tiempo: {time.time() - start_time:.2f}s")


# USO ================================================
convertir_xlsb_ultrafast(
    archivo_xlsb="conamed.xlsb",
    dir_salida="csv_resultado",
    batch_size=50000  # Ajustar según RAM disponible
)
