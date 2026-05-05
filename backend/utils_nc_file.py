import os
from pathlib import Path


def _collect_timestamped_nc_files(parentfolder_path):
    files = []
    for filename in os.listdir(parentfolder_path):
        if not filename.endswith('.nc'):
            continue
        try:
            file_timestamp = int(filename[:-3])
        except ValueError:
            continue
        full_path = os.path.join(str(parentfolder_path), filename)
        files.append((file_timestamp, full_path))
    return files


def get_latest_nc_file(parentfolder='nc_folder'):
    """Gibt das neueste timestamped .nc File zurück."""
    base_dir = Path(__file__).resolve().parent
    parentfolder_path = Path(parentfolder)
    if not parentfolder_path.is_absolute():
        parentfolder_path = base_dir / parentfolder_path

    if not parentfolder_path.exists():
        raise FileNotFoundError(f"Ordner '{parentfolder_path}' existiert nicht")

    timestamped_files = _collect_timestamped_nc_files(parentfolder_path)
    if not timestamped_files:
        raise FileNotFoundError(
            f"Keine timestamped .nc Dateien im Ordner '{parentfolder_path}' gefunden"
        )

    newest_file = max(timestamped_files, key=lambda x: x[0])
    return newest_file[1]

def get_nc_file(start_time, parentfolder='nc_folder', valid_time=33*3600):
    """
    Gibt das gültige NC-File mit dem neuesten Zeitstempel zurück.
    
    Parameter
    ----------
    start_time : float
        Referenz-Zeitstempel (z.B. aktuelle Zeit mit time.time())
    parentfolder : str, optional
        Pfad zum Ordner mit den NC-Files (default: 'nc_folder')
    valid_time : int, optional
        Gültigkeitsdauer in Sekunden (default: 33 Stunden = 118800 Sekunden)
    
    Returns
    -------
    str or None
        Pfad zum neuesten gültigen NC-File, oder None wenn keines gültig ist
    """
    
    # Sicherstellen, dass der Ordner existiert
    base_dir = Path(__file__).resolve().parent
    parentfolder_path = Path(parentfolder)
    if not parentfolder_path.is_absolute():
        parentfolder_path = base_dir / parentfolder_path

    if not parentfolder_path.exists():
        raise FileNotFoundError(f"Ordner '{parentfolder_path}' existiert nicht")
    all_timestamped_files = _collect_timestamped_nc_files(parentfolder_path)
    if not all_timestamped_files:
        raise FileNotFoundError(
            f"Keine timestamped .nc Dateien im Ordner '{parentfolder_path}' gefunden"
        )

    valid_files = []
    for file_timestamp, full_path in all_timestamped_files:
        age = start_time - file_timestamp
        if 0 <= age <= valid_time:
            valid_files.append((file_timestamp, full_path))

    if valid_files:
        newest_files = max(valid_files, key=lambda x: x[0])
        return newest_files[1]

    # Kein valider Modelllauf in der Gültigkeitsdauer gefunden.
    newest_available = max(all_timestamped_files, key=lambda x: x[0])
    raise FileNotFoundError(
        "Kein gültiges .nc File für start_time gefunden. "
        f"Neueste verfügbare Datei: {newest_available[1]}"
    )
    
