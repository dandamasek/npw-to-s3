import xarray as xr
import pandas as pd
import matplotlib.pyplot as plt
import s3fs
import boto3
from matplotlib.widgets import Slider, Button
from config import aws_access_key_id, aws_secret_access_key, BUCKET_NAME, REGION

# AWS přístupové údaje
AWS_ACCESS_KEY = aws_access_key_id
AWS_SECRET_KEY = aws_secret_access_key
BUCKET_NAME = "npw-aladin"
BASE_PREFIX = "meteo_data"

# Vytvoření připojení k S3
s3fs_instance = s3fs.S3FileSystem(anon=False,
                                 key=AWS_ACCESS_KEY,
                                 secret=AWS_SECRET_KEY,
                                 client_kwargs={"region_name": REGION})

# Inicializace boto3 klienta pro lepší kontrolu existence
s3_client = boto3.client('s3',
                       aws_access_key_id=AWS_ACCESS_KEY,
                       aws_secret_access_key=AWS_SECRET_KEY,
                        region_name=REGION)

def check_exists_boto3(bucket, prefix):
    """Kontroluje existenci objektu/prefixu pomocí boto3 místo s3fs"""
    response = s3_client.list_objects_v2(
        Bucket=bucket,
        Prefix=prefix,
        MaxKeys=1
    )
    return 'Contents' in response and len(response['Contents']) > 0

