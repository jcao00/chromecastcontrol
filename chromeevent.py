"""
    Handles events from a chromecast device, and reports these to various endpoints
"""

import configparser
import json
import time
from chromestate import ChromeState
import paho.mqtt.publish as publish

class ChromeEvent:
    """ Chrome event handling """
    def __init__(self, device, idx, streams):
        config = configparser.ConfigParser()
        config.read('/config/config.ini')
        if "default" in config:
            self.mqtthost = config['default']['mqtthost']
            self.mqttport = int(config['default']['mqttport'])
            self.domoticz = config['default']['domoticz']
        else:
            self.mqtthost = "jarvis"
            self.mqttport = 1883
            self.domoticz = "http://localhost:8080/json.htm"
        self.streams = streams
        self.idx = idx
        self.device = device
        self.device.register_status_listener(self)
        self.device.media_controller.register_status_listener(self)
        self.status = ChromeState(device.device)
        if self.device.cast_type != 'audio':
            self.status.chrome_app = 'Backdrop'

    def getChannelList(self):
        if self.device.cast_type == 'audio':
            return self.streams.getChannelList('audio/mp3')
        else:
            return self.streams.getChannelList('video/mp4')

    def new_cast_status(self, status):
        print("----------- new cast status ---------------")
        print(status)
        app_name = status.display_name
        if app_name == "Backdrop":
            self.status.clear()
        if app_name is None:
            app_name = "None"
            self.status.clear()
        if self.device.media_controller.status.player_state == "PLAYING":
            self.state()
        else:
            self.status.chrome_app = app_name
        self.__mqtt_publish(self.status)

    def new_media_status(self, status):
        print("----------- new media status ---------------")
        print(status)
        if status.player_state != self.status.player_state:
            self.__createstate(status)
            self.__mqtt_publish(self.status)
        if self.status.player_state == 'PLAYING':
            # Netflix is not reporting nicely on play / pause state changes, so we poll it to get an up to date status
            if self.status.chrome_app == 'Netflix':
                time.sleep(1)
                self.device.media_controller.update_status()

            # The following is needed to update radio / tv programme displayed on dashboard
            if self.status.chrome_app == 'Radio' or self.status.chrome_app == 'TV' or self.status.chrome_app == 'DR TV' :
                time.sleep(20)
                self.device.media_controller.update_status()

    def __mqtt_publish(self, msg):
        basetopic = 'dashboard/chromecast/' + self.device.cast_type + '/'
        msg = [
            {'topic': basetopic + 'media', 'payload': (json.dumps(msg.media, default=lambda o: o.__dict__)).encode('utf-8'), 'retain': True },
            {'topic': basetopic + 'app', 'payload': (json.dumps(msg.app, default=lambda o: o.__dict__)).encode('utf-8'), 'retain': True },
            {'topic': basetopic + 'state', 'payload': msg.player_state, 'retain': True },            
            ]

        publish.multiple( msg , hostname=self.mqtthost, port=self.mqttport)

    def stop(self):
        """ Stop playing on the chromecast """
        self.device.media_controller.stop()
        self.status.clear()

    def pause(self):
        """ Pause playback """
        self.device.media_controller.pause()

    def skip(self):
        """ Skip to next track """
        self.device.media_controller.skip()

    def quit(self):
        """ Quit running application on chromecast """
        self.device.media_controller.stop()
        self.device.quit_app()
        self.status.clear()

    def play(self, media=None):
        """ Play a media URL on the chromecast """
        if media is None:
            self.device.media_controller.play()
        else:
            new_media = self.streams.getChannelData(channelId=media)
            if self.device.status.app_id is not None:
                x = self.state()
                if x.player_state == "PLAYING":
                    if x.content == new_media.link:
                        return
            self.device.media_controller.play_media(new_media.link, new_media.media)
            self.__mqtt_publish(self.state())

    def __createstate(self, state):
        self.status.update(state, self.streams)
        return self.status

    def state(self):
        """ Return state of the player """
        if self.device.status.app_id is None:
            self.status.clear()
            return self.status
        if self.device.status.app_id == 'E8C28D3C':
            self.status.clear()
            return self.status
        s = self.device.media_controller.status
        return self.__createstate(s)

    def state_json(self):
        """ Returns status as json encoded string """
        return self.status.json()
