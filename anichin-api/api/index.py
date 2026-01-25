from flask import Flask, jsonify, request
import cloudscraper
from bs4 import BeautifulSoup
import base64

app = Flask(__name__)
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'android', 'desktop': False})

BASE_URL = "https://anichin.moe"

@app.route('/')
def index():
    return jsonify({
        "message": "Anichin API Private",
        "endpoints": [
            "/api/home",
            "/api/episode?slug=/judul-episode-lo"
        ]
    })

# --- 1. ENDPOINT HOME (YANG TADI) ---
@app.route('/api/home')
def get_home():
    try:
        response = scraper.get(BASE_URL)
        soup = BeautifulSoup(response.text, 'lxml')
        
        container = soup.select_one('div.listupd.normal') or soup.select_one('div.listupd')
        articles = container.select('article.bs')
        
        data_anime = []
        for item in articles:
            try:
                title = item.select_one('.tt h2').text.strip()
                link = item.select_one('div.bsx a')['href']
                episode = item.select_one('span.epx').text.strip()
                img = item.select_one('img')['src'].split('?')[0]
                
                # Kita ambil slug-nya aja (bagian belakang URL) biar rapi
                # Contoh link: https://anichin.moe/episode-1/ -> slug: /episode-1/
                slug = link.replace(BASE_URL, "")

                data_anime.append({
                    "title": title,
                    "episode": episode,
                    "thumb": img,
                    "slug": slug 
                })
            except:
                continue
                
        return jsonify({"status": "success", "data": data_anime})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- 2. ENDPOINT EPISODE (INI YANG BARU) ---
@app.route('/api/episode')
def get_episode():
    # Cara pakenya: /api/episode?slug=/judul-episode/
    slug = request.args.get('slug')
    
    if not slug:
        return jsonify({"status": "error", "message": "Mana slug-nya woy?"}), 400
    
    target_url = BASE_URL + slug
    
    try:
        response = scraper.get(target_url)
        if response.status_code != 200:
            return jsonify({"status": "error", "message": "Link mati"}), 404

        soup = BeautifulSoup(response.text, 'lxml')
        
        # Ambil Judul Episode
        title_tag = soup.select_one('h1.entry-title')
        title = title_tag.text.strip() if title_tag else "Unknown Title"
        
        video_list = []

        # A. Cari Default Player (Biasanya OK.ru)
        default_iframe = soup.select_one('#pembed iframe')
        if default_iframe:
            video_list.append({
                "server": "Default",
                "type": "embed",
                "url": default_iframe['src']
            })

        # B. Cari Mirror (Base64 Encoded)
        mirror_options = soup.select('select.mirror option')
        for option in mirror_options:
            server_name = option.text.strip()
            encrypted_code = option['value']
            
            # Skip opsi "Select Video Server"
            if not encrypted_code: continue
            
            try:
                # Decode Base64
                decoded_html = base64.b64decode(encrypted_code).decode('utf-8')
                soup_mirror = BeautifulSoup(decoded_html, 'lxml')
                iframe = soup_mirror.find('iframe')
                
                if iframe:
                    video_list.append({
                        "server": server_name,
                        "type": "embed", # Tandanya ini harus di-extract lagi di HP
                        "url": iframe['src']
                    })
            except:
                continue

        return jsonify({
            "status": "success",
            "slug": slug,
            "title": title,
            "videos": video_list
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Local Run
if __name__ == '__main__':
    app.run(debug=True)