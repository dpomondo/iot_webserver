### iot_webserver

A basic webserver made with python & Flask, to accept data sent from various Raspberry Pi Picos and ESP8266 boards, for the purpose of saving and displaying that information via a <gasp> web page.

```
flask run --host=0.0.0.0 --no-debug
```
With flask-mqtt implemented, we need to turn off 'auto-restart on save' behavior.
