import os
import json
import imageio

def main():
    input_path = "assets/hero_source.mp4"
    output_dir = "static/hero"
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        from PIL import Image
    except ImportError:
        import subprocess
        subprocess.check_call(["pip", "install", "Pillow"])
        from PIL import Image
    
    reader = imageio.get_reader(input_path, 'ffmpeg')
    
    frame_count = 0
    saved_count = 0
    frames_list = []
    
    for frame in reader:
        if frame_count % 2 == 0:
            img = Image.fromarray(frame)
            width = 1000
            wpercent = (width / float(img.size[0]))
            hsize = int((float(img.size[1]) * float(wpercent)))
            img = img.resize((width, hsize), Image.Resampling.LANCZOS)
            
            filename = f"f_{saved_count:03d}.jpg"
            out_path = os.path.join(output_dir, filename)
            img.save(out_path, "JPEG", quality=78)
            frames_list.append(filename)
            saved_count += 1
        frame_count += 1
        
    manifest = {"frames": frames_list, "count": saved_count}
    with open(os.path.join(output_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f)
        
if __name__ == "__main__":
    main()
