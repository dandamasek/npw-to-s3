import boto3
import s3fs
from config import aws_access_key_id, aws_secret_access_key, BUCKET_NAME

def check_s3_data():
    """Jednoduchý skript pro kontrolu, zda data v S3 existují a v jakém jsou formátu"""
    
    AWS_ACCESS_KEY = aws_access_key_id
    AWS_SECRET_KEY = aws_secret_access_key
    BUCKET_NAME = "meteodatabucket"  # Nahraď správným názvem buketu
    
    print(f"Kontroluji data v S3 bucketu: {BUCKET_NAME}")
    
    # Inicializace S3 klienta (boto3)
    s3_client = boto3.client('s3',
                          aws_access_key_id=AWS_ACCESS_KEY,
                          aws_secret_access_key=AWS_SECRET_KEY)
    
    # Inicializace S3FS (pro alternativní kontrolu)
    s3fs_instance = s3fs.S3FileSystem(anon=False,
                                     key=AWS_ACCESS_KEY,
                                     secret=AWS_SECRET_KEY)
    
    # 1. Základní kontrola - vypsat objekty v kořenu bucketu
    print("\n1. Obsah kořenového adresáře:")
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Delimiter='/')
    
    if 'CommonPrefixes' in response:
        print("  Prefixy (adresáře):")
        for prefix in response['CommonPrefixes']:
            print(f"    {prefix['Prefix']}")
    
    if 'Contents' in response:
        print("  Soubory:")
        for obj in response['Contents']:
            print(f"    {obj['Key']}")
    
    # 2. Hledání meteo_data adresáře
    print("\n2. Hledání meteo_data adresáře:")
    meteo_prefix = "meteo_data/"
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=meteo_prefix, Delimiter='/')
    
    if 'CommonPrefixes' in response:
        print("  Nalezené měsíční adresáře:")
        for prefix in response['CommonPrefixes']:
            month_prefix = prefix['Prefix']
            print(f"    {month_prefix}")
            
            # Kontrola obsahu měsíčního adresáře
            month_response = s3_client.list_objects_v2(
                Bucket=BUCKET_NAME, 
                Prefix=month_prefix,
                Delimiter='/'
            )
            
            if 'CommonPrefixes' in month_response:
                print(f"      Parametry v adresáři {month_prefix}:")
                for param_prefix in month_response['CommonPrefixes']:
                    print(f"        {param_prefix['Prefix']}")
            
            if 'Contents' in month_response:
                print(f"      Soubory v adresáři {month_prefix}:")
                for obj in month_response['Contents']:
                    print(f"        {obj['Key']}")
    
    # 3. Hledání konkrétního parametru pro duben 2025
    april_2025 = "meteo_data/202504/"
    print(f"\n3. Hledání dat pro {april_2025}:")
    try:
        april_response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME, 
            Prefix=april_2025
        )
        
        if 'Contents' in april_response and len(april_response['Contents']) > 0:
            print(f"  Nalezeno {len(april_response['Contents'])} objektů:")
            for obj in april_response['Contents'][:10]:  # Jen prvních 10 pro přehlednost
                print(f"    {obj['Key']}")
        else:
            print("  Žádné objekty nenalezeny.")
            
        # Kontrola s3fs
        try:
            print("\n  Kontrola pomocí s3fs:")
            if s3fs_instance.exists(april_2025.rstrip('/')):
                print(f"  Adresář {april_2025} EXISTUJE podle s3fs")
                files = s3fs_instance.ls(april_2025.rstrip('/'))
                print(f"  Obsah adresáře: {files}")
            else:
                print(f"  Adresář {april_2025} NEEXISTUJE podle s3fs")
                
            # Zkusíme zkontrolovat, zda existuje konkrétní zarr soubor
            temp_zarr = f"{april_2025}CLSTEMPERATURE.zarr"
            if s3fs_instance.exists(temp_zarr):
                print(f"  Soubor {temp_zarr} EXISTUJE podle s3fs")
            else:
                print(f"  Soubor {temp_zarr} NEEXISTUJE podle s3fs")
                
        except Exception as e:
            print(f"  Chyba při kontrole s3fs: {e}")
            
    except Exception as e:
        print(f"  Chyba při hledání dat pro duben 2025: {e}")
    
    print("\nHotovo.")

if __name__ == "__main__":
    check_s3_data()