from flask import Flask, jsonify, request, render_template
import cloudscraper
from bs4 import BeautifulSoup
import base64

app = Flask(__name__)
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'android', 'desktop': False})
BASE_URL = "https://anichin.moe"

# --- ROUTE UTAMA (DASHBOARD) ---
@app.route('/')
def dashboard():
    base_url = request.url_root.rstrip('/')
    return render_template('dashboard.html', app_url=base_url)

# --- 1. HOME ---
# URL: /anime/donghua/home/1
@app.route('/anime/donghua/home/<page>')
def get_home(page):
    url = f"{BASE_URL}/page/{page}/" if page != '1' else BASE_URL
    
    try:
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        container = soup.select_one('div.listupd.normal') or soup.select_one('div.listupd')
        articles = container.select('article.bs')
        
        latest_release = []
        for item in articles:
            try:
                title = item.select_one('.tt h2').text.strip()
                link = item.select_one('div.bsx a')['href']
                img = item.select_one('img')
                ep_el = item.select_one('.epx')
                type_el = item.select_one('.typez')
                
                slug = link.replace(BASE_URL, "").strip('/') + '/'
                poster = img['src'].split('?')[0] if img else ""
                current_ep = ep_el.text.strip() if ep_el else "?"
                status = "Completed" if "Completed" in current_ep else "Ongoing"
                type_val = type_el.text.strip() if type_el else "Donghua"
                
                # Format Href buat APK
                href = f"/donghua/episode/{slug}"

                latest_release.append({
                    "title": title,
                    "slug": slug,
                    "poster": poster,
                    "status": status,
                    "type": type_val,
                    "current_episode": current_ep,
                    "href": href,
                    "anichinUrl": link
                })
            except: continue
            
        return jsonify({"status": "success", "latest_release": latest_release})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

# --- 2. SEARCH ---
# URL: /anime/donghua/search/naruto
@app.route('/anime/donghua/search/<query>')
def search_anime(query):
    url = f"{BASE_URL}/?s={query}"
    
    try:
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        articles = soup.select('article.bs')
        data = []
        
        for item in articles:
            try:
                title = item.select_one('.tt h2').text.strip()
                link = item.select_one('div.bsx a')['href']
                img = item.select_one('img')
                
                slug = link.replace(BASE_URL, "").strip('/')
                poster = img['src'].split('?')[0] if img else ""
                
                status_el = item.select_one('.status') or item.select_one('.epx')
                status = status_el.text.strip() if status_el else "Unknown"
                
                type_val = "Donghua" # Default
                
                # Logic href beda antara Anime dan Episode
                if "/anime/" in link:
                    href = f"/donghua/detail/{slug}/"
                else:
                    href = f"/donghua/episode/{slug}/"

                data.append({
                    "title": title,
                    "slug": slug,
                    "poster": poster,
                    "status": status,
                    "type": type_val,
                    "href": href,
                    "anichinUrl": link
                })
            except: continue
            
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

# --- 3. DETAIL ---
# URL: /anime/donghua/detail/anime/judul-anime/
# Pake <path:slug> biar dia bisa baca tanda '/' di dalam slug
@app.route('/anime/donghua/detail/<path:slug>')
def get_detail(slug):
    # Pastikan format slug bener (kadang ada yg ngirim tanpa slash awal/akhir)
    if not slug.startswith('/'): slug = '/' + slug
    if not slug.endswith('/'): slug += '/'
    
    url = BASE_URL + slug
    try:
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        info_div = soup.select_one('div.infox')
        title = info_div.select_one('h1.entry-title').text.strip()
        thumb = soup.select_one('div.thumb img')['src'].split('?')[0]
        
        genres = [g.text.strip() for g in info_div.select('.genxed a')]
        
        info_data = {}
        for span in info_div.select('.spe span'):
            text = span.text.strip()
            if ':' in text:
                key, val = text.split(':', 1)
                info_data[key.strip().lower()] = val.strip()
            
        synopsis = soup.select_one('div.entry-content').text.strip()
        
        ep_list = []
        for li in soup.select('div.eplister li'):
            ep_title = li.select_one('.epl-title').text.strip()
            ep_link = li.select_one('a')['href']
            # Bersihin slug episode
            ep_slug = ep_link.replace(BASE_URL, "").strip('/') + '/'
            
            ep_list.append({
                "title": ep_title,
                "slug": ep_slug,
                "href": f"/donghua/episode/{ep_slug}", # Format APK
                "date": li.select_one('.epl-date').text.strip(),
                "episode": li.select_one('.epl-num').text.strip()
            })
            
        return jsonify({
            "status": "success",
            "data": {
                "title": title,
                "poster": thumb,
                "genres": genres,
                "info": info_data,
                "synopsis": synopsis,
                "episode_list": ep_list
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

# --- 4. EPISODE STREAM ---
# URL: /anime/donghua/episode/judul-episode-sub-indo/
@app.route('/anime/donghua/episode/<path:slug>')
def get_episode_stream(slug):
    if not slug.startswith('/'): slug = '/' + slug
    if not slug.endswith('/'): slug += '/'
    
    url = BASE_URL + slug
    try:
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        title = soup.select_one('h1.entry-title').text.strip()
        streams = []
        
        # Default Player
        pembed = soup.select_one('#pembed iframe')
        if pembed:
            streams.append({"server": "Default", "url": pembed['src']})
            
        # Mirror Players
        for opt in soup.select('select.mirror option'):
            if not opt['value']: continue
            try:
                dec = base64.b64decode(opt['value']).decode('utf-8')
                iframe = BeautifulSoup(dec, 'lxml').find('iframe')
                if iframe:
                    streams.append({"server": opt.text.strip(), "url": iframe['src']})
            except: continue
            
        return jsonify({"status": "success", "title": title, "streams": streams})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)