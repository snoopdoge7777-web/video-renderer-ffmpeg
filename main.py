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
            
            # Iterar sobre todas las keys de archivos que envíe n8n
            for key in request.files:
                files = request.files.getlist(key)
                for file in files:
                    file_bytes = file.read()
                    
                    # Verificar si los primeros bytes corresponden a texto o subtítulos (ej. empieza con números o '1')
                    head_preview = file_bytes[:20].decode('utf-8', errors='ignore')
                    if "00:" in head_preview or head_preview.startswith("1\n") or head_preview.startswith("1\r"):
                        print(f"[ADVERTENCIA] Se ignoró un campo que parece texto/SRT en la key '{key}': {head_preview}")
                        continue
                        
                    # Validar tamaño mínimo de una imagen real
                    if len(file_bytes) > 100:
                        img_filename = f"img_{len(local_images):03d}.png"
                        img_path = os.path.join(work_dir, img_filename)
                        with open(img_path, "wb") as f:
                            f.write(file_bytes)
                        local_images.append(img_path)

        # CASO B: Recibe JSON (con URLs o Base64)
        elif request.is_json:
            data = request.json
            video_id = data.get('video_id', f"video_{os.urandom(4).hex()}")
            srt_content = data.get('srt', data.get('srt_content', ''))
            image_urls = data.get('image_urls', [])
            
            for valid_idx, img_item in enumerate(image_urls):
                if not img_item:
                    continue
                img_filename = f"img_{valid_idx:03d}.png"
                img_path = os.path.join(work_dir, img_filename)
                
                if isinstance(img_item, str) and img_item.startswith('data:image'):
                    header, encoded = img_item.split(",", 1)
                    decoded_bytes = base64.b64decode(encoded)
                    with open(img_path, "wb") as fh:
                        fh.write(decoded_bytes)
                    local_images.append(img_path)
                else:
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
            return jsonify({
                "status": "error", 
                "message": "No se encontraron imágenes válidas. n8n está enviando texto (SRT) en lugar de binarios de imagen."
            }), 400
                
        output_video = os.path.join(work_dir, f"{video_id}.mp4")
        
        # 2. Comando FFmpeg
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-framerate", "1/3",
            "-start_number", "0",
            "-i", os.path.join(work_dir, "img_%03d.png"),
            "-c:v", "libx264",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-pix_fmt", "yuv420p",
            output_video
        ]
        
        try:
            subprocess.run(
                ffmpeg_cmd, 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
        except subprocess.CalledProcessError as e:
            return jsonify({
                "status": "error", 
                "message": f"Error de FFmpeg: {e.stderr.strip()}"
            }), 500
        
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
