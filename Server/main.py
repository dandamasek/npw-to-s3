from AladinDownloadLOC import downloadAladin
import asyncio
from GRB_to_netCDF import convertToNC
from transfrom_s3 import process_files_by_month
from config import DIR, BUCKET_NAME, REGION

if __name__ == "__main__":
   if (asyncio.run(  downloadAladin())):
        if(convertToNC()):
            process_files_by_month(DIR, BUCKET_NAME, REGION)
