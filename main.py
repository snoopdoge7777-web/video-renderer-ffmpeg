import os
import subprocess
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render_video():
    try:
        data = request.json
        video_id = data.get('video_id', 'output_video')
        srt_content = data.get('srt_content')
        image_urls = data.get('image_urls', []) # Lista de URLs de las imágenes de Google Drive
        
        work_dir = f"/tmp/{video_id}"
        os.makedirs(work_dir, exist_ok=True)
        
        # 1. Guardar subtítulos
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
                
        output_video = os.path.join(work_dir, f"{video_id}.mp4")
        
        # 3. Comando FFmpeg para unir imágenes (ej: 3 segundos por imagen) y quemar subtítulos
        # Usamos concat demuxer o un filtro de fotogramas estables con subtítulos incrustados
        # Filtro de subtítulos requiere escapar rutas en FFmpeg si es necesario
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-framerate", "1/3", # 3 segundos por imagen
            "-i", os.path.join(work_dir, "img_%03d.png"),
            "-i", srt_path,
            "-c:v", "libx264",
            "-vf", f"subtitles={srt_path}:force_style='FontSize=24,PrimaryColour=&H00FFFF&'",
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
