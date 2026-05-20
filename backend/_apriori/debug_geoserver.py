import requests
import logging
import json
import os
import sys
from datetime import datetime

# --- Configuration ---
GS_URL = os.getenv("GEOSERVER_URL", "http://localhost:8080/geoserver")
GS_USER = os.getenv("GEOSERVER_USER", "admin")
GS_PASS = os.getenv("GEOSERVER_PASS", "geoserver")
AUTH = (GS_USER, GS_PASS)
WORKSPACE = "vprouting"
STORE = "rain_forecast"
LAYER = "hourly_rain"
STYLE = "rain_blue"

# --- Logging Setup ---
LOG_FILENAME = f"geoserver_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILENAME),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def check_geoserver_alive():
    logger.info(f"--- Checking GeoServer Status at {GS_URL} ---")
    try:
        r = requests.get(f"{GS_URL}/rest/about/version", auth=AUTH, timeout=5)
        if r.status_code == 200:
            logger.info(f"GeoServer is ALIVE. Version info: {r.text.strip()}")
            return True
        else:
            logger.error(f"GeoServer responded with status {r.status_code}: {r.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to GeoServer: {e}")
        return False

def check_workspace():
    logger.info(f"--- Checking Workspace '{WORKSPACE}' ---")
    r = requests.get(f"{GS_URL}/rest/workspaces/{WORKSPACE}.json", auth=AUTH)
    if r.status_code == 200:
        logger.info(f"Workspace '{WORKSPACE}' exists.")
    else:
        logger.error(f"Workspace '{WORKSPACE}' missing or error: {r.status_code}")

def check_store():
    logger.info(f"--- Checking CoverageStore '{STORE}' ---")
    r = requests.get(f"{GS_URL}/rest/workspaces/{WORKSPACE}/coveragestores/{STORE}.json", auth=AUTH)
    if r.status_code == 200:
        store_data = r.json()
        logger.info(f"Store '{STORE}' exists. Details: {json.dumps(store_data, indent=2)}")
    else:
        logger.error(f"Store '{STORE}' missing or error: {r.status_code}")

def check_coverage():
    logger.info(f"--- Checking Coverage/Layer '{LAYER}' ---")
    r = requests.get(f"{GS_URL}/rest/workspaces/{WORKSPACE}/coveragestores/{STORE}/coverages/{LAYER}.json", auth=AUTH)
    if r.status_code == 200:
        cov_data = r.json()
        logger.info(f"Coverage '{LAYER}' exists.")
        
        # Check dimensions
        coverage = cov_data.get("coverage", {})
        
        # Check LatLon Bounding Box
        bbox = coverage.get("latLonBoundingBox", {})
        logger.info(f"LatLon Bounding Box: {json.dumps(bbox, indent=2)}")
        
        # Print all metadata to see how time is stored
        metadata = coverage.get("metadata", {})
        logger.info(f"Metadata: {json.dumps(metadata, indent=2)}")
        
        # Print dimensions to see if time is a dimension
        dimensions = coverage.get("dimensions", {})
        logger.info(f"Dimensions dictionary: {json.dumps(dimensions, indent=2)}")
    else:
        logger.error(f"Coverage '{LAYER}' missing or error: {r.status_code}")

def check_style():
    logger.info(f"--- Checking Style '{STYLE}' ---")
    r = requests.get(f"{GS_URL}/rest/styles/{STYLE}.sld", auth=AUTH)
    if r.status_code == 200:
        logger.info(f"Style '{STYLE}' exists.")
        # Log first 15 lines of SLD to check color map starting threshold
        lines = r.text.splitlines()
        logger.info("SLD Snippet (first 15 lines):")
        for line in lines[:15]:
            logger.info("  " + line)
    else:
        logger.error(f"Style '{STYLE}' missing or error: {r.status_code}")

def test_wms_getmap():
    logger.info("--- Testing WMS GetMap ---")
    # Base params matching your frontend
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "FORMAT": "image/png",
        "TRANSPARENT": "true",
        "LAYERS": f"{WORKSPACE}:{LAYER}",
        "STYLES": STYLE,
        "SRS": "EPSG:4326",
        "WIDTH": "858",
        "HEIGHT": "590",
        "BBOX": "-0.817,41.183,18.183,51.183"
    }

    # Test 1: No TIME param (default behavior)
    logger.info("Testing GetMap WITHOUT TIME parameter...")
    r_no_time = requests.get(f"{GS_URL}/{WORKSPACE}/wms", params=params)
    if r_no_time.status_code == 200:
        file_no_time = "debug_wms_no_time.png"
        with open(file_no_time, "wb") as f:
            f.write(r_no_time.content)
        logger.info(f"Success. Saved '{file_no_time}' ({len(r_no_time.content)} bytes).")
        if len(r_no_time.content) < 1000:
             logger.warning("Image size is very small, likely empty/transparent.")
    else:
        logger.error(f"WMS request failed: {r_no_time.status_code} - {r_no_time.text}")

    # Test 2: We need to pull the capabilities to find a valid time
    logger.info("Fetching WMS GetCapabilities to find valid TIME parameters...")
    cap_r = requests.get(f"{GS_URL}/{WORKSPACE}/wms?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetCapabilities")
    if cap_r.status_code == 200:
        if "Dimension name=\"time\"" in cap_r.text:
            # Quick and dirty XML parse to extract the time extent
            import xml.etree.ElementTree as ET
            try:
                # WMS 1.1.1 Capabilities
                root = ET.fromstring(cap_r.text)
                times = []
                for elem in root.iter():
                    if 'Extent' in elem.tag and elem.attrib.get('name') == 'time':
                        times = elem.text.split(',')
                        break
                
                if times:
                    logger.info(f"Found {len(times)} valid times in Capabilities.")
                    first_time = times[0].strip()
                    logger.info(f"Testing GetMap WITH TIME parameter: {first_time} ...")
                    params["TIME"] = first_time
                    r_time = requests.get(f"{GS_URL}/{WORKSPACE}/wms", params=params)
                    if r_time.status_code == 200:
                        file_time = "debug_wms_with_time.png"
                        with open(file_time, "wb") as f:
                            f.write(r_time.content)
                        logger.info(f"Success. Saved '{file_time}' ({len(r_time.content)} bytes).")
                        if len(r_time.content) < 1000:
                             logger.warning("Image size is very small, likely empty/transparent.")
                    else:
                        logger.error(f"WMS request with TIME failed: {r_time.status_code} - {r_time.text}")
                else:
                    logger.warning("Found TIME dimension but couldn't parse specific time values.")
            except Exception as e:
                logger.error(f"Failed to parse Capabilities XML for times: {e}")
        else:
            logger.warning("No TIME dimension advertised in WMS Capabilities for this layer.")
    else:
         logger.error(f"GetCapabilities failed: {cap_r.status_code}")

if __name__ == "__main__":
    logger.info("STARTING GEOSERVER WMS DIAGNOSTICS")
    logger.info(f"Targeting: {GS_URL}")
    if check_geoserver_alive():
        check_workspace()
        check_store()
        check_coverage()
        check_style()
        test_wms_getmap()
    logger.info(f"Diagnostics complete. Full log saved to: {LOG_FILENAME}")
