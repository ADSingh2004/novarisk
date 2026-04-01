import numpy as np
from typing import Dict, Any, Tuple, Optional, TYPE_CHECKING
from app.utils.spatial import generate_bbox

if TYPE_CHECKING:
    import torch
    import segmentation_models_pytorch as smp

# Using a lightweight U-Net with ResNet18 encoder
# 5 classes: Forest, Water, Urban, Agriculture, Barren
NUM_CLASSES = 5
CLASS_NAMES = ["forest", "water", "urban", "agriculture", "barren"]

# Maximum inference resolution for CPU performance (keeps inference under ~10s)
MAX_INFERENCE_DIM = 256

# Module-level model cache to avoid re-loading on every request
_cached_model: Optional[Any] = None

def get_model():
    """Returns a cached, singleton model instance."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model
    
    # Lazy import to avoid Windows Python 3.13 import issues
    import torch
    import segmentation_models_pytorch as smp
    
    if smp is None:
        raise ImportError("segmentation-models-pytorch is not installed.")
    
    # Lightweight encoder with pre-trained ImageNet weights.
    # In production, this would load a finetuned Sentinel-2 checkpoint.
    _cached_model = smp.Unet(
        encoder_name="resnet18",
        encoder_weights="imagenet", 
        in_channels=3, # Sentinel-2 RGB
        classes=NUM_CLASSES,
    )
    _cached_model.eval()
    return _cached_model

def calculate_land_cover_from_stac_items(items: list, bbox: Tuple[float, float, float, float]) -> Dict[str, Any]:
    """
    Classifies land cover from a list of Sentinel-2 STAC items.
    Extracts RGB bands and runs a lightweight PyTorch segmentation model.
    
    Performance optimizations:
    - Model is cached as a singleton (avoids reloading ResNet18 on every call)
    - Input is downscaled to MAX_INFERENCE_DIM for CPU inference speed
    - Predictions are upscaled back via nearest-neighbor interpolation
    - OPTIMIZED: Uses shared RGB composite computation to avoid redundant tile downloads
    """
    if not items:
        return {"error": "No Sentinel-2 items found", "status": "failed"}
    
    # Lazy imports to avoid Windows Python 3.13 circular import issues
    import stackstac
    import torch
    import torch.nn.functional as F
        
    try:
        # OPTIMIZED: Stack all bands at once to avoid multiple downloads
        # This is more efficient than computing RGB separately
        cube = stackstac.stack(
            items,
            assets=["B04", "B03", "B02"],  # Red, Green, Blue
            bounds_latlon=bbox,
            resolution=40, # 40m resolution keeps it ~250x250 for a 10km box, fast for inference
            epsg=3857 # Web Mercator
        )
        
        # Mask nodata (0 values) before computing median
        cube = cube.where(cube > 0)
        # Median composite — computed once
        composite = cube.median(dim="time", skipna=True).compute()
        
        # Extract numpy array (Channels: B04, B03, B02)
        rgb = np.stack([
            composite.sel(band="B04").values,
            composite.sel(band="B03").values,
            composite.sel(band="B02").values
        ], axis=0) # Shape: (3, H, W)
        
        # Handle NaNs (background or clouds)
        rgb = np.nan_to_num(rgb, nan=0.0)
        
        # Normalize roughly to [0, 1] for typical Sentinel-2 L2A BOA reflectance
        rgb = np.clip(rgb / 3000.0, 0, 1)
        
        # Full-resolution dimensions
        _, orig_h, orig_w = rgb.shape
        
        # Convert to tensor
        tensor = torch.tensor(rgb, dtype=torch.float32).unsqueeze(0) # Shape: (1, 3, H, W)
        
        # Downscale for CPU inference performance if needed
        # Running U-Net on 985x990 is ~60s+ on CPU; 256x256 is ~2s
        needs_resize = orig_h > MAX_INFERENCE_DIM or orig_w > MAX_INFERENCE_DIM
        if needs_resize:
            scale = MAX_INFERENCE_DIM / max(orig_h, orig_w)
            new_h = max(32, int(orig_h * scale))
            new_w = max(32, int(orig_w * scale))
            tensor = F.interpolate(tensor, size=(new_h, new_w), mode="bilinear", align_corners=False)
        
        # Pad to nearest multiple of 32 (required by U-Net encoder)
        _, _, h, w = tensor.shape
        pad_h = (32 - (h % 32)) % 32
        pad_w = (32 - (w % 32)) % 32
        
        if pad_h > 0 or pad_w > 0:
            tensor = F.pad(tensor, (0, pad_w, 0, pad_h))
            
        # Use cached model
        model = get_model()
        
        # Inference (CPU)
        with torch.no_grad():
            logits = model(tensor)
            probs = torch.softmax(logits, dim=1) # Shape: (1, 5, padded_H, padded_W)
            preds = torch.argmax(probs, dim=1)    # Shape: (1, padded_H, padded_W)
            
        # Crop padding
        if pad_h > 0 or pad_w > 0:
            preds = preds[:, :h, :w]
        
        # Upscale predictions back to original resolution if we downscaled
        if needs_resize:
            preds = F.interpolate(
                preds.unsqueeze(0).float(), 
                size=(orig_h, orig_w), 
                mode="nearest"
            ).squeeze(0).long()
        
        preds_np = preds.squeeze(0).numpy() # Shape: (orig_H, orig_W)
            
        # Calculate percentages
        total_pixels = preds_np.size
        percentages = {}
        
        for i, class_name in enumerate(CLASS_NAMES):
            count = np.sum(preds_np == i)
            percentages[f"{class_name}_percentage"] = float(count / total_pixels) if total_pixels > 0 else 0.0
            
        return {
            "status": "success",
            "percentages": percentages,
            "classification_map": preds_np.tolist(),
            "rgb_shape": [orig_h, orig_w]
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "status": "failed"}
