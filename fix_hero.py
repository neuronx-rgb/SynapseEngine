import re

with open("frontend/components/hero.py", "r", encoding="utf-8") as f:
    content = f.read()

new_script = """
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

# Replace script part
content = re.sub(r'// Cursor tracking logic.*?</script>', new_script.strip() + '\n        </script>', content, flags=re.DOTALL)

# Adjust height
content = content.replace('components.html(html_code, height=400)', 'components.html(html_code, height=600)')

with open("frontend/components/hero.py", "w", encoding="utf-8") as f:
    f.write(content)
