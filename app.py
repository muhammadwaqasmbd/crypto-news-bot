from flask import Flask
import requests, json
from flask import render_template
from RepeatedTimer import RepeatedTimer
from flask_socketio import SocketIO, emit
from threading import Thread
from gevent import monkey as curious_george
import redis
import datetime as dt
from rejson import Client, Path
from SetEncoder import SetEncoder
from urllib.request import Request, urlopen 
from bs4 import BeautifulSoup
import time
from mechanize import Browser

r1 = redis.StrictRedis(host='localhost', port=6379, db=1, charset="utf-8", decode_responses=True)
r2 = redis.StrictRedis(host='localhost', port=6379, db=2, charset="utf-8", decode_responses=True)
r3 = redis.StrictRedis(host='localhost', port=6379, db=3, charset="utf-8", decode_responses=True)
r4 = redis.StrictRedis(host='localhost', port=6379, db=4, charset="utf-8", decode_responses=True)

async_mode = "gevent"
curious_george.patch_all(ssl=False)
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socket_ = SocketIO(app,async_mode=async_mode)
thread = None

@app.route("/")
def scrape():
    return render_template('index.html')

@socket_.on('start_process', namespace='/start')
def start_process(message):
    rt_huobi = RepeatedTimer(1, process_huobi_thread) 
    rt_okex = RepeatedTimer(1, process_okex_thread)
    rt_binance = RepeatedTimer(3, process_binance_thread) 
    rt_medium = RepeatedTimer(60, process_medium_thread) 
    rt_huobi_redis = RepeatedTimer(1, process_huobi_redis_thread) 
    rt_okex_redis = RepeatedTimer(1, process_okex_redis_thread)
    rt_binance_redis = RepeatedTimer(1, process_binance_redis_thread) 
    rt_medium_redis = RepeatedTimer(1, process_medium_redis_thread)

def process_huobi_redis_thread():
    thread = Thread(target=get_all_records,args=[r1,"get_huobi"])
    thread.daemon = True
    thread.start()

def process_okex_redis_thread():
    thread = Thread(target=get_all_records,args=[r1,"get_okex"])
    thread.daemon = True
    thread.start()

def process_binance_redis_thread():
    thread = Thread(target=get_all_records,args=[r1,"get_binance"])
    thread.daemon = True
    thread.start()

def process_medium_redis_thread():
    thread = Thread(target=get_all_records,args=[r1,"get_medium"])
    thread.daemon = True
    thread.start()

def process_huobi_thread():
    thread = Thread(target=process_huobi_articles)
    thread.daemon = True
    thread.start()

def process_okex_thread():
    thread = Thread(target=process_okex_articles)
    thread.daemon = True
    thread.start()

def process_binance_thread():
    thread = Thread(target=process_binance_articles)
    thread.daemon = True
    thread.start()

def process_binance_article_thread(code,json_data):
    thread = Thread(target=process_binance_article,args=[code,json_data])
    thread.daemon = True
    thread.start()

def process_medium_thread():
    thread = Thread(target=process_medium_articles)
    thread.daemon = True
    thread.start()

def redis_save_thread(r,publish_date,json_data):
    thread = Thread(target=redis_save_date,args=[r,publish_date,json_data])
    thread.daemon = True
    thread.start()

def redis_get_data_thread(r,article_type):
    thread = Thread(target=get_all_records,args=[r,article_type])
    thread.daemon = True
    thread.start()

def process_huobi_articles():
    current_time =  dt.datetime.now()
    data = get_records("https://www.huobi.com/support/public/getList/v2?page=1&limit=20&oneLevelId=360000031902&twoLevelId=360000039481&language=en-us",True)
    articles_data = data["data"]["list"]
    for article in articles_data:
        json_data = json.dumps([{"title":article["title"]},{"time2":dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}],cls=SetEncoder)
        publish_date = get_datestring_from_integer(article["showTime"])
        redis_save_thread(r1,publish_date, json_data)
    #redis_get_data_thread(r1,"get_huobi")
    print("Total Time in seconds huobi :", (current_time- dt.datetime.now()).total_seconds())

def redis_save_date(r,publish_date,json_data):
    r.set(publish_date, json_data)

