
import aiohttp
import asyncio
import io
import os
import boto3
from datetime import datetime, timedelta
from config import BUCKET_NAME, aws_secret_access_key, aws_access_key_id, REGION

# Konfigurace pro dva typy radarových dat
RADAR_TYPES = [
    {
        "name": "maxz",
        "base_url": "https://opendata.chmi.cz/meteorology/weather/radar/composite/maxz/hdf5/",
        "code": "PABV23",
        "s3_prefix": "radar/maxz"
    },
    {
        "name": "echotop",
        "base_url": "https://opendata.chmi.cz/meteorology/weather/radar/composite/echotop/hdf5/",
        "code": "PADV23",
        "s3_prefix": "radar/echotop"
    }
]

# Funkce pro nahrávání souborů do S3
def upload_file_to_s3(file_obj, bucket, object_name):
    """
    Nahraje soubor do S3 bucketu
    
    :param file_obj: Soubor v paměti (BytesIO objekt)
    :param bucket: Název S3 bucketu
    :param object_name: Cesta a název souboru v S3 bucketu
    :return: True pokud se upload povedl, jinak False
    """
    try:
        # Vytvoření S3 klienta
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=REGION
        )
        
        s3_client.put_object(Body=file_obj.getvalue(), Bucket=bucket, Key=object_name)
        return True
    except Exception as e:
        print(f"Chyba při nahrávání do S3: {e}")
        return False

async def fetch_data(URL):
    """
    Stahuje data z URL pomocí aiohttp.
    Vrátí data, pokud je stahování úspěšné, jinak None.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(URL) as response:
                if response.status == 200:
                    data = await response.read()
                    return data
                else:
                    print(f"Nepodařilo se stáhnout data z {URL}, status kód: {response.status}")
                    return None
    except Exception as e:
        print(f"Chyba při stahování dat z {URL}: {e}")
        return None

async def process_radar_file(timestamp, radar_type):
    """
    Zpracuje jeden radarový soubor - stáhne ho a nahraje do S3
    
    :param timestamp: Časová značka pro soubor (datetime objekt)
    :param radar_type: Slovník s konfigurací pro typ radarových dat
    :return: True pokud je zpracování úspěšné, jinak False
    """
    # Formátování času pro název souboru
    formatted_time = timestamp.strftime("%Y%m%d%H%M%S")
    
    # Sestavení názvu souboru a URL
    filename = f"T_{radar_type['code']}_C_OKPR_{formatted_time}.hdf"
    url = f"{radar_type['base_url']}{filename}"
    
    # Stažení dat
    data = await fetch_data(url)
    if data:
        # Příprava dat pro nahrání do S3
        file_in_memory = io.BytesIO(data)
        
        # Cesta v S3 - organizace podle data a typu radaru
        date_str = timestamp.strftime("%Y%m%d")
        s3_path = f"{radar_type['s3_prefix']}/{date_str}/{filename}"
        
        # Nahrání do S3
        success = upload_file_to_s3(file_in_memory, BUCKET_NAME, s3_path)
        if success:
            print(f"Nahráno {filename} do S3 bucketu {BUCKET_NAME}, cesta: {s3_path}")
            return True
        else:
            print(f"Nepodařilo se nahrát {filename} do S3")
            return False
    else:
        print(f"Nepodařilo se stáhnout {radar_type['name']} radar pro čas {formatted_time}")
        return False

async def process_time_period(date):
    """
    Zpracuje všechna radarová data pro zadané datum
    
    :param date: Datum pro zpracování (datetime objekt)
    """
    print(f"Zpracovávám data pro datum: {date.strftime('%Y-%m-%d')}")
    
    # Nastavení počátečního a koncového času
    date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    date_end = date.replace(hour=23, minute=55, second=0, microsecond=0)
    
    # Pokud zpracováváme dnešní den, nastavíme konec na aktuální čas
    current_date = datetime.now()
    if date.date() == current_date.date():
        date_end = current_date - timedelta(minutes=10)  # Bezpečnostní buffer
    
    current_timestamp = date_start
    
    # Pro každý 5-minutový interval ve dni
    tasks = []
    while current_timestamp <= date_end:
        # Pro každý typ radarových dat vytvoříme úkol
        for radar_type in RADAR_TYPES:
            task = process_radar_file(current_timestamp, radar_type)
            tasks.append(task)
        
        # Posun na další 5-minutový interval
        current_timestamp += timedelta(minutes=5)
    
    # Spuštění všech úkolů současně (s omezením počtu)
    semaphore = asyncio.Semaphore(5)  # Maximálně 5 současných spojení
    
    async def bounded_process(task):
        async with semaphore:
            return await task
    
    bounded_tasks = [bounded_process(task) for task in tasks]
    results = await asyncio.gather(*bounded_tasks, return_exceptions=True)
    
    # Počet úspěšných stažení
    successful = sum(1 for result in results if result is True)
    print(f"Pro datum {date.strftime('%Y-%m-%d')} zpracováno {successful} z {len(tasks)} souborů")

async def main():
    """
    Hlavní funkce pro stažení obou typů radarových dat za poslední 3 dny
    """
    
    # Získání aktuálního data a předchozích 2 dnů
    current_date = datetime.now()
    dates = [
        current_date - timedelta(days=2),
        current_date - timedelta(days=1),
        current_date
    ]
    
    # Zpracování každého dne
    for date in dates:
        await process_time_period(date)
    
    print("Stahování radarových dat bylo dokončeno.")

if __name__ == "__main__":
    asyncio.run(main())