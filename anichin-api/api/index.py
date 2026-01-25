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

# --- UPDATE API 2: SEARCH (SUPPORT PAGINATION) ---
# URL: /anime/donghua/search/naruto/1
@app.route('/anime/donghua/search/<query>/<page>')
def search_anime(query, page):
    # Logic URL Search WordPress:
    # Page 1: https://anichin.moe/?s=katakunci
    # Page 2: https://anichin.moe/page/2/?s=katakunci
    
    if page == '1':
        url = f"{BASE_URL}/?s={query}"
    else:
        url = f"{BASE_URL}/page/{page}/?s={query}"
    
    try:
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        articles = soup.select('article.bs')
        data = []
        
        for item in articles:
            try:
                title_el = item.select_one('.tt h2')
                link_el = item.select_one('div.bsx a')
                img_el = item.select_one('img')
                
                if not title_el or not link_el: continue
                
                title = title_el.text.strip()
                anichinUrl = link_el['href']
                
                # Bersihin Slug
                raw_slug = anichinUrl.replace(BASE_URL, "").strip('/')
                slug = raw_slug.replace('anime/', '')
                
                poster = img_el['src'].split('?')[0] if img_el else ""
                
                # Metadata
                status_el = item.select_one('.status') or item.select_one('.epx')
                status = status_el.text.strip() if status_el else "Ongoing"
                if "Completed" in status: status = "Completed"
                
                type_el = item.select_one('.typez')
                type_val = type_el.text.strip() if type_el else "Donghua"
                
                sub_el = item.select_one('.sb')
                sub_val = sub_el.text.strip() if sub_el else "Sub"
                
                # Routing Href
                if '/anime/' in anichinUrl:
                    href = f"/donghua/detail/{slug}"
                else:
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
            
        return jsonify({
            "status": "success", 
            "query": query,
            "page": page,
            "data": data
        })
        
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

