#!/usr/bin/env python3
from flask import Flask, render_template, request
import time
import csv
import random
import os
import pickle
from bokeh.plotting import figure
from bokeh.resources import CDN
from bokeh.embed import file_html
from utilities import make_filename

app = Flask(__name__)
count = 0
esp8266_data = 0

if not os.path.isfile("data.pickle"):
    fp = open("data.pickle", "x")
    fp.close()
try:
    with open("data.pickle", "rb") as fp:
        big_count = pickle.load(fp)
except EOFError:
    # first time through should be 0
    big_count = -1

big_count += 1

# update our launch count
with open("data.pickle", "wb") as fp:
    pickle.dump(big_count, fp)


@app.route('/plot')
def plot_data():
    plot = figure()
    y = []
    for i in range(1, 11):
        y.append(round(100 * random.random(), 1))
    plot.scatter(list(range(1, 11)), y)

    html = file_html(plot, CDN, "my plot")
    return html


@app.route('/query-data', methods=['GET'])
def take_in_data():
    global esp8266_data
    fil_nam = make_filename()
    esp8266_data = request.args.get('data')

    tim_stam = time.asctime()
    results = []
    results.append(tim_stam)
    for k in request.args.keys():
        results.append(k)
        results.append(request.args.get(k))
    with open(fil_nam, 'a') as t:
        writer = csv.writer(t, delimiter=',')
        # writer.writerow([tim_stam, esp8266_data])
        writer.writerow(results)

    # return f"data: {request.args.get('data')}"
    return request.args.get('data')


@app.route('/', methods=['GET', 'POST'])
def index():
    global big_count
    global count
    count += 1
    # templateData = {
    #     'title': "Hello!",
    #     'num': count
    # }
    if request.method == 'POST':
        temp_num = 99
    elif request.method == 'GET':
        temp_num = count
    return render_template('index.html',
                           title="Hello!",
                           num=temp_num,
                           big_num=big_count,
                           data=esp8266_data
                           )


if __name__ == '__main__':
    app.run(debug=True, port=80, host='0.0.0.0')
