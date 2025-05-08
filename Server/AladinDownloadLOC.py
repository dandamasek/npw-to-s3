import aiohttp
import asyncio
import bz2
import os
from datetime import datetime, timedelta
from config import (
    DOMAINLA,
    DOMAINCZ,
    SUBDOMAINCZ,
    SUBDOMAINLA,
    ALADIN_ATTRIBUTES,
    DIR
)

DOMAIN = DOMAINCZ
DIRNAME = DIR
SUBDOMAIN = SUBDOMAINCZ
# DOMAIN = DOMAINLA
# DIRNAME = "LA"
# SUBDOMAIN = SUBDOMAINLA

# List of TIME values to process
TIME_VALUES = ["00", "06", "12", "18"]

async def fetch_data(URL):
    async with aiohttp.ClientSession() as session:
        async with session.get(URL) as response:
            if response.status == 200:
                data = await response.read()
                return data
            else:
                print(f"Failed to fetch data, status code: {response.status}")
                return None

async def process_time_slot(date, time_value):
    current_date = date.strftime(f"%Y%m%d{time_value}")
    
    for attribute in ALADIN_ATTRIBUTES:
        CURRENTFILE = f"{current_date}_{ALADIN_ATTRIBUTES[attribute]}.grb.bz2"
        URL = f"{DOMAIN}{time_value}{SUBDOMAIN}{CURRENTFILE}"
        
        data = await fetch_data(URL)
        if data:
            output_file_grb = CURRENTFILE.replace('.bz2', '')
            try:
                decompressed_data = bz2.decompress(data)
            except Exception as e:
                print(f"Failed to decompress bz2 data for {date.strftime('%Y-%m-%d')} {time_value}: {e}")
                continue
            
            # Create directories
            os.makedirs(f"{DIRNAME}", exist_ok=True)
            os.makedirs(f"{DIRNAME}/{time_value}", exist_ok=True)
            os.makedirs(f"{DIRNAME}/{time_value}/{current_date}", exist_ok=True)
            
            # Write the decompressed file
            output_path = f"{DIRNAME}/{time_value}/{current_date}/{output_file_grb}"
            with open(output_path, 'wb') as file:
                file.write(decompressed_data)
                print(f"Saved decompressed GRB data to {output_file_grb} for date {date.strftime('%Y-%m-%d')} time {time_value}\n")
        else:
            print(f"Failed to fetch the data for date {date.strftime('%Y-%m-%d')} time {time_value}.\n")

async def downloadAladin():
    # Get current date and the previous 2 days
    current_date = datetime.now()
    dates = [
        current_date - timedelta(days=1),
    ]
    
    # Create tasks for each date and time slot combination
    tasks = []
    for date in dates:
        for time in TIME_VALUES:
            tasks.append(process_time_slot(date, time))
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)
    
    return True