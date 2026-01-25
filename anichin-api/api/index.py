from flask import Flask, jsonify
import cloudscraper
from bs4 import BeautifulSoup

app = Flask(__name__)
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'android', 'desktop': False})

BASE_URL = "https://anichin.moe"

@app.route('/')
def home():
    return "Anichin API is Running! Pergi ke /api/home untuk data."

@app.route('/api/home')
def get_home_data():
    try:
        response = scraper.get(BASE_URL)
        if response.status_code != 200:
            return jsonify({"status": "error", "message": "Gagal ke Anichin"}), 500

        soup = BeautifulSoup(response.text, 'lxml')
        
        # Selector Home (Sesuai analisa kita kemaren)
        container = soup.select_one('div.listupd.normal')
        if not container:
            container = soup.select_one('div.listupd')
            
        articles = container.select('article.bs')
        
        data_anime = []
        for item in articles:
            try:
                title = item.select_one('.tt h2').text.strip()
                link = item.select_one('div.bsx a')['href']
                episode = item.select_one('span.epx').text.strip()
                img = item.select_one('img')['src']
                
                # Bersihin link gambar (kadang ada resize parameter)
                # Opsional, biar rapi aja
                if '?' in img:
                    img = img.split('?')[0]

                data_anime.append({
                    "title": title,
                    "episode": episode,
                    "thumb": img,
                    "link": link
                })
            except:
                continue
                
        return jsonify({
            "status": "success",
            "total": len(data_anime),
            "data": data_anime
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Ini biar bisa jalan di local (Termux) juga
if __name__ == '__main__':
    app.run(debug=True)