import xarray as xr
import os
import re
import boto3
import s3fs
from datetime import datetime
import logging
from config import aws_access_key_id, aws_secret_access_key, BUCKET_NAME, DIR, REGION

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def list_files_in_directory(directory_path, extension=None):
    """List all files in a directory with a specific extension."""
    file_paths = []
    
    for dirpath, _, filenames in os.walk(directory_path):
        for filename in filenames:
            if extension and not filename.endswith(extension):
                continue
            
            file_path = os.path.join(dirpath, filename)
            file_paths.append(file_path)
    
    return file_paths

def extract_date_and_param(filename):
    """Extract date, time and parameter name from filename."""
    basename = os.path.basename(filename)
    # Format like "2025012112_CLS_VISICLD.grb"
    match = re.match(r"(\d{10})_(.+)\.", basename)
    
    if match:
        datetime_str, param_name = match.groups()
        # Extract year, month, day and hour
        year = datetime_str[:4]
        month = datetime_str[4:6]
        day = datetime_str[6:8]
        hour = datetime_str[8:10]
        
        # Create formatted date
        date = f"{year}-{month}-{day}T{hour}:00:00"
        
        # Adjust parameter name
        param_name = param_name.replace('-', '_')
        
        return year, month, date, param_name
    return None, None, None, None

# Funkce pro kontrolu existence pomocí boto3
def check_exists_boto3(bucket, prefix,REGION):
    """Kontroluje existenci objektu/prefixu pomocí boto3 místo s3fs"""
    s3_client = boto3.client('s3',
                           region_name=REGION,
                           aws_access_key_id=aws_access_key_id,
                           aws_secret_access_key=aws_secret_access_key)
    response = s3_client.list_objects_v2(
        Bucket=bucket,
        Prefix=prefix,
        MaxKeys=1
    )
    return 'Contents' in response and len(response['Contents']) > 0

def process_files_by_month(dir_path, bucket_name, REGION):
    """Process files by month and parameter and save to S3 bucket."""
    # List NetCDF files
    nc_files = list_files_in_directory(dir_path, '.nc')
    logger.info(f"Found {len(nc_files)} NetCDF files to process")
    
    # Group files by month
    files_by_month = {}
    for nc_file in nc_files:
        year, month, date, param_name = extract_date_and_param(nc_file)
        if year and month:
            month_key = f"{year}{month}"
            if month_key not in files_by_month:
                files_by_month[month_key] = []
            files_by_month[month_key].append((nc_file, date, param_name))
    
    # Initialize S3 filesystem interface
    storage_options = {"key": aws_access_key_id, "secret": aws_secret_access_key,"client_kwargs": {"region_name": REGION}}
    s3fs_instance = s3fs.S3FileSystem(anon=False, **storage_options)
    
    # Process files by month
    for month_key, file_info_list in files_by_month.items():
        logger.info(f"Processing month: {month_key}")
        
        # S3 path for month
        s3_month_prefix = f"meteo_data/{month_key}"
        
        # Group files by parameters
        params_dict = {}
        for file_info in file_info_list:
            nc_file, date, param_name = file_info
            if param_name not in params_dict:
                params_dict[param_name] = []
            params_dict[param_name].append((nc_file, date))
        
        for param_name, param_files in params_dict.items():
            logger.info(f"Processing parameter: {param_name}")
            
            # S3 path for this parameter
            s3_zarr_path = f"{s3_month_prefix}/{param_name}.zarr"
            s3_uri = f"s3://{bucket_name}/{s3_zarr_path}"
            
            # Sort files by date
            param_files.sort(key=lambda x: x[1])
            
            try:
                # Process each file for this parameter in batches
                batch_size = 10  # Process 10 files at a time
                for batch_idx in range(0, len(param_files), batch_size):
                    batch_files = param_files[batch_idx:batch_idx + batch_size]
                    batch_num = batch_idx // batch_size + 1
                    logger.info(f"Processing batch {batch_num}/{(len(param_files)-1)//batch_size + 1}")
                    
                    # Collecting datasets for this batch
                    datasets = []
                    
                    for nc_file, date in batch_files:
                        try:
                            # Load NetCDF file as xarray dataset
                            ds = xr.open_dataset(nc_file, decode_timedelta=True)
                            
                            # Rename data variable to parameter name
                            var_name = list(ds.data_vars.keys())[0]
                            ds = ds.rename({var_name: param_name})
                            
                            # Set correct time
                            ds['time'] = xr.DataArray([datetime.fromisoformat(date)], dims=['time'])
                            
                            # If 'step' has more than 72, truncate to 72
                            if 'step' in ds.dims and len(ds['step']) > 72:
                                ds = ds.isel(step=slice(0, 72))
                            
                            # Add dataset to list
                            datasets.append(ds)
                        except Exception as e:
                            logger.error(f"Error processing file {nc_file}: {e}")
                    
                    # Combine all datasets in batch
                    if datasets:
                        logger.info(f"Combining {len(datasets)} files from batch {batch_num}")
                        
                        combined_ds = xr.concat(datasets, dim="time")
                        
                        # Optimize chunking - use reasonably sized chunks
                        time_chunk = min(len(combined_ds.time), 5)  # More reasonable time chunk size
                        step_chunk = min(20, len(combined_ds.step)) if 'step' in combined_ds.dims else None
                        
                        chunks = {'time': time_chunk}
                        if step_chunk:
                            chunks['step'] = step_chunk
                            
                        combined_ds = combined_ds.chunk(chunks)
                        
                        # ZMĚNA: Check if Zarr store already exists using boto3 instead of s3fs
                        zarr_prefix = f"{s3_zarr_path}/"
                        zarr_exists = check_exists_boto3(bucket_name, zarr_prefix, REGION)
                        
                        logger.info(f"Checking if zarr store exists at {zarr_prefix} using boto3: {zarr_exists}")
                        
                        if zarr_exists:
                            mode = "a"
                            append_dim = "time"
                            logger.info(f"Appending data to existing Zarr store at {s3_uri}")
                            
                            # For appending, make sure there are no time duplicates
                            try:
                                existing_ds = xr.open_zarr(s3_uri, storage_options=storage_options)
                                existing_times = existing_ds.time.values
                                new_times = combined_ds.time.values
                                
                                # Filter out times that already exist
                                duplicate_mask = [t in existing_times for t in new_times]
                                if any(duplicate_mask):
                                    logger.warning(f"Found {sum(duplicate_mask)} duplicate timestamps - removing")
                                    combined_ds = combined_ds.isel(time=[i for i, m in enumerate(duplicate_mask) if not m])
                                    
                                # If everything was duplicate, skip this batch
                                if len(combined_ds.time) == 0:
                                    logger.info("All timestamps already exist, skipping batch")
                                    continue
                                    
                                existing_ds.close()
                            except Exception as e:
                                logger.error(f"Error checking for time duplicates: {e}")
                                # Pokud nelze otevřít existující dataset, pokračujeme s append
                                logger.warning("Will continue with append mode despite error")
                                pass
                        else:
                            mode = "w"
                            append_dim = None
                            logger.info(f"Creating new Zarr store at {s3_uri}")
                        
                        # Save to S3
                        logger.info(f"Saving batch to {s3_uri} (mode={mode})")
                        try:
                            # Add retry mechanism
                            max_retries = 3
                            retry_count = 0
                            while retry_count < max_retries:
                                try:
                                    combined_ds.to_zarr(s3_uri, mode=mode, append_dim=append_dim, 
                                                    storage_options=storage_options,
                                                    consolidated=True)  # Enable metadata consolidation for better performance
                                    logger.info(f"Successfully saved data to {s3_uri}")
                                    break
                                except Exception as e:
                                    retry_count += 1
                                    logger.warning(f"Error saving to Zarr (attempt {retry_count}/{max_retries}): {e}")
                                    if retry_count >= max_retries:
                                        raise
                        except Exception as e:
                            logger.error(f"Failed to save data after {max_retries} attempts: {e}")
                        
                        # Close datasets and clear memory
                        combined_ds.close()
                        combined_ds = None
                        for ds in datasets:
                            ds.close()
                        datasets = []
            
            except Exception as e:
                logger.error(f"Error processing parameter {param_name}: {e}")
    
    logger.info("Finished processing all files")
    return True

