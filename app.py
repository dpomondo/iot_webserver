#!/usr/bin/env python3
from flask import Flask, render_template, request
from flask_socketio import SocketIO, send, emit
from flask_mqtt import Mqtt
import time
import csv
# import random
import os
import pickle
import json
import threading
import queue
from math import nan, isnan
from bokeh.plotting import figure
from bokeh.models import Range1d, LinearAxis, Title
from bokeh.resources import CDN
# from bokeh.embed import file_html
from bokeh.embed import components
from utilities import make_filename

app = Flask(__name__)
task_queue = queue.Queue()
LEN_TEMP_DATA = 20

dashes = [[3, 4], [2, 2], [5, 9], []]
temperature_colors = ["FireBrick", "DarkRed", "DeepPink", "Red"]
humidity_colors = ["DodgerBlue", "DeepBlueSky", "CadetBlue", "CornflowerBlue"]


class DataStream:
    def __init__(self, name, mqtt_address):
        self.name = name
        self.mqtt_address = mqtt_address
        self.temperature_data = []
        self.humidity_data = []
        for i in range(LEN_TEMP_DATA):
            self.temperature_data.append(nan)
            self.humidity_data.append(nan)
        self.line_dash = dashes.pop()
        self.temp_line_color = temperature_colors.pop()
        self.hum_line_color = humidity_colors.pop()

    def append_data(self, new_temp, new_humidity):
        self.temperature_data.append(new_temp)
        self.humidity_data.append(new_humidity)
        while len(self.temperature_data) > LEN_TEMP_DATA:
            self.temperature_data.pop(0)
            self.humidity_data.pop(0)
        assert len(self.temperature_data) == len(self.humidity_data)
        print(f"\t{self.name} has new data: {self.temperature_data}\t{self.humidity_data}")

        task_queue.put((plot_data, [], {}))

    def __str__(self):
        return f"name: {self.name}\taddress: {self.mqtt_address}\n\tline colors: {self.temp_line_color}, {self.hum_line_color}\n\tdashes: {self.line_dash}"


initial_names = ['garage/desk', 'attic']
initial_locations = ['test/garage', 'test/webserver']
streams = {}

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

# these need to be next to each other! a delay between the Mqtt(app) call 
# and invoking the on_connect function might mean that the connection 
# if up and running BEFORE the handler gets registered.
mqtt = Mqtt(app)


@mqtt.on_connect()
def handle_mqtt_connect(client, userdata, flags, rc):
    print(f"connection attempt with mqtt broker! result: {rc}")
    if len(streams) == 0:
        for nam in range(len(initial_names)):
            streams[initial_names[nam]] = DataStream(
                initial_names[nam], initial_locations[nam])
            print(f"new object:\n\t{streams[initial_names[nam]]}")

        for k in streams:
            print(f"{k} is key for DataStream object {streams[k]}")

    for strm in streams:
        print(
            f"subscribing to {streams[strm].mqtt_address} for device {streams[strm].name}")
        mqtt.subscribe(streams[strm].mqtt_address)
    # mqtt.subscribe('test/webserver')


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


