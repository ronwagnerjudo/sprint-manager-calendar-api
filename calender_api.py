from flask import Flask, jsonify, request
from google_apis import create_service
from datetime import datetime, timedelta

CLIENT_SECRET_FILE = "client_secret.json"
SCOPS = "https://www.googleapis.com/auth/calendar"
API_VERSION = "v3"
API_NAME = "calendar"



service = create_service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPS)

get_calendars_events = service.events().list(calendarId='primary').execute()


class FindTaskTime():
  def __init__(self):
    self.events_times = []
    self.events_in_same_day = []
    self.start_time = ""

  def check_availability_for_task(self, task_time):
    now = datetime.now()
    today = datetime.today()

    for date in get_calendars_events:
      string_start_time = date["items"]["start"]["dateTime"]
      formated_start_time=string_start_time.split("+")[0]
      start_time_to_datetime = datetime.strptime(formated_start_time, "%Y-%m-%dT%H:%M:%S")

      string_end_time = date["items"]["end"]["dateTime"]
      formated_end_time=string_end_time.split("+")[0]
      end_time_to_datetime = datetime.strptime(formated_end_time, "%Y-%m-%dT%H:%M:%S")

      if now < start_time_to_datetime:
        self.events_times.append(start_time_to_datetime, end_time_to_datetime)

    for day in range(14):
      start_time = today + timedelta(days=day)
      end_time = start_time + timedelta(hours=task_time)

      if start_time.strftime("%A") == "Friday" or start_time.strftime("%A") == "Saturday":
        continue
      
      for event in self.events_times[::2]:
        if event.day == start_time.day:
          self.events_in_same_day.append(event)
        elif self.events_in_same_day == []:
          self.start_time = f"{start_time.year}-{start_time.month}-{start_time.day}T09:00:00"
          return True
    # if (09:00 <= start_time and end_time_to_datetime <  start_time) and ( end_time < start_time_to_datetime or end_time < 19:00)
    

app = Flask(__name__)

@app.route("/new_task", methods=["POST"])
def create_new_task():
    user_name = request.form.get("username")
    task_name = request.form.get("task_name")
    task_time = request.form.get("task_time")
    
    event = {
      'summary': task_name,
      'start': {
        'dateTime': task_time,
        'timeZone': 'Asia/Jerusalem',
      },
      'end': {
        'dateTime': task_time,
        'timeZone': 'Asia/Jerusalem',
      }
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    return jsonify({"task name": user_name}), 200

@app.route("update", methods=["PUT"])
def update_task():
  pass

@app.route("delete", methods=["DELETE"])
def delete_task():
  pass


if __name__ =="__main__":
    app.run(debug=True, port=8080)


# '2022-05-10T21:00:00'

