# Instala: pip install pyxlsb
from pyxlsb import open_workbook


def listar_columnas_xlsb(ruta_archivo):
    with open_workbook(ruta_archivo) as wb:
        for sheet_name in wb.sheets:  # Itera todas las hojas
            with wb.get_sheet(sheet_name) as sheet:
                # Lee solo la primera fila (cabeceras)
                first_row = []
                for row in sheet.rows():
                    for item in row:
                        first_row.append(item.v)
                    break  # Solo procesa la primera fila
                print(f"\n📑 Hoja: '{sheet_name}'")
                print("Columnas:", first_row)


# Ejecutar (cambia la ruta)
listar_columnas_xlsb("conamed.xlsb")