def process_okex_articles():
    current_time =  dt.datetime.now()
    data = get_records("https://www.okex.com/support/hc/api/internal/recent_activities?locale=en-us&page=1&per_page=20&locale=en-us", False)
    articles_data = data["activities"]
    for article in articles_data:
        json_data = json.dumps([{"title":article["title"]},{"time2":dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}],cls=SetEncoder)
        published_date = article["timestamp"][:-1]
        publish_date = get_formated_datestring(published_date)
        redis_save_thread(r2,publish_date, json_data)
    #redis_get_data_thread(r1,"get_okex")
    print("Total Time in seconds okex :", (current_time- dt.datetime.now()).total_seconds())

def process_binance_articles():
    data = get_records("https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId=49&pageNo=1&pageSize=20", False)
    articles_data = data["data"]["articles"]
    for article in articles_data:
        json_data = json.dumps([{"title":article["title"]} ,{"time2":dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, {"publishDate":article["publishDate"]}],cls=SetEncoder)
        current_time =  dt.datetime.now()
        process_binance_article_thread(article["code"],json_data)
        #redis_get_data_thread(r3,"get_binance")
        print("Total Time in seconds binance :", (current_time- dt.datetime.now()).total_seconds())

def process_binance_article(code,json_data):
    record_data = get_records("https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode="+code, False)
    publish_date = get_datestring_from_integer(record_data["data"]["publishDate"])
    redis_save_thread(r3,publish_date, json_data)

def process_medium_articles():
    current_time =  dt.datetime.now()
    data = get_medium_records("https://medium.com/@coinbaseblog")
    for article in data:
        title = article.find("a", class_="eh bw", href=True)
        if title is None:
            continue
        else:
            href = title["href"].split("?")[0]
            title = title.contents[0]
            time.sleep(2)
            publish_date = get_medium_article(href)
            json_data = json.dumps([{"title":title}, {"time2":dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}],cls=SetEncoder)
            redis_save_thread(r4,publish_date, json_data)
    #redis_get_data_thread(r4,"get_medium")
    print("Total Time in seconds medium :", (current_time- dt.datetime.now()).total_seconds())

def get_records(url,huobi):
    url = f'{url}'
    if huobi:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = urlopen(req)
        json_data = json.loads(data.read().decode(data.info().get_param('charset') or 'utf-8'))
        return json_data
    else:
        headers = get_headers()
        data = requests.get(url, headers=headers,auth=('[username]','[password]'), verify=False).json()
        return data

def get_headers():
    headers = {
        'accept': '*/*',
        'accept-encoding': 'gzip,deflate,br',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'cookie': 'machine_cookie=5356356749135',
        'pragma': 'no-cache',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0',
    }
    return headers

def get_medium_records(url):
    b = Browser()
    b.set_handle_robots(False)
    b.addheaders = [('Referer', 'https://www.medium.com'), ('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]
    b.open(url)
    soup = BeautifulSoup(b.response().read(), 'html.parser')
    articles = soup.find_all("div", class_="gf gg gh ah gi ku gk kv gm kw go kx gq ky")
    return articles

def get_medium_article(url):
    b = Browser()
    b.set_handle_robots(False)
    b.addheaders = [('Referer', 'https://www.medium.com'), ('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]
    b.open(url)
    soup = BeautifulSoup(b.response().read(), "html.parser")
    publish_date = soup.find("meta", property="article:published_time")["content"]
    publish_date = publish_date[:-5]
    formated_date = get_formated_datestring(publish_date)
    return formated_date

def get_all_records(r,article_type):
    with app.test_request_context('/'):
        articles=[]
        keys = r.keys('*')
        for key in keys:
            vals = r.get(key)
            if vals is not None:
                article_dict = {key:vals}
                articles.append(article_dict)
        if len(articles) > 0:
            emit(article_type,{'articles': articles},broadcast=True,namespace='/start')

def get_datestring_from_integer(time):
    return dt.datetime.fromtimestamp(time/ 1e3).strftime("%Y-%m-%d %H:%M:%S")

def get_formated_datestring(time):
    return dt.datetime.strptime(time,"%Y-%m-%dT%H:%M:%S").strftime('%Y-%m-%d %H:%M:%S')

if __name__ == "__main__":
  socket_.run(app,host='0.0.0.0', port=3000, debug=True)
