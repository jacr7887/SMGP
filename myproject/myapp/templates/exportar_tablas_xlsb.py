import csv
from pyxlsb import open_workbook


def extraer_cabeceras_xlsb_a_csv(archivo_xlsb, archivo_csv_salida='campos.csv'):
    """
    Extrae nombres campos primera fila cada hoja .xlsb CSV

    Args:
        archivo_xlsb (str): Ruta archivo .xlsb
        archivo_csv_salida (str): Nombre archivo CSV salida

    Returns:
        dict: Estadísticas proceso

    """
    estadisticas = {'hojas_procesadas': [], 'campos_totales': 0}

    try:
        with open_workbook(archivo_xlsb) as wb:
            with open(archivo_csv_salida, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Nombre_Hoja', 'Campo'])  # Encabezado CSV

                for sheet_name in wb.sheets:
                    try:
                        sheet = wb.get_sheet(sheet_name)
                        primera_fila = next(sheet.rows())

                        campos = [
                            str(cell.v).strip() if cell.v is not None else '' for cell in primera_fila]

                        # Registrar stats
                        estadisticas['hojas_procesadas'].append({
                            'nombre': sheet_name,
                            'num_campos': len(campos)
                        })
                        estadisticas['campos_totales'] += len(campos)

                        # escribir CSV
                        for campo_idx, campo in enumerate(campos, start=1):
                            writer.writerow(
                                [sheet_name, f"{campo_idx}_{campo}"])

                    except StopIteration:
                        continue

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo .xlsb: '{archivo_xlsb}'")
    except Exception as e:
        print(f"Ocurrió un error general al procesar el archivo: {e}")

    return estadisticas


# Uso --------------
if __name__ == "__main__":
    stats = extraer_cabeceras_xlsb_a_csv(
        archivo_xlsb='conamed.xlsb',
        archivo_csv_salida='estructura_campos.csv'
    )

    print(f"✅ {len(stats['hojas_procesadas'])} hojas procesadas")
    print(f"📊 {stats['campos_totales']} campos extraídos")
