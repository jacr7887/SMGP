import pandas as pd
from tabulate import tabulate


def excel_a_tablas_texto(archivo_excel, archivo_salida, formato='simple'):
    """
    Exporta todas las hojas de un Excel a un archivo de texto con tablas formateadas

    Parámetros:
    archivo_excel (str): Ruta del archivo Excel de entrada
    archivo_salida (str): Ruta del archivo de texto de salida
    formato (str): Estilo de tabla (plain, simple, grid, fancy_grid, github, etc.)
    """

    # Leer todas las hojas del Excel
    xls = pd.ExcelFile(archivo_excel)

    with open(archivo_salida, 'w', encoding='utf-8') as f:
        for sheet_name in xls.sheet_names:
            # Leer cada hoja
            df = pd.read_excel(xls, sheet_name=sheet_name)

            # Eliminar filas completamente vacías
            df = df.dropna(how='all')

            # Convertir a tabla formateada
            tabla = tabulate(df, headers='keys',
                             tablefmt=formato, showindex=False)

            # Escribir en archivo
            f.write(f"\n{'='*60}\n")
            f.write(f"Hoja: {sheet_name}\n")
            f.write(f"{'='*60}\n\n")
            f.write(tabla)
            f.write("\n\n")


# Uso del programa
if __name__ == "__main__":
    # Configuración
    EXCEL_INPUT = 'datos.xlsx'
    TXT_OUTPUT = 'tablas.txt'

    # Tipos de formato disponibles:
    # 'plain', 'simple', 'grid', 'fancy_grid', 'pipe', 'orgtbl', 'jira', 'presto',
    # 'psql', 'rst', 'mediawiki', 'moinmoin', 'youtrack', 'html', 'latex', 'latex_raw',
    # 'latex_booktabs', 'textile', 'tsv'

    FORMATO = 'fancy_grid'  # Elige el estilo que prefieras

    # Ejecutar conversión
    excel_a_tablas_texto(EXCEL_INPUT, TXT_OUTPUT, FORMATO)
    print(f"Conversión completa! Archivo generado: {TXT_OUTPUT}")
