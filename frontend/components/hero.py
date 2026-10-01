import os
import json
import streamlit as st
import streamlit.components.v1 as components

def render_hero():
    manifest_path = "static/hero/manifest.json"
    if not os.path.exists(manifest_path):
        st.warning("Hero frames not found. Please run the extraction script.")
        return
        
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
        
    frames = manifest["frames"]
    frame_urls = [f"/app/static/hero/{fname}" for fname in frames]
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body, html {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            background-color: #05080A;
        }}
        canvas {{
            display: block;
            width: 100%;
            height: 100%;
            object-fit: contain;
            border-radius: 12px;
        }}
    </style>
    </head>
    <body>
        <canvas id="heroCanvas"></canvas>
        <script>
            const urls = {json.dumps(frame_urls)};
            const images = [];
            let loaded = 0;
            const canvas = document.getElementById('heroCanvas');
            const ctx = canvas.getContext('2d');
            
            // Preload images
            for(let i = 0; i < urls.length; i++) {{
                const img = new Image();
                img.src = urls[i];
                img.onload = () => {{
                    loaded++;
                    if(loaded === urls.length) {{
                        drawFrame(0);
                    }}
                }};
                images.push(img);
            }}
            
            function drawFrame(index) {{
                if (images.length === 0 || !images[index]) return;
                const img = images[index];
                
                // Set canvas size to match image aspect ratio
                canvas.width = img.width;
                canvas.height = img.height;
                
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            }}
            
            // Cursor tracking logic
            let currentFrame = Math.floor(urls.length / 2);
            let targetFrame = currentFrame;
            
            function animate() {{
                if (Math.abs(targetFrame - currentFrame) > 0.1) {{
                    currentFrame += (targetFrame - currentFrame) * 0.12;
                    drawFrame(Math.floor(currentFrame));
                }}
                requestAnimationFrame(animate);
            }}
            animate();

            const handleMove = (x, width) => {{
                if (images.length === 0) return;
                const percent = Math.max(0, Math.min(1, x / width));
                targetFrame = percent * (images.length - 1);
            }};

            const mouseHandler = (e) => {{
                handleMove(e.clientX, window.parent.innerWidth || window.innerWidth);
            }};

            try {{
                if (window.parent && window.parent.document) {{
                    if (window.parent._heroMouseHandler) {{
                        window.parent.document.removeEventListener('mousemove', window.parent._heroMouseHandler);
                    }}
                    window.parent._heroMouseHandler = mouseHandler;
                    window.parent.document.addEventListener('mousemove', mouseHandler);
                }}
            }} catch (e) {{
                // CORS or parent access failed, fallback to local document
                document.addEventListener('mousemove', mouseHandler);
            }}
        </script>
    </body>
    </html>
    """
    
    components.html(html_code, height=600)