def load_data(parameter, start_date, end_date, lat_range=None, lon_range=None):
    """Načte data z S3 pro zadaný parametr a časové období."""
    try:
        # Převedení dat na datetime objekty
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # Zjištění potřebných měsíců
        needed_months = []
        current = start_dt.replace(day=1)
        while current <= end_dt:
            needed_months.append(current.strftime("%Y%m"))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        print(f"Potřebné měsíce: {needed_months}")
        
        # Načtení dat pro každý měsíc
        datasets = []
        storage_options = {"anon": False, "key": AWS_ACCESS_KEY, "secret": AWS_SECRET_KEY,
                           "client_kwargs": {"region_name": REGION}}
        
        for month in needed_months:
            # Cesta k zarr souboru v S3
            zarr_path = f"s3://{BUCKET_NAME}/{BASE_PREFIX}/{month}/{parameter}.zarr"
            prefix_to_check = f"{BASE_PREFIX}/{month}/{parameter}.zarr/"
            
            # Kontrola existence souboru pomocí boto3 místo s3fs
            print(f"Kontroluji existenci dat pro měsíc {month} (parametr {parameter})...")
            exists = check_exists_boto3(BUCKET_NAME, prefix_to_check)
            
            if exists:
                print(f"Data pro měsíc {month} EXISTUJÍ.")
                try:
                    # Načtení dat přímo - přeskočíme kontrolu s s3fs.exists()
                    print(f"Načítám data z {zarr_path}...")
                    ds = xr.open_zarr(zarr_path, consolidated=True, storage_options=storage_options)
                    print(f"Načten dataset s časovým rozsahem: {ds.time.min().values} až {ds.time.max().values}")
                    print(f"Rozměry datasetu: {ds.dims}")
                    datasets.append(ds)
                except Exception as e:
                    print(f"Chyba při načítání dat pro měsíc {month}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"Data pro měsíc {month} NEEXISTUJÍ nebo jsou prázdná.")
        
        if not datasets:
            print("Nepodařilo se načíst žádná data pro zadané období.")
            return None
        
        # Spojení datasetů
        print(f"Spojuji {len(datasets)} datasetů...")
        combined_ds = xr.concat(datasets, dim="time")
        
        # Filtrování podle času
        print(f"Filtruji data od {start_dt} do {end_dt}")
        filtered_ds = combined_ds.sel(time=slice(start_dt, end_dt))
        
        # Filtrování podle zeměpisné šířky a délky
        if lat_range is not None:
            print(f"Filtruji zeměpisnou šířku od {lat_range[0]} do {lat_range[1]}")
            filtered_ds = filtered_ds.sel(latitude=slice(lat_range[0], lat_range[1]))
        
        if lon_range is not None:
            print(f"Filtruji zeměpisnou délku od {lon_range[0]} do {lon_range[1]}")
            filtered_ds = filtered_ds.sel(longitude=slice(lon_range[0], lon_range[1]))
        
        print(f"Finální rozměry datasetu: {filtered_ds.dims}")
        return filtered_ds
        
    except Exception as e:
        print(f"Chyba při načítání dat: {e}")
        import traceback
        traceback.print_exc()
        return None


def launch_viewer():
    """Spustí interaktivní prohlížeč meteorologických dat."""

    # Výchozí parametry pro načtení
    default_param = "CLSTEMPERATURE"
    default_start_date = "2025-03-20"
    default_end_date = "2025-05-26"
    default_lat_range = (49.0, 50.5)  
    default_lon_range = (14.0, 16.0)
    
    # Načtení dat
    print(f"\nNačítám data pro {default_param}...")
    data = load_data(default_param, default_start_date, default_end_date, 
                   default_lat_range, default_lon_range)
    
    if data is None:
        print("Nepodařilo se načíst data.")
        return
    
    # Vytvoření okna pro vizualizaci
    fig, ax = plt.subplots(figsize=(14, 10))
    plt.subplots_adjust(bottom=0.25)
    
    # Počáteční hodnoty
    time_idx = 0
    step_idx = 0
    max_time_idx = len(data.time) - 1
    max_step_idx = len(data.step) - 1
    
    # Rozsah hodnot parametru pro konzistentní barvy
    param_min = float(data[default_param].min())
    param_max = float(data[default_param].max())
    
    # Počáteční vykreslení
    time_value = data.time.values[time_idx]
    step_value = data.step.values[step_idx]
    valid_time = pd.to_datetime(time_value) + pd.to_timedelta(step_value)
    
    title = (f"{default_param}\n"
            f"Čas měření: {pd.to_datetime(time_value)}\n"
            f"Krok předpovědi: +{step_value}\n"
            f"Platnost: {valid_time}")
    
    # Vykreslení dat
    plot_data = data[default_param].isel(time=time_idx, step=step_idx)
    img = ax.pcolormesh(data.longitude, data.latitude, plot_data, 
                       cmap='viridis', vmin=param_min, vmax=param_max, 
                       shading='auto')
    plt.colorbar(img, ax=ax, label=default_param)
    ax.set_title(title)
    ax.set_xlabel('Zeměpisná délka')
    ax.set_ylabel('Zeměpisná šířka')
    ax.grid(True, linestyle='--', alpha=0.6)
    
    # Ovládací prvky - časový posuvník
    ax_time = plt.axes([0.25, 0.15, 0.5, 0.03])
    time_slider = Slider(
        ax=ax_time,
        label='Čas měření',
        valmin=0,
        valmax=max_time_idx,
        valinit=time_idx,
        valstep=1
    )
    
    # Ovládací prvky - krok předpovědi
    ax_step = plt.axes([0.25, 0.10, 0.5, 0.03])
    step_slider = Slider(
        ax=ax_step,
        label='Krok předpovědi',
        valmin=0,
        valmax=max_step_idx,
        valinit=step_idx,
        valstep=1
    )
    
    # Funkce pro aktualizaci grafu
    def update(val):
        time_idx = int(time_slider.val)
        step_idx = int(step_slider.val)
        
        time_value = data.time.values[time_idx]
        step_value = data.step.values[step_idx]
        valid_time = pd.to_datetime(time_value) + pd.to_timedelta(step_value)
        
        title = (f"{default_param}\n"
                f"Čas měření: {pd.to_datetime(time_value)}\n"
                f"Krok předpovědi: +{step_value}\n"
                f"Platnost: {valid_time}")
        
        plot_data = data[default_param].isel(time=time_idx, step=step_idx)
        img.set_array(plot_data.values.ravel())
        ax.set_title(title)
        fig.canvas.draw_idle()
    
    # Připojení funkce k událostem posuvníků
    time_slider.on_changed(update)
    step_slider.on_changed(update)
    
    # Tlačítko pro reset
    ax_reset = plt.axes([0.8, 0.10, 0.1, 0.04])
    reset_button = Button(ax_reset, 'Reset', hovercolor='0.975')
    
    def reset(event):
        time_slider.reset()
        step_slider.reset()
    
    reset_button.on_clicked(reset)
    
    plt.show()

if __name__ == "__main__":
    launch_viewer()