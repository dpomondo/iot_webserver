#!/usr/bin/env python3
from flask import Flask, render_template, request
from flask_socketio import SocketIO, send, emit
from flask_mqtt import Mqtt
import time
from datetime import datetime, timedelta
import csv
# import random
import os
import pickle
import json
import threading
import queue
import traceback
from math import nan, isnan
from bokeh.plotting import figure
from bokeh.models import Range1d, LinearAxis, Title, Legend
from bokeh.resources import CDN
# from bokeh.embed import file_html
from bokeh.embed import components
from utilities import make_filename
# from datastream import DataStream, temperature_colors, humidity_colors, dashes
from class_datastream import DataStream

app = Flask(__name__)
task_queue = queue.Queue()
LEN_TEMP_DATA = 80
plot_time_range = timedelta(minutes=30)

write_delta = timedelta(seconds=30)
plot_delta = timedelta(seconds=30)
disk_write_delta = timedelta(minutes=15)
# call plot first time we get there
previous_plot = datetime.now() - plot_delta
# old_script, old_div = None, None

time_format_string = "%Y-%m-%dT%H:%M:%S"


def time_check(strm, new_temp, temp_sensor, new_humidity, humidity_sensor):
    if (new_temp == nan) or (new_humidity == nan):
        raise ValueError("Trying to append nan to time series")
    now = datetime.now()
    if now > strm.previous_write + write_delta:
        # strm.append_data(new_temp, new_humidity)
        task_queue.put((strm.append_data, [new_temp, new_humidity], {}))
        strm.previous_write = now   # should this be INSIDE the class method?
        strm.new_data_flag = True

    if now > strm.previous_disk_write + timedelta(minutes=10):
        task_queue.put((write_data_csv, [], {
                       "name": strm.name,
                        "time": now,
                        "new_temp": new_temp,
                        "temp_sensor": temp_sensor,
                        "new_humidity": new_humidity,
                        "humidity_sensor": humidity_sensor}))
        strm.previous_disk_write = now

    global previous_plot
    if now > previous_plot + plot_delta:
        task_queue.put((plot_data, [], {}))
        # plot_flag = set([st.new_data_flag for st in streams.values()])
        # if False not in plot_flag:
        #     task_queue.put((plot_data, [], {}))
        #     # previous_plot = now
        #     for st in streams.values():
        #         st.new_data_flag = False


initial_names = ['garage/desk', 'attic', 'garage/attic']
initial_locations = ['garage/desk', 'test/webserver', 'garage/attic']
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
# is up and running BEFORE the handler gets registered.
mqtt = Mqtt(app)


@mqtt.on_connect()
def handle_mqtt_connect(client, userdata, flags, rc):
    print(f"connection attempt with mqtt broker! result: {rc}")
    if len(streams) == 0:
        for nam in range(len(initial_names)):
            streams[initial_names[nam]] = DataStream(
                initial_names[nam],
                initial_locations[nam],
                LEN_TEMP_DATA,
                write_delta,
                disk_write_delta)
            print(f"new object:\n\t{streams[initial_names[nam]]}")

        for k in streams:
            print(f"{k} is key for DataStream object {streams[k]}")

    for strm in streams.values():
        targets = [strm.mqtt_address,
                   strm.mqtt_address + "/mqtt_reset",
                   strm.mqtt_address + "/wireless_reset",
                   strm.mqtt_address + "/power_status",
                   strm.mqtt_address + "/watchdog_reset"]
        for t in targets:
            print(
                f"subscribing to {t} for device {strm.name}")
            mqtt.subscribe(t)
    # mqtt.subscribe('test/webserver')


count = 0
esp8266_data = 0
data_dir = "data"

if not os.path.isfile(data_dir + "/" + "data.pickle"):
    # fp = open("data.pickle", "x")
    fp = open(data_dir + "/" + "data.pickle", "x")
    fp.close()
    big_count = -1
else:
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