def plot_data():
    print("\tPlotting...")
    plot = figure(width=700, height=300, toolbar_location=None)
    plot.extra_y_ranges['foo'] = Range1d(0, 100)
    hum_y = LinearAxis(
        axis_label="humidity",
        # x_range_name='foo',
        y_range_name='foo')
    hum_y.axis_label_text_color = 'blue'

    # trying to get high & low bounds for temp y axis
    # if nan in temperature_data:
    #     td_int = [n for n in temperature_data if not isnan(n)]
    #     print(f"\tnum:{len(td_int)}\tgood temp values:{str(td_int)}")
    #     floor = int(min(td_int) / 5) * 5
    #     ceiling = (int(max(td_int) / 5) * 5) + 5
    # else:
    #     floor = int(min(temperature_data) / 5) * 5
    #     ceiling = (int(max(temperature_data) / 5) * 5) + 5
    # print(f"\tfloor: {floor}\tceiling: {ceiling}")

    lows = set()
    for st in streams:
        lows.update(streams[st].temperature_data)

    lows.discard(nan)
    floor = int(min(lows) / 5) * 5
    ceiling = (int(max(lows) / 5) * 5) + 5

    # floor = 30
    # ceiling = 100
    plot.y_range = Range1d(floor, ceiling)
    # x = list(range(1, len(temperature_data) + 1))

    x = list(range(1, LEN_TEMP_DATA + 1))
    plot.x_range = Range1d(x[0]-1, x[-1]+2)
    plot.add_layout(hum_y, "right")
    plot.add_layout(Title(text="Temp in °F",
                          align="center",
                          text_color="red",
                          text_font_style="italic"),
                    "left")
    # plot.step(x, temperature_data, mode="center", color="red")
    # plot.step(x, humidity_data, mode="center",
    #           color="blue", y_range_name="foo")
    for st in streams:
        plot.step(x, streams[st].temperature_data, mode="center",
                  color=streams[st].temp_line_color,
                  line_dash=streams[st].line_dash,
                  legend_label=st)
        plot.step(x, streams[st].humidity_data, mode="center",
                  color=streams[st].hum_line_color,
                  line_dash=streams[st].line_dash, y_range_name="foo",
                  legend_label=st)
    script, div = components(plot)
    socketio.emit('draw_plot', {'plot_script': script,
                  'plot_div': div}, namespace='/')


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
    print(f"-->received topic: [{data["topic"]}]")
    print(
        f"-->received msg:\n\t{data["payload"]}\tlength: {len(data["payload"])}")
    try:
        temp = data["payload"].replace('\x00', '')
        try:
            esp8266_data = json.loads(temp)
            print("(data decoded just fine) ", end='')
        except json.decoder.JSONDecodeError:
            esp8266_data = json.loads(temp.replace("'", '"'))
            print("(bad quotes in string) ", end='')
        if isinstance(esp8266_data, dict):
            print("json data decoded to dict\n----------------------")
            # for k in esp8266_data.keys(): print(f"\t{k}:\t{esp8266_data[k]}")
            print(json.dumps(esp8266_data, sort_keys=True, indent=4))
            temperature = esp8266_data.get('temp_f', {}).get('result', None)
            humidity = esp8266_data.get('humidity', {}).get('result', None)
            if temperature is not None:
                temperature = round(temperature, 2)
            if humidity is not None:
                humidity = round(humidity, 2)
            # socketio.emit("data", temperature, namespace='/')
            task_queue.put(
                (socketio.emit, ["data", temperature], {"namespace": '/'}))
            # task_queue.put((append_data,
            if streams[esp8266_data.get('device', {})] is not None:
            # if streams[data.get('topic', {})] is not None:
                task_queue.put(
                    (streams[esp8266_data.get('device', {})].append_data,
                    # (streams[data.get('topic', {})].append_data,
                     [],
                     {"new_temp": temperature,
                      "new_humidity": humidity}))
        else:
            print(f"data returned as type {type(data["payload"])}")
            # socketio.emit("data", data["payload"], namespace='/')
            task_queue.put(
                # (socketio.emit, "data", {"data": data["payload"], "namespace": '/'}))
                (socketio.emit, ["data", data["payload"]], {"namespace": '/'}))
    except Exception as e:
        print(f"error: {e}")
        esp8266_data = data["payload"]
        socketio.emit("data", data["payload"], namespace='/')
    return_data = f"snd->{esp8266_data}"
    # socketio.emit("data", return_data, namespace='/')
    # socketio.emit('mqtt_message', data=data, namespace='/')
    task_queue.put((socketio.emit, ['mqtt_message', data], {"namespace": '/'}))
    # mqtt.publish('test/littleguy', return_data.encode())
    task_queue.put(
        (mqtt.publish, ['test/littleguy', return_data.encode()], {}))


if __name__ == '__main__':
    # app.run(debug=True, port=80, host='0.0.0.0')
    socketio.run(app, host="0.0.0.0", debug=True)
