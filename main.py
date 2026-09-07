import os
import subprocess
import base64
import json
import requests
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render_video():
    try:
        work_dir = f"/tmp/{os.urandom(4).hex()}"
        os.makedirs(work_dir, exist_ok=True)
        
        data = request.get_json(silent=True) or {}
        print("DATOS RECIBIDOS:", data)
        
        video_id = data.get('video_id', 'video_default')
        srt_content = data.get('srt_content', data.get('srt', ''))
        image_urls_raw = data.get('image_urls', [])
        
        # --- BLINDAJE PARA IMAGE_URLS ---
        image_urls = []
        if isinstance(image_urls_raw, list):
            image_urls = image_urls_raw
        elif isinstance(image_urls_raw, str):
            try:
                image_urls = json.loads(image_urls_raw)
            except:
                if "," in image_urls_raw:
                    image_urls = [u.strip() for u in image_urls_raw.split(",")]
                else:
                    image_urls = [image_urls_raw]
        
        local_images = []
        
        for valid_idx, img_item in enumerate(image_urls):
            if not img_item or not isinstance(img_item, str):
                continue
            
            img_filename = f"img_{valid_idx:03d}.png"
            img_path = os.path.join(work_dir, img_filename)
            
            if img_item.startswith('data:image'):
                header, encoded = img_item.split(",", 1)
                decoded_bytes = base64.b64decode(encoded)
                with open(img_path, "wb") as fh:
                    fh.write(decoded_bytes)
                local_images.append(img_path)
            elif img_item.startswith('http'):
                r = requests.get(img_item)
                if r.status_code == 200 and b"<html" not in r.content.lower():
                    with open(img_path, "wb") as fh:
                        fh.write(r.content)
                    local_images.append(img_path)

        srt_path = os.path.join(work_dir, "subtitles.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
            
        if not local_images:
            return jsonify({
                "status": "error", 
                "message": f"No se procesaron imágenes válidas. Se recibió: {image_urls_raw}"
            }), 400
                
        output_video = os.path.join(work_dir, f"{video_id}.mp4")
        
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
        
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        return send_file(output_video, mimetype='video/mp4', as_attachment=True, download_name=f"{video_id}.mp4")
        
    except subprocess.CalledProcessError as e:
        print("FFMPEG ERROR:", e.stderr)
        return jsonify({
            "status": "error", 
            "message": f"Error en FFmpeg: {e.stderr}"
        }), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
