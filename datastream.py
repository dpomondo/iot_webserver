from math import nan
from datetime import datetime, timedelta
import pickle

dashes = [[3, 4], [2, 2], [5, 9], [2, 4], [5, 2], []]
temperature_colors = ["FireBrick", "DarkRed", "DeepPink", "Red"]
humidity_colors = ["DodgerBlue", "DeepSkyBlue", "CadetBlue", "CornflowerBlue"]

data_dir = "data"


class DataStream:
    def __init__(self, name, mqtt_address, data_length, time_delta):
        self.name = name
        self.mqtt_address = mqtt_address

        self.mqtt_resets = 0
        self.wireless_resets = 0
        self.watchdog_resets = 0
        self.vsys = 0.0

        self.temperature_data = []
        self.humidity_data = []
        self.time_data = []
        # get rid of this hardcoded number
        self.data_length = data_length
        self.write_delta = time_delta
        self.line_dash = dashes.pop()
        self.temp_line_color = temperature_colors.pop()
        self.hum_line_color = humidity_colors.pop()
        self.previous_write = datetime.now() - self.write_delta
        self.new_data_flag = False
        try:
            with open(data_dir + "/" + str(self.name).replace("/", "_") + ".pickle", "rb") as fp:
                bak = pickle.load(fp)
                self.temperature_data = bak["temp"]
                self.humidity_data = bak["humidity"]
                self.time_data = bak["time"]
        except FileNotFoundError:
            fp = open(data_dir + "/" + self.name.replace("/", "_") + ".pickle", "x")
            fp.close()
            print("File Not Found, setting all values to nan")
            for i in range(self.data_length):
                self.temperature_data.append(nan)
                self.humidity_data.append(nan)
                self.time_data.append(nan)
        except KeyError:
            print("Bad Key during initialization, setting all values to nan")
            for i in range(self.data_length):
                self.temperature_data.append(nan)
                self.humidity_data.append(nan)
                self.time_data.append(nan)

    def append_data(self, new_temp, new_humidity):
        name_tag = str(self.name).replace("/", "_")
        self.temperature_data.append(new_temp)
        self.humidity_data.append(new_humidity)
        self.time_data.append(datetime.today())
        while len(self.temperature_data) > self.data_length:
            self.temperature_data.pop(0)
            self.humidity_data.pop(0)
            self.time_data.pop(0)
        assert len(self.temperature_data) == len(self.humidity_data)
        assert len(self.time_data) == len(self.temperature_data)
        print(f"----------------------------\n{self.name} has new data:\n\t{
              self.temperature_data}\n\t{self.humidity_data}\n\t{self.time_data}")
        with open(data_dir + "/" + name_tag + ".pickle", "wb") as fp:
            bak = {"temp": self.temperature_data,
                   "humidity": self.humidity_data,
                   "time": self.time_data}
            pickle.dump(bak, fp)

    def __str__(self):
        return f"name: {self.name}\taddress: {self.mqtt_address}\n\tline colors: {self.temp_line_color}, {self.hum_line_color}\n\tdashes: {self.line_dash}"
