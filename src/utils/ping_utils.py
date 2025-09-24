from collections import deque
from dataclasses import dataclass
import logging
from typing import Dict, List
import uuid
from tcp_latency import measure_latency
import threading
import time
import multiprocessing as mp
import statistics
from matplotlib import pyplot as plt
import datetime

DEFAULT_PORT = 8585
MAX_QUEUE_SIZE = 40 * 300 # 40 channels, (60 * 10) / 5 -> 300 elements per channel, roughly 10 minutes

logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
logger.addHandler(ch)

@dataclass
class Packet:
    channel: int
    ping: int
    time: datetime
    success: bool

CHANNEL_TO_IP = {
    1: "35.155.204.207",
    2: "52.26.82.74",
    3: "34.217.205.66",
    4: "35.161.183.101",
    5: "54.218.157.183",
    6: "52.25.78.39",
    7: "54.68.160.34",
    8: "34.218.141.142",
    9: "52.33.249.126",
    10: "54.148.170.23",
    11: "54.201.184.26",
    12: "54.191.142.56",
    13: "52.13.185.207",
    14: "34.215.228.37",
    15: "54.187.177.143",
    16: "54.203.83.148",
    17: "54.148.188.235",
    18: "52.43.83.76",
    19: "54.69.114.137",
    20: "54.148.137.49",
    21: "54.212.109.33",
    22: "44.230.255.51",
    23: "100.20.116.83", 
    24: "54.188.84.22",
    25: "34.215.170.50",
    26: "54.184.162.28",
    27: "54.185.209.29",
    28: "52.12.53.225",
    29: "54.189.33.238",
    30: "54.188.84.238",
    31: "44.234.162.14",
    32: "44.234.162.13",
    33: "44.234.161.92",
    34: "44.234.161.48",
    35: "44.234.160.137",
    36: "44.234.161.28",
    37: "44.234.162.100",
    38: "44.234.161.69",
    39: "44.234.162.145",
    40: "44.234.162.130"
}

class PingCheckingThread(threading.Thread):
    def __init__(self, result_queue: mp.Queue, channel: int, ip_addr: str, port: int):
        threading.Thread.__init__(self)
        self._result_queue = result_queue
        self._ip_addr = ip_addr
        self._port = port
        self._channel = channel
        self._handled = False
    
    def run(self):
        while True:
            time.sleep(2)
            latency = measure_latency(host=self._ip_addr, port=self._port)
            ping = 0
            success = False
            
            if latency:
                ping = int(latency[0])
                success = True

            current_timestamp = datetime.datetime.now()
            packet = Packet(channel=self._channel, ping=ping, time=current_timestamp, success=success)
            while self._result_queue.qsize() > MAX_QUEUE_SIZE:
                self._result_queue.get()
            self._result_queue.put(packet)

def main():
    queue = mp.Queue() 

    # Stores a history of pings
    channel_ping_history: Dict[int, deque] = {}

    # Stores the channel ping average
    channel_ping_averages: Dict[int, float] = {}

    for channel, ip_addr in CHANNEL_TO_IP.items():
        channel_thread = PingCheckingThread(result_queue=queue, channel=channel, ip_addr=ip_addr, port=DEFAULT_PORT)
        channel_thread.start()
        channel_ping_history[channel] = deque([], 60)

    while True:
        # update every time we get a new ping result in the queue
        if queue.qsize() != 0:
            packet = queue.get()
            channel_ping_history[packet.channel].append(packet)
        
            for channel in CHANNEL_TO_IP.keys():
                pings = [packet.ping for packet in channel_ping_history[channel]]

                if len(pings) != 0:
                    channel_avg = round(statistics.mean(pings), 2)
                    channel_ping_averages[channel] = channel_avg
                
                sorted_pings = sorted(channel_ping_averages.items(), key=lambda x: x[1])
            

            channel_1_pings = [packet.ping for packet in channel_ping_history[1]]
            channel_1_times = [packet.time for packet in channel_ping_history[1]]
            plt.close()
            #plt.style.use("~/gpq-bot/src/spooky.mplstyle")
            plt.title('Channel Ping history', fontsize='xx-large')
            plt.plot(channel_1_pings, color = '#46FFD1', linewidth=1)
            import os
            file_location = os.path.join('/home/pi/gpq-bot/src/', 'channel_1' + '.png')
            plt.savefig(file_location)
        
        

if __name__ == "__main__":
    main()
    
