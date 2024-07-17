from flask import Flask, render_template

app = Flask(__name__)
count = 0


@app.route('/')
def index():
    global count
    count += 1
    templateData = {
        'title': "Hello!",
        'num': count
    }
    return render_template('index.html', **templateData)


if __name__ == '__main__':
    app.run(debug=True, port=80, host='0.0.0.0')
