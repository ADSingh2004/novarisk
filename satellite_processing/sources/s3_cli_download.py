import os
import subprocess
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

def download_s3_file_cli(s3_uri: str, destination: str) -> Path:
    """
    Downloads a file from an S3 URI using the AWS CLI.
    Fixed for Windows compatibility.
    Uses --no-sign-request for public buckets like Sentinel data.
    """
    dest_path = Path(destination)
    
    # FIX: On Windows, use proper temp directory instead of \tmp\
    if dest_path.drive == '':  # Relative path or \tmp\ on Windows
        # Use Windows temp directory
        temp_base = Path(tempfile.gettempdir()) / "novarisk" / "s1"
        temp_base.mkdir(parents=True, exist_ok=True)
        dest_path = temp_base / Path(destination).name
        logger.info(f"Redirecting download to Windows temp: {dest_path}")
    
    # Ensure parent directory exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Skip if already downloaded
    if dest_path.exists() and dest_path.stat().st_size > 0:
        logger.info(f"File already cached: {dest_path}")
        return dest_path

    # Construct AWS CLI command
    cmd = [
        r"C:\Program Files\Amazon\AWSCLIV2\aws.exe", 
        "s3", "cp",
        s3_uri,
        str(dest_path),
        "--no-sign-request"
    ]
    
    logger.info(f"Downloading: {s3_uri}")
    logger.info(f"Destination: {dest_path}")
    
    try:
        result = subprocess.run(
            cmd, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        logger.info(f"✓ Downloaded successfully: {dest_path}")
        return dest_path
    
    except FileNotFoundError as e:
        logger.error("AWS CLI not found!")
        logger.error("Install from: https://awscli.amazonaws.com/AWSCLIV2.msi")
        raise Exception("AWS CLI not installed or not in expected path")
    
    except subprocess.CalledProcessError as e:
        logger.error(f"S3 download failed: {e.stderr}")
        logger.error(f"S3 URI: {s3_uri}")
        logger.error(f"Destination: {dest_path}")
        logger.error("This is expected if satellite data temporarily unavailable")
        raise Exception(f"S3 download failed for {s3_uri}")