# do we have an old plot we can recycle?
if not os.path.isfile(data_dir + "/" + "plot_bak.pickle"):
    fp = open(data_dir + "/" + "plot_bak.pickle", "x")
    fp.close()
    old_script, old_div = None, None
else:
    try:
        with open(data_dir + "/" + "plot_bak.pickle", "rb") as fp:
            plot_pickle = pickle.load(fp)
            old_script = plot_pickle["script"]
            old_div = plot_pickle["div"]
    except EOFError:
        old_script, old_div = None, None


def worker_function():
    while True:
        func, args, kwargs = task_queue.get()
        print(f"trying to run {func} with {args} and {kwargs}... ", end='')
        try:
            func(*args, **kwargs)
            print("worked!")
        except Exception as e:
            print(f"task queue failed: {e}")
            error_trace = traceback.format_exc()
            print(error_trace)
        task_queue.task_done()


threading.Thread(target=worker_function, daemon=True).start()


def plot_data():
    global old_script
    global old_div
    global previous_plot
    # clear_screen_ansi()
    print("\tPlotting...")
    plot = figure(width=900, height=500,
                  x_axis_type="datetime",
                  toolbar_location=None)
    plot.extra_y_ranges['foo'] = Range1d(0, 100)
    hum_y = LinearAxis(
        axis_label="humidity",
        # x_range_name='foo',
        y_range_name='foo')
    plot.add_layout(Legend(), 'below')
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
    earlyiest_td = []
    for st in streams.values():
        lows.update(st.temperature_data)
        print(f"\t\t{st.name}\tlen temp data: {len(st.temperature_data)}")
        td = [tim for tim in st.time_data if tim is not nan]
        if len(td) > 0:
            print(f"\t\t\tearliest:{td[0]}\tlen: {len(td)}")
            earlyiest_td.append(min(td))

    lows.discard(nan)
    floor = int(min(lows) / 5) * 5
    ceiling = (int(max(lows) / 5) * 5) + 5

    now = datetime.now()
    earliest = now - min(earlyiest_td)
    if earliest > plot_time_range:
        earliest = plot_time_range

    print(f"floor: {floor}\tceiling: {ceiling}\tearliest: {earliest}")

    plot.y_range = Range1d(floor, ceiling)
    plot.x_range = Range1d(now - earliest, now)
    plot.add_layout(hum_y, "right")
    plot.add_layout(Title(text="Temp in °F",
                          align="center",
                          text_color="red",
                          text_font_style="italic"),
                    "left")
    # plot.step(x, temperature_data, mode="center", color="red")
    # plot.step(x, humidity_data, mode="center",
    #           color="bl ue", y_range_name="foo")
    for st in streams.values():
        print(f"checking the data integrity of {st.name}: ", end='')
        good_time = [d for d in st.time_data if d is not nan]
        # good_data = [d for d in st.temperature_data if d is not nan]
        # good_humi = [d for d in st.humidity_data if d is not nan]
        # plot.step(x, streams[st].temperature_data, mode="center",
        # plot.step(time.strptime(streams[st].time_data, time_format_string),
        # plot.step(streams[st].time_data,
        #           streams[st].temperature_data,
        if len(good_time) > 0:
            print("good!")
            good_data = [d for d in st.temperature_data if d is not nan]
            good_humi = [d for d in st.humidity_data if d is not nan]
            plot.step(good_time,
                      good_data,
                      mode="center",
                      color=st.temp_line_color,
                      line_dash=st.line_dash,
                      legend_label=st.name)
            # plot.step(x, streams[st].humidity_data, mode="center",
            # plot.step(time.strptime(streams[st].time_data, time_format_string),
            plot.step(good_time,
                      good_humi,
                      mode="center",
                      color=st.hum_line_color,
                      line_dash=st.line_dash, y_range_name="foo",
                      legend_label=st.name)
        else:
            print(
                f"skipping {st.name} because it has {len(good_time)} good data")
    script, div = components(plot)
    old_script, old_div = script, div
    previous_plot = now

    # with open(data_dir + "/" + "data.pickle", "wb") as fp:
    with open(data_dir + "/" + "plot_bak.pickle", "wb") as fp:
        plot_pickle = {"script": script, "div": div}
        pickle.dump(plot_pickle, fp)
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


