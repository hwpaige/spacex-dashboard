from PIL import Image
import os
import sys

def tile_image(input_path, output_dir, tiles_x, tiles_y, target_size=None):
    if not os.path.exists(input_path):
        print(f"Error: Input {input_path} not found")
        return
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Disable DecompressionBombError for very large images
    Image.MAX_IMAGE_PIXELS = None
    
    print(f"Opening {input_path}...")
    with Image.open(input_path) as img:
        original_size = img.size
        print(f"Original size: {original_size}")
        
        # If target_size is provided, resize the image first
        if target_size:
            print(f"Resizing to {target_size}...")
            img = img.resize(target_size, Image.Resampling.LANCZOS)
            width, height = target_size
        else:
            width, height = original_size
            
        tile_width = width // tiles_x
        tile_height = height // tiles_y
        
        print(f"Slicing into {tiles_x}x{tiles_y} tiles (approx {tile_width}x{tile_height} each)...")
        
        for y in range(tiles_y):
            for x in range(tiles_x):
                left = x * tile_width
                top = y * tile_height
                # Ensure the last tile covers the remaining pixels
                right = (x + 1) * tile_width if x < tiles_x - 1 else width
                bottom = (y + 1) * tile_height if y < tiles_y - 1 else height
                
                tile = img.crop((left, top, right, bottom))
                output_path = os.path.join(output_dir, f"tile_{x}_{y}.jpg")
                tile.save(output_path, quality=90, optimize=True)
                print(f"Saved {output_path} ({tile.size})")

if __name__ == "__main__":
    # Recommended configurations:
    # 2x1 tiles: 8192x4096 total (128MB VRAM) - Good for 1GB/2GB Pi
    # 4x2 tiles: 16384x8192 total (512MB VRAM) - Excellent for 4GB/8GB Pi
    
    input_file = 'assets/images/earth_texture_hd.jpg'
    output_folder = 'assets/images/tiles'
    
    # Let's upgrade to 4x2 for much higher fidelity
    tiles_x = 4
    tiles_y = 2
    
    # We resize to exact multiples of the tile count for perfect alignment
    # 4096 is the hardware limit for Pi 4/5
    target_w = tiles_x * 4096
    target_h = tiles_y * 4096
    
    # Note: If source is smaller than target, resize() will upscale.
    # The HD source is 21600x10800, so we are still downscaling slightly to 16384x8192.
    
    tile_image(input_file, output_folder, tiles_x, tiles_y, target_size=(target_w, target_h))
    
    print(f"\nTiling complete ({tiles_x}x{tiles_y}).")
    print("Update globe.html with these values to use the new grid.")
