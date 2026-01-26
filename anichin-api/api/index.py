from flask import Flask, jsonify, request, render_template
import cloudscraper
from bs4 import BeautifulSoup
import base64
import re
import json

app = Flask(__name__)

# Setup Scraper
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'android', 'desktop': False})
BASE_URL = "https://anichin.moe"

# --- ROUTE DASHBOARD & WEB ---
@app.route('/')
def dashboard():
    base_url = request.url_root.rstrip('/')
    return render_template('dashboard.html', app_url=base_url)

@app.route('/app')
def web_app():
    return render_template('index.html')

# --- 1. HOME ---
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
@app.route('/anime/donghua/search/<query>/<page>')
def search_anime(query, page):
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
                title = item.select_one('.tt h2').text.strip()
                link = item.select_one('div.bsx a')['href']
                img = item.select_one('img')
                
                raw_slug = link.replace(BASE_URL, "").strip('/')
                slug = raw_slug.replace('anime/', '')
                poster = img['src'].split('?')[0] if img else ""
                
                status_el = item.select_one('.status') or item.select_one('.epx')
                status = status_el.text.strip() if status_el else "Ongoing"
                if "Completed" in status: status = "Completed"
                
                type_val = "Donghua"
                sub_val = "Sub"
                
                if '/anime/' in link:
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
                    "anichinUrl": link
                })
            except: continue
            
        return jsonify({"status": "success", "page": page, "data": data})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

