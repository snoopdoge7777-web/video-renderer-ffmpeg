import os
import subprocess
import base64
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render_video():
    try:
        work_dir = f"/tmp/{os.urandom(4).hex()}"
        os.makedirs(work_dir, exist_ok=True)
        
        video_id = "video_default"
        srt_content = ""
        local_images = []

        # CASO A: Recibe archivos binarios directamente (Multipart/form-data desde n8n)
        if request.files:
            video_id = request.form.get('video_id', f"video_{os.urandom(4).hex()}")
            srt_content = request.form.get('srt', request.form.get('srt_content', ''))
            
            files = request.files.getlist('images')
            for idx, file in enumerate(files):
                img_filename = f"img_{idx:03d}.png"
                img_path = os.path.join(work_dir, img_filename)
                file.save(img_path)
                local_images.append(img_path)

        # CASO B: Recibe JSON (con URLs o Base64)
        elif request.is_json:
            data = request.json
            video_id = data.get('video_id', f"video_{os.urandom(4).hex()}")
            srt_content = data.get('srt', data.get('srt_content', ''))
            image_urls = data.get('image_urls', [])
            
            for idx, img_item in enumerate(image_urls):
                if not img_item:
                    continue
                img_filename = f"img_{idx:03d}.png"
                img_path = os.path.join(work_dir, img_filename)
                
                # Si viene en formato Base64
                if isinstance(img_item, str) and img_item.startswith('data:image'):
                    header, encoded = img_item.split(",", 1)
                    with open(img_path, "wb") as fh:
                        fh.write(base64.b64decode(encoded))
                    local_images.append(img_path)
                else:
                    # Intento de respaldo por URL clásica
                    import requests
                    r = requests.get(img_item)
                    if r.status_code == 200 and b"<html" not in r.content.lower():
                        with open(img_path, "wb") as fh:
                            fh.write(r.content)
                        local_images.append(img_path)

        # 1. Guardar subtítulos
        srt_path = os.path.join(work_dir, "subtitles.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
            
        if not local_images:
            return jsonify({"status": "error", "message": "No se pudo procesar ninguna imagen válida"}), 400
                
        output_video = os.path.join(work_dir, f"{video_id}.mp4")
        
        # 2. Comando FFmpeg
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-framerate", "1/3",
            "-i", os.path.join(work_dir, "img_%03d.png"),
            "-c:v", "libx264",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-pix_fmt", "yuv420p",
            output_video
        ]
        
        subprocess.run(ffmpeg_cmd, check=True)
        
        # 3. Enviar video resultante
        return send_file(
            output_video, 
            mimetype='video/mp4', 
            as_attachment=True, 
            download_name=f"{video_id}.mp4"
        )
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
