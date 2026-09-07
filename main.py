import os
import subprocess
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render_video():
    try:
        data = request.json
        # Genera un ID único si n8n no lo envía para evitar conflictos en /tmp/
        video_id = data.get('video_id', f"video_{os.urandom(4).hex()}")
        
        # Corregido para que coincida exactamente con la clave 'srt' que configuramos en n8n
        srt_content = data.get('srt', '')
        image_urls = data.get('image_urls', [])
        
        work_dir = f"/tmp/{video_id}"
        os.makedirs(work_dir, exist_ok=True)
        
        # 1. Guardar subtítulos si existen
        srt_path = os.path.join(work_dir, "subtitles.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
            
        # 2. Descargar las imágenes ordenadas
        local_images = []
        for idx, img_url in enumerate(image_urls):
            img_path = os.path.join(work_dir, f"img_{idx:03d}.png")
            r = requests.get(img_url)
            if r.status_code == 200:
                with open(img_path, 'wb') as img_file:
                    img_file.write(r.content)
                local_images.append(img_path)
                
        if not local_images:
            return jsonify({"status": "error", "message": "No se pudo descargar ninguna imagen válida"}), 400
                
        output_video = os.path.join(work_dir, f"{video_id}.mp4")
        
        # 3. Comando FFmpeg con filtro de escala para asegurar dimensiones pares (evita errores de libx264)
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
        
        return jsonify({
            "status": "success",
            "message": "Video renderizado con éxito",
            "video_path": output_video
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
