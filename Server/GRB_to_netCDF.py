
import cfgrib
import xarray as xr
import os

from config import DIR
def list_files_in_directory(directory_path, extension=None):
    return [os.path.join(dirpath, filename) for dirpath, _, filenames in os.walk(directory_path)
            for filename in filenames if not extension or filename.endswith(extension)]


def convertToNC():
    # Vstupní adresář s GRIB soubory
    input_directory = DIR
    output_directory = DIR

    # Výstupní adresář (adresář Data v aktuálním umístění skriptu)
    current_directory = os.path.dirname(os.path.abspath(__file__))


    # Vytvoření adresáře Data, pokud neexistuje
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
        print(f"Vytvořen adresář: {output_directory}")

    # Získání seznamu GRIB souborů
    files = list_files_in_directory(input_directory, '.grb')

    for file in files:
        try:
            # Načti GRIB soubor do xarray Dataset
            ds = cfgrib.open_dataset(file)
            
            # Vytvoř cestu pro výstupní soubor
            filename = os.path.basename(file)
            output_file = os.path.join(output_directory, filename.replace('.grb', '.nc'))
            
            # Ulož do NetCDF
            ds.to_netcdf(output_file)
        except Exception as e:
            print(f"Chyba při zpracování souboru {file}: {e}")
            return False

    return True