import re

with open("frontend/components/hero.py", "r", encoding="utf-8") as f:
    content = f.read()

# The JS block is inside an f-string, so braces must be doubled.
js_unescaped = """
            // Cursor tracking logic
            let currentFrame = Math.floor(urls.length / 2);
            let targetFrame = currentFrame;
            
            function animate() {
                if (Math.abs(targetFrame - currentFrame) > 0.1) {
                    currentFrame += (targetFrame - currentFrame) * 0.12;
                    drawFrame(Math.floor(currentFrame));
                }
                requestAnimationFrame(animate);
            }
            animate();

            const handleMove = (x, width) => {
                if (images.length === 0) return;
                const percent = Math.max(0, Math.min(1, x / width));
                targetFrame = percent * (images.length - 1);
            };

            const mouseHandler = (e) => {
                handleMove(e.clientX, window.parent.innerWidth || window.innerWidth);
            };

            try {
                if (window.parent && window.parent.document) {
                    if (window.parent._heroMouseHandler) {
                        window.parent.document.removeEventListener('mousemove', window.parent._heroMouseHandler);
                    }
                    window.parent._heroMouseHandler = mouseHandler;
                    window.parent.document.addEventListener('mousemove', mouseHandler);
                }
            } catch (e) {
                // CORS or parent access failed, fallback to local document
                document.addEventListener('mousemove', mouseHandler);
            }
"""

js_escaped = """
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
"""

# Replace exactly that block
if js_unescaped.strip() in content:
    content = content.replace(js_unescaped.strip(), js_escaped.strip())
else:
    # Manual replace just in case indentation was different
    content = content.replace("function animate() {", "function animate() {{")
    content = content.replace("if (Math.abs(targetFrame - currentFrame) > 0.1) {", "if (Math.abs(targetFrame - currentFrame) > 0.1) {{")
    content = content.replace("drawFrame(Math.floor(currentFrame));\n                }", "drawFrame(Math.floor(currentFrame));\n                }}")
    content = content.replace("requestAnimationFrame(animate);\n            }", "requestAnimationFrame(animate);\n            }}")
    content = content.replace("const handleMove = (x, width) => {", "const handleMove = (x, width) => {{")
    content = content.replace("targetFrame = percent * (images.length - 1);\n            };", "targetFrame = percent * (images.length - 1);\n            }};")
    content = content.replace("const mouseHandler = (e) => {", "const mouseHandler = (e) => {{")
    content = content.replace("handleMove(e.clientX, window.parent.innerWidth || window.innerWidth);\n            };", "handleMove(e.clientX, window.parent.innerWidth || window.innerWidth);\n            }};")
    content = content.replace("try {", "try {{")
    content = content.replace("if (window.parent && window.parent.document) {", "if (window.parent && window.parent.document) {{")
    content = content.replace("if (window.parent._heroMouseHandler) {", "if (window.parent._heroMouseHandler) {{")
    content = content.replace("window.parent.document.removeEventListener('mousemove', window.parent._heroMouseHandler);\n                    }", "window.parent.document.removeEventListener('mousemove', window.parent._heroMouseHandler);\n                    }}")
    content = content.replace("window.parent.document.addEventListener('mousemove', mouseHandler);\n                }", "window.parent.document.addEventListener('mousemove', mouseHandler);\n                }}")
    content = content.replace("} catch (e) {", "}} catch (e) {{")
    content = content.replace("document.addEventListener('mousemove', mouseHandler);\n            }", "document.addEventListener('mousemove', mouseHandler);\n            }}")

with open("frontend/components/hero.py", "w", encoding="utf-8") as f:
    f.write(content)
