import os

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
    if not os.path.exists(parentfolder):
        raise FileNotFoundError(f"Ordner '{parentfolder}' existiert nicht")
    valid_files = []
    
    # Alle .nc-Dateien im Ordner durchsuchen
    for filename in os.listdir(parentfolder):
        if filename.endswith('.nc'):

            # Zeitstempel aus dem Dateinamen extrahieren
            # Erwartet Format: "{timestamp}.nc" z.B. "1234567890.nc"
            try:
                # Alles vor .nc entfernen und zu Integer konvertieren
                timestamp_str = filename[:-3]  # Entfernt ".nc"
                file_timestamp = int(timestamp_str)
            except ValueError:
                # Wenn Zeitstempel nicht parsbar ist, Datei überspringen
                continue
        
            # Prüfen ob Datei noch gültig ist
            age = start_time - file_timestamp
            if 0 <= age <= valid_time:
                full_path = os.path.join(parentfolder, filename)
                valid_files.append((file_timestamp, full_path))
            
    
    # Neuste Datei oder None
    if not valid_files:
        return None
    else:
        newest_files = max(valid_files, key=lambda x: x[0])
        return newest_files[1]
    
