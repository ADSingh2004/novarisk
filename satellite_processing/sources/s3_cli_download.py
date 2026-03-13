import os
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def download_s3_file_cli(s3_uri: str, destination: str) -> Path:
    """
    Downloads a file from an S3 URI using the AWS CLI.
    This fulfills the one-time download via CLI method requirement.
    Uses --no-sign-request for public buckets like Earth Search.
    
    Args:
        s3_uri (str): The valid S3 URI, e.g. s3://sentinel-cogs/sentinel-s2-l2a-cogs/53/T/ME/2021/1/S2A_53TME_20210101_0_L2A/B04.tif
        destination (str): Local file path for destination.
        
    Returns:
        Path: The local path to the downloaded file.
    """
    dest_path = Path(destination)
    if dest_path.exists() and dest_path.stat().st_size > 0:
        logger.info(f"File {destination} already exists. Skipping download.")
        return dest_path

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        r"C:\Program Files\Amazon\AWSCLIV2\aws.exe", "s3", "cp",
        s3_uri,
        str(dest_path),
        "--no-sign-request"
    ]
    
    logger.info(f"Running subprocess: {' '.join(cmd)}")
    try:
        # Run aws s3 cli command
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info(f"Successfully downloaded {s3_uri} to {dest_path}")
        return dest_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to download from S3 CLI: {e.stderr.decode()}")
        raise Exception(f"S3 CLI Download failed for {s3_uri}")
