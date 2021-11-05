from flask import Flask
import requests
from flask import render_template
from RepeatedTimer import RepeatedTimer
from flask_socketio import SocketIO, emit
from threading import Thread
from gevent import monkey as curious_george
import redis

r = redis.StrictRedis(host='localhost', port=6379, db=0, charset="utf-8", decode_responses=True)
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
    rt = RepeatedTimer(1, process_thread) 

def process_thread():
    thread = Thread(target=process_articles)
    thread.daemon = True
    thread.start()

def process_articles():
    with app.test_request_context('/'):
        data = get_articles()
        articles_data = data["data"]
        articles = []
        for article in articles_data:
            article_dict = {article["attributes"]["publishOn"]: article["attributes"]["title"]}
            articles.append(article_dict)
            r.set(article["attributes"]["publishOn"], article["attributes"]["title"])
        emit('get_artciles',{'articles': articles},broadcast=True,namespace='/start')

def get_articles():
    url = f'https://seekingalpha.com/api/v3/articles?cacheBuster=2021-10-20&filter[category]=stock-ideas::long-ideas&filter[since]=0&filter[until]=0&include=author,primaryTickers,secondaryTickers&isMounting=true&page[size]=100&page[number]=1'
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
    data = requests.get(url, headers=headers).json()
    return data

if __name__ == "__main__":
  socket_.run(app, debug=True)