# --- UPDATE API 4: EPISODE STREAM (STRUCTURE FIXED) ---
@app.route('/anime/donghua/episode/<path:slug>')
def get_episode_stream(slug):
    # Normalisasi slug
    if not slug.startswith('/'): slug = '/' + slug
    if not slug.endswith('/'): slug += '/'
    
    target_url = BASE_URL + slug
    
    try:
        response = scraper.get(target_url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 1. Judul Episode
        ep_title_el = soup.select_one('h1.entry-title')
        ep_title = ep_title_el.text.strip() if ep_title_el else "Unknown Title"
        
        # 2. STREAMING LINKS
        servers = []
        
        # A. Default Player (Main)
        pembed = soup.select_one('#pembed iframe')
        if pembed:
            # Coba deteksi nama server dari src
            src = pembed['src']
            name = "Default"
            if "ok.ru" in src: name = "OK.ru"
            elif "dailymotion" in src: name = "Dailymotion"
            elif "rumble" in src: name = "Rumble"
            
            servers.append({"name": name, "url": src})
            
        # B. Mirror Players (Decode Base64)
        for opt in soup.select('select.mirror option'):
            if not opt['value']: continue
            try:
                dec = base64.b64decode(opt['value']).decode('utf-8')
                iframe = BeautifulSoup(dec, 'lxml').find('iframe')
                if iframe:
                    servers.append({"name": opt.text.strip(), "url": iframe['src']})
            except: continue
            
        streaming_data = {
            "main_url": servers[0] if servers else None,
            "servers": servers
        }

        # 3. DOWNLOAD URL
        download_data = {}
        dl_containers = soup.select('.soraurlx')
        
        for dl in dl_containers:
            try:
                # Ambil resolusi dari tag strong (360p, 480p)
                # Di HTML lo formatnya: <strong>360p</strong>
                res_tag = dl.select_one('strong')
                if not res_tag: continue
                
                resolution = res_tag.text.strip().lower().replace(' ', '') # 360p
                
                links = {}
                for a in dl.select('a'):
                    host = a.text.strip()
                    link = a['href']
                    links[host] = link
                
                # Format key: download_url_360p
                key = f"download_url_{resolution}"
                download_data[key] = links
            except: continue

        # 4. DONGHUA DETAILS (Info Series)
        details_data = {}
        headlist = soup.select_one('.headlist')
        if headlist:
            d_title_el = headlist.select_one('.det h2 a')
            d_thumb_el = headlist.select_one('.thumb img')
            
            d_title = d_title_el.text.strip()
            d_link = d_title_el['href']
            d_slug = d_link.replace(BASE_URL, "").strip('/').replace('anime/', '')
            d_poster = d_thumb_el['src'].split('?')[0] if d_thumb_el else ""
            
            # Ambil Tanggal Rilis
            date_el = soup.select_one('.year .updated')
            released = date_el.text.strip() if date_el else "-"
            
            # Type (Gabungin semua text di span .epx buat meniru format user)
            type_text = "Donghua"
            epx_el = soup.select_one('.epx')
            if epx_el:
                type_text = epx_el.text.strip() # Isinya biasanya "Donghua Sub"

            details_data = {
                "title": d_title,
                "slug": d_slug,
                "poster": d_poster,
                "type": type_text,
                "released": released,
                "uploader": "admin",
                "href": f"/donghua/detail/{d_slug}",
                "anichinUrl": d_link
            }

        # 5. NAVIGATION
        nav_data = {"all_episodes": None, "previous_episode": None, "next_episode": None}
        nav_div = soup.select_one('.naveps')
        if nav_div:
            # All Episodes
            all_a = nav_div.select_one('a[href*="/anime/"]')
            if all_a:
                all_slug = all_a['href'].replace(BASE_URL, "").strip('/').replace('anime/', '')
                nav_data["all_episodes"] = {
                    "slug": all_slug,
                    "href": f"/donghua/detail/{all_slug}",
                    "anichinUrl": all_a['href']
                }
            
            # Prev Episode
            prev_a = nav_div.select_one('a[rel="prev"]')
            if prev_a:
                p_slug = prev_a['href'].replace(BASE_URL, "").strip('/')
                nav_data["previous_episode"] = {
                    "episode": "Previous Episode", # Text default krn gak ada di tombol
                    "slug": p_slug,
                    "href": f"/donghua/episode/{p_slug}",
                    "anichinUrl": prev_a['href']
                }
            
            # Next Episode
            # Cek apakah ada link next atau cuma span nolink
            next_a = nav_div.select_one('a[rel="next"]')
            # Fallback manual check text
            if not next_a:
                for a in nav_div.select('a'):
                    if "Next" in a.text: next_a = a; break;
            
            if next_a:
                n_slug = next_a['href'].replace(BASE_URL, "").strip('/')
                nav_data["next_episode"] = {
                    "episode": "Next Episode",
                    "slug": n_slug,
                    "href": f"/donghua/episode/{n_slug}",
                    "anichinUrl": next_a['href']
                }

        # 6. EPISODES LIST
        episodes_list_data = []
        # Target list di bawah player (#singlepisode .episodelist)
        ep_container = soup.select('#singlepisode .episodelist li')
        
        for li in ep_container:
            try:
                a_tag = li.select_one('a')
                if not a_tag: continue
                
                e_title = li.select_one('.playinfo h3').text.strip()
                e_link = a_tag['href']
                e_slug = e_link.replace(BASE_URL, "").strip('/')
                
                episodes_list_data.append({
                    "episode": e_title,
                    "slug": e_slug,
                    "href": f"/donghua/episode/{e_slug}",
                    "anichinUrl": e_link
                })
            except: continue

        # Return Final JSON
        return jsonify({
            "status": "success",
            # "creator": "Sanka Vollerei", # DIHAPUS SESUAI REQUEST
            "episode": ep_title,
            "streaming": streaming_data,
            "download_url": download_data,
            "donghua_details": details_data,
            "navigation": nav_data,
            "episodes_list": episodes_list_data
        })

    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500
        
# --- UPDATE API 5: COMPLETED (ROUTE BARU) ---
# URL: /anime/donghua/completed/1
@app.route('/anime/donghua/completed/<page>')
def get_completed(page):
    # Logic URL Completed di Anichin
    # Page 1: https://anichin.moe/completed/
    # Page 2: https://anichin.moe/completed/page/2/
    
    if page == '1':
        url = f"{BASE_URL}/completed/"
    else:
        url = f"{BASE_URL}/completed/page/{page}/"
    
    try:
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Cari container list (Biasanya class .listupd)
        container = soup.select_one('div.listupd')
        articles = container.select('article.bs')
        
        completed_donghua = []
        for item in articles:
            try:
                # 1. Ambil Data Dasar
                title_el = item.select_one('.tt h2')
                link_el = item.select_one('div.bsx a')
                img_el = item.select_one('img')
                
                if not title_el or not link_el: continue
                
                title = title_el.text.strip()
                anichinUrl = link_el['href']
                
                # 2. Slug & Href
                # Link Completed biasanya ke detail anime: /anime/judul/
                # Slug yang dimau: the-dragon-soul/ (ada slash belakang)
                slug = anichinUrl.replace(BASE_URL, "").strip('/')
                slug = slug.replace('anime/', '') # Jaga-jaga kalo ada prefix anime
                if not slug.endswith('/'): slug += '/'
                
                href = f"/donghua/detail/{slug}"
                
                # 3. Poster
                poster = img_el['src'].split('?')[0] if img_el else ""
                
                # 4. Status (Hardcode Completed sesuai request JSON lo)
                status = "Completed"

                completed_donghua.append({
                    "title": title,
                    "slug": slug,
                    "poster": poster,
                    "status": status,
                    "href": href,
                    "anichinUrl": anichinUrl
                })
            except: continue
            
        return jsonify({
            "status": "success",
            # "creator": "Sanka Vollerei", # DIHAPUS
            "completed_donghua": completed_donghua
        })
        
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500
        
# --- UPDATE API 6: SCHEDULE (ROUTE BARU) ---
@app.route('/anime/donghua/schedule')
def get_schedule():
    url = f"{BASE_URL}/schedule/"
    
    try:
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        schedule_data = []
        
        # Loop setiap hari (Monday - Sunday)
        # Class-nya format: .schedulepage.sch_sunday, .sch_monday, dst
        days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        
        for day in days:
            day_container = soup.select_one(f'.schedulepage.sch_{day}')
            if not day_container: continue
            
            day_name = day.capitalize() # Sunday
            anime_list = []
            
            # Ambil semua anime di hari itu
            articles = day_container.select('.bsx')
            for item in articles:
                try:
                    title_el = item.select_one('.tt')
                    link_el = item.select_one('a')
                    img_el = item.select_one('img')
                    
                    if not title_el: continue
                    
                    title = title_el.text.strip()
                    anichinUrl = link_el['href']
                    
                    # Bersihin Slug (Hapus base url + slash)
                    slug = anichinUrl.replace(BASE_URL, "").strip('/')
                    if not slug.endswith('/'): slug += '/'
                    
                    # Cek Link Tipe (Anime Detail atau Episode)
                    # Di schedule biasanya link ke detail anime (/anime/...)
                    # Tapi kadang ada yg link langsung ke episode
                    if '/anime/' in anichinUrl:
                        href = f"/donghua/detail/{slug.replace('anime/', '')}"
                    else:
                        href = f"/donghua/episode/{slug}"
                    
                    poster = img_el['src'].split('?')[0] if img_el else ""
                    
                    # Ambil Waktu Tayang & Episode
                    # <span class="epx cndwn" data-rlsdt="1769354519">at 13:50</span>
                    # <span class="sb Sub">14</span>
                    time_el = item.select_one('.epx')
                    time_release = time_el.text.replace('at ', '').strip() if time_el else "?"
                    timestamp = time_el.get('data-rlsdt') if time_el else None
                    
                    ep_el = item.select_one('.sb')
                    episode = ep_el.text.strip() if ep_el else "?"

                    anime_list.append({
                        "title": title,
                        "slug": slug,
                        "poster": poster,
                        "episode": episode,
                        "time": time_release,
                        "timestamp": timestamp, # Unix timestamp (berguna buat countdown di APK)
                        "href": href,
                        "anichinUrl": anichinUrl
                    })
                except: continue
            
            if anime_list:
                schedule_data.append({
                    "day": day_name,
                    "anime_list": anime_list
                })
            
        return jsonify({
            "status": "success",
            "schedule": schedule_data
        })
        
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)