def write_data_csv(name, time, new_temp, temp_sensor, new_humidity, humidity_sensor):
    fil_nam = data_dir + "/" + make_filename()
    # tim_stam = datetime.now.strftime(time_format_string)
    tim_stam = time.strftime(time_format_string)
    if not os.path.isfile(fil_nam):
        with open(fil_nam, 'x', newline='') as csvfile:
            header_writer = csv.writer(csvfile, delimiter=',')
            header_writer.writerow(["time",
                                   "device",
                                    "temp_f",
                                    "temp_sensor",
                                    "error_flag_t",
                                    "humidity",
                                    "humidity_sensor",
                                    "error_flag_h"])
    target = []
    target.append(tim_stam)
    target.append(name)
    target.append(new_temp)
    target.append(temp_sensor)
    target.append("None")
    target.append(new_humidity)
    target.append(humidity_sensor)
    target.append("None")
    with open(fil_nam, 'a',  newline='') as csvfile:
        target_writer = csv.writer(csvfile, delimiter=',')
        target_writer.writerow(target)


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
    if (old_script is not None) & (old_div is not None):
        socketio.emit('draw_plot', {'plot_script': old_script,
                      'plot_div': old_div}, namespace='/')
    else:
        task_queue.put((plot_data, [], {}))


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
    # here be hacks
    if data["topic"] in initial_locations:
        print("********\nnormal data message\n*********")
        task_queue.put((data_mqtt_message, [data], {}))
    else:
        print("uh oh something interesting: ", end="")
        addr, end = data["topic"].rsplit("/", 1)
        for strm in streams.values():
            if strm.mqtt_address == addr:
                if end == "mqtt_reset":
                    strm.mqtt_resets = int(data["payload"])
                elif end == "wireless_reset":
                    strm.wireless_resets = int(data["payload"])
                elif end == "watchdog_reset":
                    # the devices can keep track of mqtt or
                    # wireless reset totals, but watchdog resets
                    # need to be incremented on the server end
                    strm.watchdog_resets += 1
                # elif end == "read_vsys":
                elif end == "power_status":
                    # strm.vsys = float(data["payload"])
                    strm.vsys = data["payload"]
                print(f"{strm.name} had {end} event")
                task_queue.put(
                    (socketio.emit, ['mqtt_message', data], {"namespace": '/'}))


def data_mqtt_message(data):
    try:
        temp = data["payload"].replace('\x00', '')
        try:
            esp8266_data = json.loads(temp)
            print("(data decoded just fine) ", end='')
        except json.decoder.JSONDecodeError:
            esp8266_data = json.loads(temp.replace("'", '"'))
            print("(bad quotes in string) ", end='')
        # here be switches
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
                    # (streams[esp8266_data.get('device', {})].append_data,
                    (time_check, [streams[esp8266_data.get('device', {})]],
                     # (streams[data.get('topic', {})].append_data,
                     {"new_temp": temperature,
                      "temp_sensor": esp8266_data.get('temp_f', {}).get('sensor', None),
                      "new_humidity": humidity,
                      "humidity_sensor": esp8266_data.get('humidity', {}).get('sensor', None)}
                     )
                )   # end task_queue.put
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
    # return_data = f"snd->{esp8266_data}"
    task_queue.put((socketio.emit, ['mqtt_message', data], {"namespace": '/'}))
    # task_queue.put(
    #     (mqtt.publish, ['test/littleguy', return_data.encode()], {}))


if __name__ == '__main__':
    # app.run(debug=True, port=80, host='0.0.0.0')
    socketio.run(app, host="0.0.0.0", debug=True)
