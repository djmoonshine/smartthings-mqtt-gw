import requests
import paho.mqtt.client as mqtt
import jsonpath
import json
import time


def get_status(auth_token, device_id):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + auth_token,
    }
    url = "https://api.smartthings.com/v1/devices/" + device_id + "/status"
    try:
        response = requests.get(url, headers=headers)
        return(response.text)
    except:
        print("Error communicating with api")
        return("")


def set_temperature(auth_token, device_id, temp):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + auth_token,
    }
    data = {"commands": [{
      "component": "main",
      "capability": "thermostatCoolingSetpoint",
      "command": "setCoolingSetpoint",
      "arguments": [
        temp
      ]}]}
    url = "https://api.smartthings.com/v1/devices/" + device_id + "/commands"
    print(data)
    try:
        response = requests.post(url, json=data, headers=headers)
    except:
        print("Error communicating with api")

    print("Http status response " + str(response.status_code))


def set_mode(auth_token, device_id, mode):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + auth_token,
    }
    data = {"commands": [{
        "component": "main",
        "capability": "airConditionerMode",
        "command": "setAirConditionerMode",
        "arguments": [
            mode
        ]}]}
    url = "https://api.smartthings.com/v1/devices/" + device_id + "/commands"
    try:
        response = requests.post(url, json=data, headers=headers)
    except:
        print("Error communicating with api!")
    print(response.status_code)


def send_ha_mqtt_discovery(device_id, name):
    msg = {
        "name": name,
        "mode_cmd_t": "homeassistant/climate/" + device_id + "/setMode",
        "mode_stat_t": "homeassistant/climate/" + device_id + "/state/mode",
        "avty_t": "homeassistant/climate/" + device_id + "/available",
        "pl_avail": "online",
        "pl_not_avail": "offline",
        "temp_cmd_t": "homeassistant/climate/" + device_id + "/setTemp",
        "temp_stat_t": "homeassistant/climate/" + device_id + "/state/target_temp",
        "curr_temp_t": "homeassistant/climate/" + device_id + "/state/measured_temp",
        "min_temp": "15",
        "max_temp": "25",
        "temp_step": "1",
        "modes": ["heat", "cool"]
    }
    print("Publishing " + str(msg).replace("'", '"'))
    client.publish("homeassistant/climate/" + device_id + "/config", str(msg).replace("'", '"'))


def set_temp_callback(client, userdata, message):
    message.payload = message.payload.decode("utf-8")
    temp = round(float(message.payload))
    print("Setting temperature to: " + str(temp))
    set_temperature(token,device,int(temp))
    time.sleep(3)
    send_state()


def set_mode_callback(client, userdata, message):
    message.payload = message.payload.decode("utf-8")
    print("Setting mode to: " + str(message.payload))
    set_mode(token,device,str(message.payload))
    client.publish("homeassistant/climate/" + device + "/state/mode", str(message.payload))
    time.sleep(5)


def on_connect(clientt, userdata, flags, rc):
    if rc == 0:
        print("Connected to broker")
        print("Sending discovery message to HA")
        send_ha_mqtt_discovery(device,"Luftvarmepump")
        print("Subscibing to topics")
        client.subscribe("homeassistant/climate/" + device + "/setTemp")
        client.message_callback_add("homeassistant/climate/" + device + "/setTemp", set_temp_callback)
        client.subscribe("homeassistant/climate/" + device + "/setMode")
        client.message_callback_add("homeassistant/climate/" + device + "/setMode", set_mode_callback)
        send_state()


def send_state():
    status = get_status(token, device)
    # print(status)
    # print(jp.match1('$.components.main.airConditionerMode.airConditionerMode.value', status))
    # print(jp.match1('$.components', status))
    if status != "":

        json2 = json.loads(status)
        mode = jsonpath.jsonpath(json2, '$.components.main.airConditionerMode.airConditionerMode.value')[0]
        target_temp = jsonpath.jsonpath(json2, '$.components.main.thermostatCoolingSetpoint.coolingSetpoint.value')[0]
        measured_temp = jsonpath.jsonpath(json2, '$.components.main.temperatureMeasurement.temperature.value')[0]
        power = jsonpath.jsonpath(json2, '$.components.main.switch.switch.value')[0]
        energy_used = jsonpath.jsonpath(json2, '$.components.main.powerConsumptionReport.powerConsumption.value.persistedEnergy')[0]
        energy_used = energy_used / 1000
        print(time.time())
        print("Mode " + mode)
        print("Target temp " + str(target_temp))
        print("Measured temp " + str(measured_temp))
        print("Power " + power)
        print("Total energy used " + str(energy_used) + "kWh")
        state = {
            "mode":mode,
            "target_temp":target_temp,
            "current_temp":measured_temp,
        }
        client.publish("homeassistant/climate/" + device + "/available", "online")
        client.publish("homeassistant/climate/" + device + "/state/mode", mode)
        client.publish("homeassistant/climate/" + device + "/state/target_temp", str(target_temp))
        client.publish("homeassistant/climate/" + device + "/state/measured_temp", str(measured_temp))
        #client.publish("homeassistant/climate/" + device + "/state/", str(state))


with open('config.json', 'r') as f:
    config = json.load(f)
    token = config['TOKEN']
    device = config['DEVICE']
    mqtt_user = config['MQTT_USER']
    mqtt_pwd = config['MQTT_PWD']
    mqtt_address = config['MQTT_ADDRESS']


client = mqtt.Client()
client.username_pw_set(mqtt_user, password=mqtt_pwd)
client.will_set("homeassistant/climate/" + device + "/available","offline",1,retain=False)
client.on_connect = on_connect
print("Connecting to broker")
client.connect(mqtt_address, port=1883, keepalive=60, bind_address="")
last_time = 0
last_discovery_time = time.time()
while True:
    client.loop_start()
    if time.time() - last_time > 30:
        send_state()
        last_time = time.time()
    if time.time() - last_discovery_time > 1800:
        send_ha_mqtt_discovery(device,"Luftvarmepump")
        last_discovery_time = time.time()
    time.sleep(10)
    client.loop_stop()