#!/usr/bin/env python3
from flask import Flask, render_template, request
from flask_socketio import SocketIO, send, emit
from flask_mqtt import Mqtt
import time
import csv
import random
import os
import pickle
import json
import threading
import queue
from bokeh.plotting import figure
from bokeh.resources import CDN
from bokeh.embed import file_html
from utilities import make_filename

app = Flask(__name__)
task_queue = queue.Queue()

app.config['MQTT_BROKER_URL'] = '0.0.0.0'  # localhost
app.config['MQTT_BROKER_PORT'] = 1883  # default port for non-tls connection
# set the username here if you need authentication for the broker
app.config['MQTT_USERNAME'] = ''
# set the password here if the broker demands authentication
app.config['MQTT_PASSWORD'] = ''
# set the time interval for sending a ping to the broker to 5 seconds
app.config['MQTT_KEEPALIVE'] = 5
# set TLS to disabled for testing purposes
app.config['MQTT_TLS_ENABLED'] = False

socketio = SocketIO(app)
mqtt = Mqtt(app)
count = 0
esp8266_data = 0
data_dir = "data"


if not os.path.isfile(data_dir + "/" + "data.pickle"):
    # fp = open("data.pickle", "x")
    fp = open(data_dir + "/" + "data.pickle", "x")
    fp.close()
try:
    with open(data_dir + "/" + "data.pickle", "rb") as fp:
        big_count = pickle.load(fp)
except EOFError:
    # first time through should be 0
    big_count = -1

big_count += 1

# update our launch count
with open(data_dir + "/" + "data.pickle", "wb") as fp:
    pickle.dump(big_count, fp)


def worker_function():
    while True:
        func, args, kwargs = task_queue.get()
        print(f"trying to run {func} with {args} and {kwargs}... ", end='')
        try:
            func(*args, **kwargs)
            print("worked!")
        except Exception as e:
            print(f"task queue failed: {e}")
        task_queue.task_done()


threading.Thread(target=worker_function, daemon=True).start()


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
    fil_nam = data_dir + "/" + make_filename()
    # esp8266_data = request.args.get('data')
    incoming_data = request.args.get('data')
    esp8266_data = incoming_data

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
    # socketio.emit('esp_data', {'data': incoming_data})
    socketio.emit('esp_data', {'data': incoming_data}, namespace='/')
    # return request.args.get('data')
    return incoming_data


# @app.route('/', methods=['GET', 'POST'])
@app.route('/', methods=['GET'])
def index():
    global big_count
    global count
    count += 1
    # templateData = {
    #     'title': "Hello!",
    #     'num': count
    # }
    # if request.method == 'POST':
    #     temp_num = 99
    if request.method == 'GET':
        temp_num = count
    return render_template('index.html',
                           title="Hello!",
                           num=temp_num,
                           big_num=big_count,
                           data=esp8266_data
                           )


@socketio.on('connect')
def handle_connect():
    print(f"Client {request.sid} connected")
    # mqtt.subscribe('test/webserver')
    mqtt.subscribe('test/webserver')
    emit("data", esp8266_data)
    emit("mqtt_message", "null")


@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client {request.sid} disconnected")


@socketio.on('esp_data')
def handle_data(json):
    print(f"data event, received: {str(json)}")
    emit("data", esp8266_data)


@socketio.on('my event')
def handle_my_event(json):
    print(f"received: {str(json)}")


@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    data = dict(
        topic=message.topic,
        payload=message.payload.decode()
    )
    print(f"-->received {data["topic"]}: {data["payload"]}")
    try:
        try:
            esp8266_data = json.loads(data["payload"].replace("'", '"'))
            print("(bad quotes in string) ", end='')
        except json.decoder.JSONDecodeError:
            esp8266_data = json.loads(data["payload"])
            print("(data decoded just fine) ", end='')
        if isinstance(esp8266_data, dict):
            print("json data decoded to dict\n----------------------")
            # for k in esp8266_data.keys(): print(f"\t{k}:\t{esp8266_data[k]}")
            print(json.dumps(esp8266_data, sort_keys=True, indent=4))
            temperature = esp8266_data.get('temp_f', {}).get('result', None)
            if temperature is not None:
                temperature = round(temperature, 2)
            # socketio.emit("data", temperature, namespace='/')
            task_queue.put(
                (socketio.emit, ["data", temperature], {"namespace": '/'}))
        else:
            print(f"data returned as type {type(data["payload"])}")
            # socketio.emit("data", data["payload"], namespace='/')
            task_queue.put(
                # (socketio.emit, "data", {"data": data["payload"], "namespace": '/'}))
                (socketio.emit, ["data", data["payload"]], {"namespace": '/'}))
    except:
        print("bad json decoding!")
        esp8266_data = data["payload"]
        socketio.emit("data", data["payload"], namespace='/')
    return_data = f"snd->{esp8266_data}"
    # socketio.emit("data", return_data, namespace='/')
    # socketio.emit('mqtt_message', data=data, namespace='/')
    task_queue.put((socketio.emit, ['mqtt_message', data], {"namespace": '/'}))
    # mqtt.publish('test/littleguy', return_data.encode())
    task_queue.put((mqtt.publish, ['test/littleguy', return_data.encode()], {}))


if __name__ == '__main__':
    # app.run(debug=True, port=80, host='0.0.0.0')
    socketio.run(app, host="0.0.0.0", debug=True)
