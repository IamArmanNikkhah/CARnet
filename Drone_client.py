# -*- coding: utf-8 -*-
"""DRONE-client.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1XOqDF04_gOYYvlMdfX1NF_1APDq5CdhX
"""

import socket
import time
import cv2
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
from threading import Thread
import concurrent.futures
from picamera import PiCamera

class AirDRONE:
  def __init__(self):
    self.proximeter       = Proximeter()
    ip, in_port, out_port = self.get_input()
    self.netSender        = Client(ip, in_port, out_port)
    self.saving_directory = '/home/pi/Desktop/'
    self.timetable_dict   = {}                  #sent time: | sugested wait time: | real wait time :

  def get_input(self):
    ip = input("Enter IP address: ")
    in_port = input("Enter in_port: ")
    out_port = input("Enter out_port: ")
    return ip, in_port, out_port
  
  
  def capture_photo(self, filename):
    camera        = PiCamera()
    saved_dir     = self.saving_directory + filename + '.jpg'
    time.sleep(5)
    camera.capture(saved_dir)
    camera.close()
    return saved_dir, filename

  def record_sentTime(self,filename, sugessted_time):
      self.proximeter.record_sendTime(filename)
      current        = self.proximeter.get_time()
      real_time      = None
      self.timetable_dict[filename] = [current, sugessted_time, real_time]
      return current

  def record_reciveTime(self, filename):
    self.proximeter.record_reciveTime(filename)
    real_time                        = self.proximeter.get_time()
    self.timetable_dict[filename][2] = real_time

  
  def add_INDXbytes(self, byte_data, num):
    byte_data   = bytearray(byte_data)
    byte_to_add = num.to_bytes(2, byteorder='big')
    byte_data.extend(byte_to_add)
    return bytes(byte_data)
  
  def process_image(self, img_dir):
      myfile = open(img_dir, 'rb')
      bytes = myfile.read()
      return bytes

  def send_image(self, indx, img_dir): # 0 =< indx <= 9
      image_bytes = self.process_image(img_dir)
      final_bytes = self.add_INDXbytes(image_bytes, indx)
      self.netSender.send(final_bytes)

  def runDrone(self):
    img_counter = 0
    while True:
      
      capured_image, filename   = self.capture_photo(str(img_counter))
      self.send_image(img_counter%20, capured_image)
      sugested_wait  = self.proximeter.suggest_waitingTime()
      sent_time      = self.record_sentTime(filename,sugested_wait)
      with concurrent.futures.ThreadPoolExecutor() as executor:
        f1 = executor.submit(self.timesUP, sent_time, sugested_wait)
        f2 = executor.submit(self.recive)
        futures ={f1,f2}
      
      for fut in concurrent.futures.as_completed(futures):
        res = fut.result()
        if res[0] == 'RECIVED':  
          loc      = res[1]
          filename = self.extract_filename_fromlocation(loc)
          self.record_reciveTime(filename)
          

        if res[0] == 'TIMES UP': break
  
  def recive(self):
    loc = self.netSender.recive_location()
    return ['RECIVED' , loc]

  def timesUP(self, sent_time, sugested_wait):
    sentTime_plus_sugestedWait =self.proximeter.add_time(sent_time,sugested_wait)
    while True:
      current    = self.proximeter.get_time()
      if  self.proximeter.time_diff_real(current, sentTime_plus_sugestedWait) < 0:
        return ['TIMES UP']
    
    return ['FAIL']

  def extract_filename_fromlocation(self, string):
    start = string.find('#')
    end = string.find('#', start + 1)
    return string[start + 1:end]

class Proximeter:
  def __init__(self):
    self.timeTable_dict = {}
    self.elapsedTime    = []
  
  def get_time():
    return datetime.utcnow().strftime('%H:%M:%S.%f')

  def convert_to_seconds(self, time):
    """
    Convert a time string to seconds.
    """
    # Split the time into hours, minutes, seconds, and milliseconds
    time_split = time.split(':')
    hours = int(time_split[0])
    minutes = int(time_split[1])
    seconds = int(time_split[2].split('.')[0])
    milliseconds = int(time_split[2].split('.')[1])
    # Convert the time to seconds
    time_sec = (hours * 3600) + (minutes * 60) + seconds + (milliseconds / 1000)
    return time_sec

  def convert_to_time(self, time):
    """
    Convert a time in seconds to a string.
    """
    # Convert the time to hours, minutes, seconds, and milliseconds
    hours = int(time / 3600)
    minutes = int((time % 3600) / 60)
    seconds = int((time % 3600) % 60)
    milliseconds = int((time % 3600 % 60 % 1) * 1000)
    # Convert the time to a string
    time_str = '{:02d}:{:02d}:{:02d}.{:03d}'.format(hours, minutes, seconds, milliseconds)
    return time_str

  def add_time(self, time1, time2):
    """
    Add two times together.
    """
    # Convert the times to seconds
    time1_sec = convert_to_seconds(time1)
    time2_sec = convert_to_seconds(time2)
    # Add the times together
    total_time = time1_sec + time2_sec
    # Convert the total time back to a string
    total_time_str = convert_to_time(total_time)
    return total_time_str

  def time_diff(self, t1, t2):
    t1_sec = self.convert_to_seconds(t1)
    t2_sec = self.convert_to_seconds(t2)
    diff = abs(t1_sec - t2_sec)
    return diff

  def time_diff_real(self, t1, t2):  # t1 - t2
    t1_sec = self.convert_to_seconds(t1)
    t2_sec = self.convert_to_seconds(t2)
    diff = t1_sec - t2_sec
    return diff

  def record_reciveTime(self, filename):
    current_time   = self.get_time()
    submited_time  = self.timeTable_dict[filename]
    diffrence_time = self.time_diff(current_time, submited_time)
    self.elapsedTime.append(diffrence_time)

  def record_sendTime(self, filename):
    self.timeTable_dict[filename] = self.get_time()

  def moving_avg(x, N=3):
    cumsum = np.cumsum(np.insert(x, 0, 0))
    return (cumsum[N:] - cumsum[:-N]) / float(N)

  def exp_moving_avg(self, list, alpha=0.125):
    """
    Calculate exponentially weighted moving average of a list
    """
    ema = []
    for i in range(len(list)):
        if i == 0:
            ema.append(list[i])
        else:
            ema.append(alpha * list[i] + (1 - alpha) * ema[i - 1])
    return ema

  def plot_EMA(self):
    plt.plot(self.exp_moving_avg(self.elapsedTime))
    plt.show()

  def suggest_waitingTime(self):
     EMA_list = self.exp_moving_avg(self.elapsedTime)
     return self.convert_to_time(EMA_list[-1])

class Client:
    def __init__(self, ip, in_port, out_port):
      self.ip = ip
      self.out_port = out_port
      self.in_port  = in_port
      self.out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      self.in_sock  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      self.in_sock.bind(('', self.in_port))

    
    def send(self, data):
      self.out_sock.sendto(data, (self.ip, self.out_port))

    def recive_location(self):
      loc, addr = self.in_sock.recvfrom(5555)
      return loc

if __name__ == '__main__':
    drone = AirDRONE()
    drone.runDrone()
