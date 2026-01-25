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

# --- UPDATE API 2: SEARCH (FORMAT APK LENGKAP) ---
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
                # 1. Ambil Elemen Dasar
                title_el = item.select_one('.tt h2')
                link_el = item.select_one('div.bsx a')
                img_el = item.select_one('img')
                
                if not title_el or not link_el: continue
                
                title = title_el.text.strip()
                anichinUrl = link_el['href']
                
                # 2. Bersihin Slug
                # Anichin URL biasanya: https://anichin.moe/anime/judul/ atau https://anichin.moe/judul-episode-1/
                raw_slug = anichinUrl.replace(BASE_URL, "").strip('/')
                
                # Hapus prefix 'anime/' kalau ada, biar slug-nya bersih
                slug = raw_slug.replace('anime/', '')
                
                # 3. Poster HD
                poster = img_el['src'].split('?')[0] if img_el else ""
                
                # 4. Ambil Metadata (Status, Type, Sub)
                
                # STATUS: Prioritas ambil .status (Completed), kalau gak ada ambil .epx (Ep 10 / Ongoing)
                status_el = item.select_one('.status')
                epx_el = item.select_one('.epx')
                
                status = "Ongoing" # Default
                if status_el:
                    status = status_el.text.strip() # "Completed"
                elif epx_el:
                    # Kalau isinya angka episode, berarti Ongoing
                    status = "Ongoing"
                
                # TYPE: Donghua / Live Action / Movie
                type_el = item.select_one('.typez')
                type_val = type_el.text.strip() if type_el else "Donghua"
                
                # SUB: Sub Indo / Raw
                sub_el = item.select_one('.sb')
                sub_val = sub_el.text.strip() if sub_el else "Sub"
                
                # 5. Tentukan Href (Routing APK)
                # Kalau link aslinya ada kata '/anime/', berarti itu halaman DETAIL SERIES
                if '/anime/' in anichinUrl:
                    href = f"/donghua/detail/{slug}"
                else:
                    # Kalau gak ada, berarti itu halaman EPISODE
                    href = f"/donghua/episode/{slug}"

                data.append({
                    "title": title,
                    "slug": slug,
                    "poster": poster,
                    "status": status,
                    "type": type_val,
                    "sub": sub_val,
                    "href": href,
                    "anichinUrl": anichinUrl
                })
            except: continue
            
        return jsonify({"status": "success", "data": data})
        
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

# --- UPDATE API 3: DETAIL ANIME (FULL DATA SESUAI REQUEST) ---
@app.route('/anime/donghua/detail/<path:slug>')
def get_detail(slug):
    # Bersihin slug
    if not slug.startswith('/'): slug = '/' + slug
    if not slug.endswith('/'): slug += '/'
    
    url = BASE_URL + slug
    try:
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 1. Info Container Utama
        info_div = soup.select_one('div.infox')
        if not info_div: return jsonify({"status": "error", "msg": "Konten tidak ditemukan"}), 404

        # 2. Parsing Data Dasar
        title = info_div.select_one('h1.entry-title').text.strip()
        poster = soup.select_one('div.thumb img')['src'].split('?')[0]
        
        # Ambil Alternative Title
        alter_el = soup.select_one('span.alter')
        alter_title = alter_el.text.strip() if alter_el else ""
        
        # Ambil Rating
        rating_el = soup.select_one('.rating strong')
        rating = rating_el.text.replace("Rating", "").strip() if rating_el else "0"

        # 3. Parsing Info Detail (.spe spans)
        # Kita masukin ke dictionary dulu biar gampang dipanggil
        raw_info = {}
        for span in info_div.select('.spe span'):
            text = span.text.strip()
            if ':' in text:
                key, val = text.split(':', 1)
                raw_info[key.strip()] = val.strip()
        
        # Mapping ke variable sesuai request JSON lo
        status = raw_info.get('Status', 'Unknown')
        studio = raw_info.get('Studio', '-')
        network = raw_info.get('Network', '-')
        released = raw_info.get('Released', '-')
        duration = raw_info.get('Duration', '-')
        type_val = raw_info.get('Type', 'Donghua')
        season = raw_info.get('Season', '-')
        country = raw_info.get('Country', 'China')
        # Kadang ada "Posted by" atau "Updated on"
        updated_on = raw_info.get('Updated on', released) 
        
        # Total episode (Coba cari 'Episodes' di info, kalau gak ada hitung manual nanti)
        episodes_count = raw_info.get('Episodes', '?')

        # 4. Genres List
        genres_data = []
        for g in info_div.select('.genxed a'):
            g_name = g.text.strip()
            g_link = g['href']
            # Slug genre: https://anichin.moe/genres/action/ -> action
            g_slug = g_link.strip('/').split('/')[-1]
            
            genres_data.append({
                "name": g_name,
                "slug": g_slug,
                "href": f"/donghua/genres/{g_slug}",
                "anichinUrl": g_link
            })

        # 5. Synopsis
        synopsis_div = soup.select_one('div.entry-content')
        synopsis = synopsis_div.text.strip() if synopsis_div else ""

        # 6. Episode List
        episodes_list = []
        ep_elements = soup.select('div.eplister li')
        
        # Update episode count kalau di info tadi '?'
        if episodes_count == '?':
            episodes_count = str(len(ep_elements))

        for li in ep_elements:
            ep_title = li.select_one('.epl-title').text.strip()
            ep_link = li.select_one('a')['href']
            
            # Slug episode: https://anichin.moe/judul-episode-1/ -> judul-episode-1
            ep_slug = ep_link.replace(BASE_URL, "").strip('/')
            
            episodes_list.append({
                "episode": ep_title,
                "slug": ep_slug,
                "href": f"/donghua/episode/{ep_slug}",
                "anichinUrl": ep_link
            })

        # 7. RAKIT JSON FINAL
        result = {
            "status": status,
            "title": title,
            "alter_title": alter_title,
            "poster": poster,
            "rating": rating,
            "studio": studio,
            "network": network,
            "released": released,
            "duration": duration,
            "type": type_val,
            "episodes_count": episodes_count,
            "season": season,
            "country": country,
            "released_on": released, # Biasanya sama dengan released
            "updated_on": updated_on,
            "genres": genres_data,
            "synopsis": synopsis,
            "episodes_list": episodes_list
        }

        return jsonify(result)
        
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