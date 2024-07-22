from flask import Flask, render_template, request
import time
import csv
from utilities import make_filename

app = Flask(__name__)
count = 0
esp8266_data = 0


@app.route('/query-data', methods=['GET'])
def take_in_data():
    global esp8266_data
    fil_nam = make_filename()
    esp8266_data = request.args.get('data')

    tim_stam = time.asctime()
    with open(fil_nam, 'a') as t:
        writer = csv.writer(t, delimiter=',')
        writer.writerow([tim_stam, esp8266_data])

    return f"data: {request.args.get('data')}"


@app.route('/', methods=['GET', 'POST'])
def index():
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
                           data=esp8266_data
                           )


if __name__ == '__main__':
    app.run(debug=True, port=80, host='0.0.0.0')