# --- 3. DETAIL ---
@app.route('/anime/donghua/detail/<path:slug>')
def get_detail(slug):
    if not slug.startswith('/'): slug = '/' + slug
    if not slug.endswith('/'): slug += '/'
    
    url = BASE_URL + slug
    try:
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        info_div = soup.select_one('div.infox')
        if not info_div: return jsonify({"status": "error", "msg": "Not found"}), 404

        title = info_div.select_one('h1.entry-title').text.strip()
        poster = soup.select_one('div.thumb img')['src'].split('?')[0]
        
        alter_el = soup.select_one('span.alter')
        alter_title = alter_el.text.strip() if alter_el else ""
        rating_el = soup.select_one('.rating strong')
        rating = rating_el.text.replace("Rating", "").strip() if rating_el else "0"

        raw_info = {}
        for span in info_div.select('.spe span'):
            text = span.text.strip()
            if ':' in text:
                key, val = text.split(':', 1)
                raw_info[key.strip()] = val.strip()
        
        genres_data = []
        for g in info_div.select('.genxed a'):
            g_slug = g['href'].strip('/').split('/')[-1]
            genres_data.append({
                "name": g.text.strip(),
                "slug": g_slug,
                "href": f"/donghua/genres/{g_slug}",
                "anichinUrl": g['href']
            })

        synopsis_div = soup.select_one('div.entry-content')
        synopsis = synopsis_div.text.strip() if synopsis_div else ""

        episodes_list = []
        ep_elements = soup.select('div.eplister li')
        for li in ep_elements:
            ep_title = li.select_one('.epl-title').text.strip()
            ep_link = li.select_one('a')['href']
            ep_slug = ep_link.replace(BASE_URL, "").strip('/')
            
            episodes_list.append({
                "episode": ep_title,
                "slug": ep_slug,
                "href": f"/donghua/episode/{ep_slug}",
                "anichinUrl": ep_link
            })

        result = {
            "status": raw_info.get('Status', 'Unknown'),
            "title": title,
            "alter_title": alter_title,
            "poster": poster,
            "rating": rating,
            "studio": raw_info.get('Studio', '-'),
            "network": raw_info.get('Network', '-'),
            "released": raw_info.get('Released', '-'),
            "duration": raw_info.get('Duration', '-'),
            "type": raw_info.get('Type', 'Donghua'),
            "episodes_count": str(len(episodes_list)),
            "season": raw_info.get('Season', '-'),
            "country": raw_info.get('Country', 'China'),
            "released_on": raw_info.get('Released', '-'),
            "updated_on": raw_info.get('Updated on', '-'),
            "genres": genres_data,
            "synopsis": synopsis,
            "episodes_list": episodes_list
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

# --- 4. EPISODE STREAM (FULL) ---
@app.route('/anime/donghua/episode/<path:slug>')
def get_episode_stream(slug):
    if not slug.startswith('/'): slug = '/' + slug
    if not slug.endswith('/'): slug += '/'
    
    target_url = BASE_URL + slug
    try:
        response = scraper.get(target_url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        ep_title = soup.select_one('h1.entry-title').text.strip()
        
        servers = []
        pembed = soup.select_one('#pembed iframe')
        if pembed:
            src = pembed['src']
            name = "Default"
            if "ok.ru" in src: name = "OK.ru"
            elif "dailymotion" in src: name = "Dailymotion"
            elif "rumble" in src: name = "Rumble"
            servers.append({"name": name, "url": src})
            
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

        download_data = {}
        for dl in soup.select('.soraurlx'):
            try:
                res_tag = dl.select_one('strong')
                if not res_tag: continue
                res_key = res_tag.text.strip().lower().replace(' ', '')
                links = {}
                for a in dl.select('a'):
                    links[a.text.strip()] = a['href']
                download_data[f"download_url_{res_key}"] = links
            except: continue

        details_data = {}
        headlist = soup.select_one('.headlist')
        if headlist:
            d_title_el = headlist.select_one('.det h2 a')
            d_thumb_el = headlist.select_one('.thumb img')
            d_title = d_title_el.text.strip()
            d_link = d_title_el['href']
            d_slug = d_link.replace(BASE_URL, "").strip('/').replace('anime/', '')
            d_poster = d_thumb_el['src'].split('?')[0] if d_thumb_el else ""
            updated_span = soup.select_one('.updated')
            released_date = updated_span.text.strip() if updated_span else "-"
            
            details_data = {
                "title": d_title,
                "slug": d_slug,
                "poster": d_poster,
                "type": "Donghua",
                "released": released_date,
                "uploader": "admin",
                "href": f"/donghua/detail/{d_slug}",
                "anichinUrl": d_link
            }

        nav_data = {"previous_episode": None, "next_episode": None, "all_episodes": None}
        nav_div = soup.select_one('.naveps')
        if nav_div:
            all_a = nav_div.select_one('a[href*="/anime/"]')
            if all_a:
                all_slug = all_a['href'].replace(BASE_URL, "").strip('/').replace('anime/', '')
                nav_data["all_episodes"] = {"slug": all_slug, "href": f"/donghua/detail/{all_slug}", "anichinUrl": all_a['href']}
            
            prev_a = nav_div.select_one('a[rel="prev"]')
            if prev_a:
                p_slug = prev_a['href'].replace(BASE_URL, "").strip('/')
                nav_data["previous_episode"] = {"episode": "Previous", "slug": p_slug, "href": f"/donghua/episode/{p_slug}", "anichinUrl": prev_a['href']}
            
            next_a = nav_div.select_one('a[rel="next"]')
            if not next_a:
                 for a in nav_div.select('a'):
                     if "Next" in a.text: next_a = a; break;
            if next_a:
                n_slug = next_a['href'].replace(BASE_URL, "").strip('/')
                nav_data["next_episode"] = {"episode": "Next", "slug": n_slug, "href": f"/donghua/episode/{n_slug}", "anichinUrl": next_a['href']}

        episodes_list_data = []
        for li in soup.select('#singlepisode .episodelist li'):
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

        return jsonify({
            "status": "success",
            "episode": ep_title,
            "streaming": streaming_data,
            "download_url": download_data,
            "donghua_details": details_data,
            "navigation": nav_data,
            "episodes_list": episodes_list_data
        })
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

# --- 5. COMPLETED ---
@app.route('/anime/donghua/completed/<page>')
def get_completed(page):
    if page == '1': url = f"{BASE_URL}/completed/"
    else: url = f"{BASE_URL}/completed/page/{page}/"
    
    try:
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        articles = soup.select('div.listupd article.bs')
        
        data = []
        for item in articles:
            try:
                title = item.select_one('.tt h2').text.strip()
                link = item.select_one('div.bsx a')['href']
                img = item.select_one('img')
                
                slug = link.replace(BASE_URL, "").strip('/').replace('anime/', '')
                if not slug.endswith('/'): slug += '/'
                poster = img['src'].split('?')[0] if img else ""
                href = f"/donghua/detail/{slug}"

                data.append({
                    "title": title,
                    "slug": slug,
                    "poster": poster,
                    "status": "Completed",
                    "href": href,
                    "anichinUrl": link
                })
            except: continue
        return jsonify({"status": "success", "completed_donghua": data})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

# --- 6. SCHEDULE ---
@app.route('/anime/donghua/schedule')
def get_schedule():
    url = f"{BASE_URL}/schedule/"
    try:
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        schedule_data = []
        days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        
        for day in days:
            day_container = soup.select_one(f'.schedulepage.sch_{day}')
            if not day_container: continue
            
            anime_list = []
            for item in day_container.select('.bsx'):
                try:
                    title = item.select_one('.tt').text.strip()
                    link = item.select_one('a')['href']
                    img = item.select_one('img')
                    
                    slug = link.replace(BASE_URL, "").strip('/')
                    if not slug.endswith('/'): slug += '/'
                    
                    if '/anime/' in link:
                         href = f"/donghua/detail/{slug.replace('anime/', '')}"
                    else:
                         href = f"/donghua/episode/{slug}"
                    
                    poster = img['src'].split('?')[0] if img else ""
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
                        "timestamp": timestamp,
                        "href": href,
                        "anichinUrl": link
                    })
                except: continue
            
            if anime_list:
                schedule_data.append({"day": day.capitalize(), "anime_list": anime_list})
        return jsonify({"status": "success", "schedule": schedule_data})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

# --- 7. EXTRACT RUMBLE ---
@app.route('/anime/donghua/extract/rumble')
def extract_rumble():
    embed_url = request.args.get('url')
    if not embed_url: return jsonify({"status": "error", "msg": "No URL"}), 400
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36', 'Referer': 'https://anichin.moe/'}
        response = scraper.get(embed_url, headers=headers)
        
        mp4_links = re.findall(r'"url":"(https:[^"]+\.mp4)"', response.text)
        if not mp4_links:
            mp4_links = re.findall(r'"url":"(https:\/\/[^"]+\.mp4)"', response.text)

        if mp4_links:
            clean_links = [l.replace('\\/', '/') for l in mp4_links]
            unique_links = list(set(clean_links))
            final_link = unique_links[0]
            for link in unique_links:
                if ".haa.mp4" in link: final_link = link; break;
                elif ".gaa.mp4" in link: final_link = link
            
            return jsonify({
                "status": "success",
                "quality": "HD/Auto",
                "stream_url": final_link,
                "all_qualities": unique_links
            })
        else:
            return jsonify({"status": "error", "msg": "Failed to extract"}), 404
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)