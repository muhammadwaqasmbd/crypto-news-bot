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
    rt_binance = RepeatedTimer(1, process_binance_thread) 
    rt_medium = RepeatedTimer(1, process_medium_thread) 

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

def process_medium_thread():
    thread = Thread(target=process_medium_articles)
    thread.daemon = True
    thread.start()

def process_huobi_articles():
    current_time =  dt.datetime.today()
    with app.test_request_context('/'):
        data = get_records("https://www.huobi.com/support/public/getList/v2?page=1&limit=20&oneLevelId=360000031902&twoLevelId=360000039481&language=en-us",True)
        articles_data = data["data"]["list"]
        for article in articles_data:
            json_data = json.dumps([{"title":article["title"]}],cls=SetEncoder)
            r1.set(article["showTime"], json_data)
        articles = get_all_records(r1)
        emit('get_huobi',{'articles': articles},broadcast=True,namespace='/start')
        print("Total Time in seconds huobi :", (current_time- dt.datetime.today()).total_seconds())

def process_okex_articles():
    current_time =  dt.datetime.today()
    with app.test_request_context('/'):
        data = get_records("https://www.okex.com/support/hc/api/internal/recent_activities?locale=en-us&page=1&per_page=20&locale=en-us", False)
        articles_data = data["activities"]
        for article in articles_data:
            json_data = json.dumps([{"title":article["title"]}, {"source":article["url"]}],cls=SetEncoder)
            r2.set(article["timestamp"], json_data)
        articles = get_all_records(r2)
        emit('get_okex',{'articles': articles},broadcast=True,namespace='/start')
        print("Total Time in seconds okex :", (current_time- dt.datetime.today()).total_seconds())

def process_binance_articles():
    current_time =  dt.datetime.today()
    with app.test_request_context('/'):
        data = get_records("https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId=49&pageNo=1&pageSize=20", False)
        articles_data = data["data"]["articles"]
        for article in articles_data:
            json_data = json.dumps([{"title":article["title"]}, {"catalogName":article["catalogName"]},{"publishDate":article["publishDate"]}],cls=SetEncoder)
            r3.set(article["code"], json_data)
        articles = get_all_records(r3)
        emit('get_binance',{'articles': articles},broadcast=True,namespace='/start')
        print("Total Time in seconds binance :", (current_time- dt.datetime.today()).total_seconds())

def process_medium_articles():
    current_time =  dt.datetime.today()
    with app.test_request_context('/'):
        data = get_medium_records("https://medium.com/@coinbaseblog")
        for article in data:
            title = article.find("a", class_="eh bw")
            if title is not None:
                title = title.contents[0]
            else:
                title = "None"
            author = article.find("em", class_="jo")
            if author is not None:
                author = author.contents[0]
            else:
                author = "None"
            image = article.find("img", class_="v gx ir")
            if image is not None:
                image = image['src']
            else:
                image = "None"
            likes = article.find("button", class_="eh ei bz ca cb cc cd ce cf bl ej ek cg el em")
            if likes is not None:
                likes = likes.contents[0]
            else:
                likes = "None"
            comments = article.find("span", class_="lj li")
            if comments is not None:
                comments = comments.contents[0]
            else:
                comments = "None"
            json_data = json.dumps([{"title":title}, {"author":author},{"image":image},{"likes":likes},{"comments":comments}],cls=SetEncoder)
            r4.set(title, json_data)
        articles = get_all_records(r4)
        emit('get_medium',{'articles': articles},broadcast=True,namespace='/start')
        print("Total Time in seconds medium :", (current_time- dt.datetime.today()).total_seconds())

def get_records(url,huobi):
    url = f'{url}'
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
    if huobi:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = urlopen(req)
        json_data = json.loads(data.read().decode(data.info().get_param('charset') or 'utf-8'))
        return json_data
    else:
        data = requests.get(url, headers=headers,auth=('[username]','[password]'), verify=False).json()
        return data

def get_medium_records(url):
    response = requests.get(url, allow_redirects=True)
    page = response.content
    soup = BeautifulSoup(page, 'html.parser')
    articles = soup.find_all("div", class_="ap aq ar as at fz av v")
    return articles

def get_all_records(r):
    articles=[]
    keys = r.keys('*')
    for key in keys:
        vals = None
        type = r.type(key)
        if type == "string":
            vals = r.get(key)
        if type == "hash":
            vals = r.hgetall(key)
        if type == "zset":
            vals = r.zrange(key, 0, -1)
        if type == "list":
            vals = r.lrange(key, 0, -1)
        if type == "set":
            vals = r.smembers(key)
        article_dict = {key:vals}
        articles.append(article_dict)
    return articles

if __name__ == "__main__":
  socket_.run(app,host='0.0.0.0', port=3000, debug=True)
