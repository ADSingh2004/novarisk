import os
import logging
from eodag import EODataAccessGateway
from eodag import setup_logging
import shutil

logger = logging.getLogger(__name__)

# Basic basic setup logging for eodag
setup_logging(1)

def search_and_download_sentinel1_eodag(
    lat: float, 
    lon: float, 
    start_date: str, 
    end_date: str, 
    dl_path: str = "/tmp/novarisk/s1_eodag/"
) -> str | None:
    """
    Uses EODAG to extract Sentinel-1 GRD SAR data.
    Requires Copernicus Data Space Ecosystem (CDSE) credentials to be set in environment:
    - EODAG__COPERNICUS_DATASPACE__AUTH__CREDENTIALS__USERNAME
    - EODAG__COPERNICUS_DATASPACE__AUTH__CREDENTIALS__PASSWORD
    
    Args:
        lat: Latitude
        lon: Longitude
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        dl_path: Output directory for the GRD zip/SAFE file.
        
    Returns:
        Path to downloaded file or None
    """
    os.makedirs(dl_path, exist_ok=True)
    
    # Initialize the EODataAccessGateway
    # Note: Ensure the default provider is set to copernicus_dataspace in eodag config.
    dag = EODataAccessGateway()
    # Provide a simple point geometry for EODAG
    geometry = {"type": "Point", "coordinates": [lon, lat]}
    
    try:
        # Search for SENTINEL-1 GRD over the area and time range
        search_results, estimated_total = dag.search(
            productType="S1_SAR_GRD",
            geom=geometry,
            start=start_date,
            end=end_date,
        )
        
        logger.info(f"EODAG Found {estimated_total} Sentinel-1 Data Products.")
        
        if len(search_results) == 0:
            logger.warning("No S1 GRD products found via EODAG for the specified parameters.")
            return None
            
        # Select the first product available as an example
        first_product = search_results[0]
        
        logger.info(f"Downloading Product: {first_product.properties['title']}")
        # By default this downloads to the path specified in dag config or local /tmp
        # Let's override explicit path
        download_path = dag.download(first_product, outputs_prefix=dl_path)
        
        logger.info(f"Successfully downloaded to: {download_path}")
        return str(download_path)
        
    except Exception as e:
        logger.error(f"EODAG Search/Download Failed: {e}")
        return None
