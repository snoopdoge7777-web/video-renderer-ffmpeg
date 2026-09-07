import os
import subprocess
import requests
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render_video():
    try:
        data = request.json
        video_id = data.get('video_id', f"video_{os.urandom(4).hex()}")
        srt_content = data.get('srt', '')
        image_urls = data.get('image_urls', [])
        
        work_dir = f"/tmp/{video_id}"
        os.makedirs(work_dir, exist_ok=True)
        
        # 1. Guardar subtítulos
        srt_path = os.path.join(work_dir, "subtitles.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
            
        # 2. Descarga segura protegiendo contra valores nulos (NoneType)
        local_images = []
        session = requests.Session()
        
        for idx, img_url in enumerate(image_urls):
            # Si la URL viene vacía o es None, la ignoramos de forma segura
            if not img_url or not isinstance(img_url, str):
                continue
                
            img_filename = f"img_{idx:03d}.png"
            img_path = os.path.join(work_dir, img_filename)
            
            target_url = img_url
            if "drive.google.com" in img_url and "id=" in img_url:
                try:
                    file_id = img_url.split("id=")[1].split("&")[0]
                    target_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                except Exception:
                    pass
            
            r = session.get(target_url, allow_redirects=True)
            
            if r.status_code == 200 and b"<html" in r.content.lower() and "id=" in img_url:
                try:
                    file_id = img_url.split("id=")[1].split("&")[0]
                    target_url = f"https://drive.google.com/uc?export=download&confirm=1&id={file_id}"
                    r = session.get(target_url, allow_redirects=True)
                except Exception:
                    pass

            if r.status_code == 200 and b"<html" not in r.content.lower():
                with open(img_path, 'wb') as img_file:
                    img_file.write(r.content)
                local_images.append(img_path)
            else:
                print(f"Fallo al descargar la imagen {idx} desde {target_url}")
                
        if not local_images:
            return jsonify({"status": "error", "message": "No se pudo descargar ninguna imagen válida"}), 400
                
        output_video = os.path.join(work_dir, f"{video_id}.mp4")
        
        # 3. Comando FFmpeg
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
        
        # 4. Enviar el archivo binario del video directamente a n8n
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