def print_data_structure(bucket_name):
    """Display structure of stored data by month and parameter from S3 bucket"""
    # Initialize S3FS with credentials
    storage_options = {"key": aws_access_key_id, "secret": aws_secret_access_key}
    s3fs_instance = s3fs.S3FileSystem(anon=False, **storage_options)
    base_prefix = "meteo_data"
    
    # Initialize boto3 client for checking existence
    s3_client = boto3.client('s3',
                           aws_access_key_id=aws_access_key_id,
                           aws_secret_access_key=aws_secret_access_key)
    
    # Check if prefix exists
    prefix_exists = check_exists_boto3(bucket_name, base_prefix, REGION)
    if not prefix_exists:
        print("Data prefix doesn't exist in S3 bucket yet.")
        return
    
    # List months in S3
    try:
        # Use boto3 to list months
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=base_prefix + "/",
            Delimiter="/"
        )
        
        months = []
        if 'CommonPrefixes' in response:
            for prefix in response['CommonPrefixes']:
                month_prefix = prefix['Prefix']
                month = month_prefix.split('/')[-2]  # Extract month from path
                months.append(month)
        
        for month in sorted(months):
            print(f"Month: {month}")
            month_prefix = f"{base_prefix}/{month}"
            
            # List zarr files for given month using boto3
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=month_prefix + "/",
                Delimiter="/"
            )
            
            params = []
            if 'CommonPrefixes' in response:
                for prefix in response['CommonPrefixes']:
                    param_path = prefix['Prefix']
                    if param_path.endswith(".zarr/"):
                        param = param_path.split('/')[-2].replace(".zarr", "")
                        params.append(param)
            
            for param in sorted(params):
                s3_zarr_path = f"s3://{bucket_name}/{base_prefix}/{month}/{param}.zarr"
                try:
                    # Open dataset with decode_timedelta=True
                    ds = xr.open_zarr(s3_zarr_path, storage_options=storage_options)
                    
                    # Get time range and unique days
                    time_min = ds.time.min().values
                    time_max = ds.time.max().values
                    days = len(set(ds.time.dt.strftime('%Y-%m-%d').values))
                    
                    print(f"  - {param}: {days} days, {len(ds.time)} measurements, time range: {time_min} to {time_max}")
                    
                    # Check for gaps in time series
                    time_diff = ds.time.diff('time')
                    if len(time_diff) > 0:
                        unique_diffs = set(time_diff.astype(str).values)
                        if len(unique_diffs) > 1:
                            print(f"    * Warning: Irregular time intervals detected: {unique_diffs}")
                    
                    ds.close()
                except Exception as e:
                    print(f"  - {param}: Error opening dataset: {e}")
    except Exception as e:
        print(f"Error reading S3 structure: {e}")