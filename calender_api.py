from flask import Flask, jsonify, request
from google_apis import create_service
from datetime import datetime, timedelta
import requests
from pprint import pprint

CLIENT_SECRET_FILE = "client_secret.json"
SCOPS = "https://www.googleapis.com/auth/calendar"
API_VERSION = "v3"
API_NAME = "calendar"


service = create_service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPS)

today = datetime.today()
after_14_days = today + timedelta(days=14)

body = {
  "timeMin": f"{today.isoformat()}Z",
  "timeMax": f"{after_14_days.isoformat()}Z",
  "timeZone": 'Asia/Jerusalem',
  "items": [
    {
      "id": "primary"
    }
  ]
}

def get_event_id(event_name):
  events = service.events().list(calendarId='primary', timeMin=f"{today.isoformat()}Z").execute()
  for i in range(len(events)):
   for e in events["items"][i]:
     if e["summary"] == event_name:
       return e["id"]


def find_first_open_slot(start_time, end_time, duration):

  def datetime_to_string(time):
    return datetime.strftime(time, '%Y-%m-%dT%H:%M:%S')

  def parse_date(raw_date):
    #Transform the datetime given by the API to a python datetime object.
    formated_date = raw_date.split("+")[0]
    return datetime.strptime(formated_date, '%Y-%m-%dT%H:%M:%S')
  
  get_events_date = service.freebusy().query(body=body).execute()
  event_starts = [parse_date(e['start']) for e in get_events_date["calendars"]["primary"]["busy"]]
  event_ends = [parse_date(e['end']) for e in get_events_date["calendars"]["primary"]["busy"]]
    
  gaps = [start-end for (start,end) in zip(event_starts[1:], event_ends[:-1])]

  if start_time + duration < event_starts[0]:
      #A slot is open at the start of the desired window.
      return datetime_to_string(start_time)
    
  if end_time > event_ends[:-1]:
    #If there's a gap between the end of the last event and end time.
    enday_gap = end_time - event_ends[:-1]
    gaps.append(enday_gap)

  for i, gap in enumerate(gaps):
    if gap > duration:
      #This means that a gap is bigger than the desired slot duration, and we can "squeeze" a meeting.
      #Just after that meeting ends.
      return datetime_to_string(event_ends[i])

  #If no suitable gaps are found, return none.
  return None

def find_availble_day(duration):
  for d in range(14):
    start_day_time = today + timedelta(days=d)

    if start_day_time.strftime("%A") == "Friday" or start_day_time.strftime("%A") == "Saturday":
      continue

    if start_day_time.month < 10:
      month = f"0{start_day_time.month}"
    else:
      month = start_day_time.month
    if start_day_time.day < 10:
      day = f"0{start_day_time.day}"
    else:
      day = start_day_time.day
    s_time = f"{start_day_time.year}-{month}-{day}T09:00:00"
    datetime_s_time = datetime.strptime(s_time, '%Y-%m-%dT%H:%M:%S')
    e_time = f"{start_day_time.year}-{month}-{day}T19:00:00"
    datetime_e_time = datetime.strptime(e_time, '%Y-%m-%dT%H:%M:%S')

    if find_first_open_slot(datetime_s_time, datetime_e_time, duration) != None:
      return find_first_open_slot(datetime_s_time, datetime_e_time, duration)
    


app = Flask(__name__)

@app.route("/new_task", methods=["POST"])
def create_new_task():
    user_name = request.form.get("username")
    task_name = request.form.get("task_name")
    task_time = request.form.get("task_time")
    
    start_time = find_availble_day(task_time)
    end_time = start_time + timedelta(hours=task_time)

    event = {
      'summary': task_name,
      'start': {
        'dateTime': start_time,
        'timeZone': 'Asia/Jerusalem',
      },
      'end': {
        'dateTime': end_time,
        'timeZone': 'Asia/Jerusalem',
      }
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    return jsonify(event = {'summary': task_name, 'start': {'dateTime': start_time,'timeZone': 'Asia/Jerusalem',}, 'end': {'dateTime': end_time,'timeZone': 'Asia/Jerusalem',}}), 200

@app.route("/update", methods=["PUT"])
def update_task():
  user_name = request.form.get("username")
  task_name = request.form.get("task_name")
  task_time = request.form.get("task_time")

  event_id = get_event_id(task_name)
  update_event = service.events().get(calendarId='primary', eventId=event_id).execute()

  if find_availble_day(task_time) != None:
    start_time = find_availble_day(task_time)
    end_time = start_time + timedelta(hours=task_time)

    update_event['summary'] = task_name
    update_event['start'] = {
          'dateTime': start_time,
          'timeZone': 'Asia/Jerusalem',
        }
    update_event['end'] = {
          'dateTime': end_time,
          'timeZone': 'Asia/Jerusalem',
        }
    update_event = service.events().update(calendarId='primary', eventId=update_event['id'], body=update_event).execute()
    return jsonify(event = {'summary': task_name, 'start': {'dateTime': start_time,'timeZone': 'Asia/Jerusalem',}, 'end': {'dateTime': end_time,'timeZone': 'Asia/Jerusalem',}}), 200

  else:
    return jsonify({"error": "couldn't find free time for the task"}), 404


@app.route("/delete", methods=["DELETE"])
def delete_task():
  task_name = request.form.get("task_name")
  event_id = get_event_id(task_name)
  service.events().delete(calendarId='primary', eventId=event_id).execute()
  return jsonify({""})


if __name__ =="__main__":
    app.run(debug=True, port=8080)




