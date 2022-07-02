import os
from flask import Flask, jsonify, request
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from datetime import datetime, timedelta
import requests
import logging
from functools import wraps

logging.basicConfig(level=logging.INFO)

GOOGLE_API_VERSION = "v3"
GOOGLE_API_NAME = "calendar"
GOOGLE_SCOPES = ['openid', 'https://www.googleapis.com/auth/calendar', 
		'https://www.googleapis.com/auth/userinfo.email', 
		'https://www.googleapis.com/auth/userinfo.profile']


#------------------------------------------APP CONFIG-------------------------------------------------

app = Flask(__name__)
app.secret_key = os.urandom(12).hex()

#----------------------------------------------------------------------------
def user_details(f):
	@wraps(f)
	def decorated(*args, **kwargs):
		try: 
			response = requests.get("http://127.0.0.1:5000/get-user-details")
			data = response.json()
			creds = data["userCredentials"]
			current_user_credentials = Credentials.from_authorized_user_info(creds, GOOGLE_SCOPES)
			user_preference = data["userPreference"]
			user_sprint_time = data["userSprintTime"]
			user_start_work = data["userStartWorkHours"]
			user_end_work = data["userEndWorkHours"]
		except:
			return jsonify({"message" : "Couldn't get the credentials!"}), 401

		return f(current_user_credentials, user_preference, user_sprint_time, user_start_work, user_end_work, *args, **kwargs)

	return decorated

#------------------------------------------FUNCTIONS---------------------------------------------------

def datetime_to_string(time):
	return datetime.strftime(time, '%Y-%m-%dT%H:%M:%S')

def parse_date(raw_date):
	#Transform the datetime given by the API to a python datetime object.
	formated_date = raw_date.split("+")[0]
	return datetime.strptime(formated_date, '%Y-%m-%dT%H:%M:%S')

def first_open_slot(start_time, duration, event_starts, gaps, event_ends):
	if start_time + timedelta(hours=duration) < event_starts[0]:
		#A slot is open at the start of the desired window.
		return datetime_to_string(start_time)
		

	for i, gap in enumerate(gaps):
		if gap >= timedelta(hours=duration) :
			#This means that a gap is bigger than the desired slot duration, and we can "squeeze" a meeting.
			#Just after that meeting ends.
			return datetime_to_string(event_ends[i])

def find_open_slot(start_time, end_time, duration, service, preference):
	afternoon_default = f"{start_time.year}-{start_time.month}-{start_time.day}T15:00:00"

	body = {
	  "timeMin": f"{datetime_to_string(start_time - timedelta(hours=3))}Z",
	  "timeMax": f"{datetime_to_string(end_time)}Z",
	  "timeZone": 'Asia/Jerusalem',
	  "items": [
		{
		  "id": "primary"
		}
	  ]
   }
	#Getting the events in the day that we want to find available time.
	get_events_date = service.freebusy().query(body=body).execute()
	event_starts = [parse_date(e['start']) for e in get_events_date["calendars"]["primary"]["busy"]]
	event_ends = [parse_date(e['end']) for e in get_events_date["calendars"]["primary"]["busy"]]
	
	gaps = [start-end for (start,end) in zip(event_starts[1:], event_ends[:-1])]

	#First checking if the day is empty or not, if so then schedule according to preference.
	if get_events_date["calendars"]["primary"]["busy"] == []:
		if preference == "morning":
			return datetime_to_string(start_time)
		elif preference == "afternoon":
			afternoon_gap = end_time.hour - 15
			if duration <= afternoon_gap:
				return afternoon_default
			else:
				enday_gap = end_time - timedelta(hours=duration)
				return datetime_to_string(enday_gap)
		else:
			return datetime_to_string(start_time)

	
	if end_time > event_ends[-1]:
		#If there's a gap between the end of the last event and end time.
		enday_gap = end_time - event_ends[-1]
		gaps.append(enday_gap)

	if preference == "morning":
		if start_time + timedelta(hours=duration) < event_starts[0]:
			return datetime_to_string(start_time)
		for i, gap in enumerate(gaps):
			if gap >= timedelta(hours=duration):
				if event_ends[i].hour + duration <= 12:
					return datetime_to_string(event_ends[i])
		#Incase can't schedule according to the user preference.
		return first_open_slot(start_time, duration, event_starts, gaps, event_ends)
		
	
	if preference == "afternoon":
		afternoon_gap = end_time.hour - 15
		if event_ends[-1].hour <= 15 and duration <= afternoon_gap:
			return afternoon_default 
		for i, gap in enumerate(gaps):
			if gap >= timedelta(hours=duration):
				if event_ends[i].hour <= 15:
					continue
				if 15 <= event_ends[i].hour and (event_ends[i].hour + duration) <= end_time.hour:
					return datetime_to_string(event_ends[i])
		#Incase can't schedule according to the user preference.
		return first_open_slot(start_time, duration, event_starts, gaps, event_ends)

	#If no suitable gaps are found, return none.
	return None

def find_availble_day(duration, service, preference, sprint_time, start_work_hours, end_work_hours):
	"""Find availble day and an open slot in the google calendar according to the user preference, duration of the event/task,
	 working hours and until when to look for (in days). using the find_open_slot() function"""

	today = datetime.today()
	for d in range(sprint_time):
		start_day_time = today + timedelta(days=d + 1)

		if start_day_time.strftime("%A") == "Friday" or start_day_time.strftime("%A") == "Saturday":
			continue

		month = f"{start_day_time.month:02d}"
		day = f"{start_day_time.day:02d}"
		s_work_hours = f"{start_work_hours:02d}"
		e_work_hours = f"{end_work_hours:02d}"

		s_time = f"{start_day_time.year}-{month}-{day}T{s_work_hours}:00:00"
		datetime_s_time = datetime.strptime(s_time, '%Y-%m-%dT%H:%M:%S')
		e_time = f"{start_day_time.year}-{month}-{day}T{e_work_hours}:00:00"
		datetime_e_time = datetime.strptime(e_time, '%Y-%m-%dT%H:%M:%S')
		
		open_slot = find_open_slot(datetime_s_time, datetime_e_time, duration, service, preference)

		if open_slot != None:
			return open_slot

	
#-----------------------------------------APP--------------------------------------------------

@app.route("/new_task", methods=["GET", "POST"])
@user_details
def create_new_task(current_user_credentials, user_preference, user_sprint_time, user_start_work, user_end_work):
	service = build(GOOGLE_API_NAME, GOOGLE_API_VERSION, credentials=current_user_credentials)

	task_name = request.form.get("task_name")
	task_time = request.form.get("task_time")
	logging.INFO("getting data from the task-api")

	if task_name != "" or task_time != "":
	
		start_time = find_availble_day(task_time, service, preference=user_preference, sprint_time=user_sprint_time, start_work_hours=user_start_work, end_work_hours=user_end_work)
		if start_time == None:
			return jsonify({"error": "Sorry, but couldn't find availble time"}), 404

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

		logging.INFO("create connection with google and insert new event to the google calendar")
		event = service.events().insert(calendarId='primary', body=event).execute()
		google_event_id = event["id"]
		google_event_starttime = event["start"]["date"]
		logging.INFO("new event inserted")
		return jsonify(event = {'summary': task_name, 'start': {'dateTime': start_time,'timeZone': 'Asia/Jerusalem',}, 'end': {'dateTime': end_time,'timeZone': 'Asia/Jerusalem',}, 'googleEventId': google_event_id, "eventStartDate": google_event_starttime}), 200
	else:
		return jsonify(error={"Not valid": "Sorry, but input/s left empty."}), 404

@app.route("/update", methods=["PUT"])
@user_details
def update_task(current_user_credentials, user_preference, user_sprint_time, user_start_work, user_end_work):
	service = build(GOOGLE_API_NAME, GOOGLE_API_VERSION, credentials=current_user_credentials)

	task_name = request.form.get("task_name")
	task_time = request.form.get("task_time")
	google_event_id = request.form.get("googleEventId")
	logging.INFO("getting data from the task-api")

	# event_id = get_event_id(task_name)
	logging.INFO("retrieve event to update from the google calendar")
	update_event = service.events().get(calendarId='primary', eventId=google_event_id).execute()


	start_time = find_availble_day(task_time, service, preference=user_preference, sprint_time=user_sprint_time,vstart_work_hours=user_start_work, end_work_hours=user_end_work)
	if start_time == None:
		return jsonify({"error": "Sorry, but couldn't find availble time"}), 404

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
	logging.INFO("create connection with google and update event in the google calendar")
	update_event = service.events().update(calendarId='primary', eventId=update_event['id'], body=update_event).execute()
	logging.INFO("event updated")
	return jsonify(event = {'summary': task_name, 'start': {'dateTime': start_time,'timeZone': 'Asia/Jerusalem',}, 'end': {'dateTime': end_time,'timeZone': 'Asia/Jerusalem',}}), 200



@app.route("/delete", methods=["DELETE"])
@user_details
def delete_task(current_user_credentials):
	service = build(GOOGLE_API_NAME, GOOGLE_API_VERSION, credentials=current_user_credentials)

	google_event_id = request.form.get("googleEventId")
	logging.INFO("getting data from the task-api")

	logging.INFO("create connection with google and delete event in the google calendar")
	service.events().delete(calendarId='primary', eventId=google_event_id).execute()
	logging.INFO("event deleted")
	return jsonify(task_name = {"event deleted"}), 200


if __name__ =="__main__":
	app.run(debug=True, port=8080, ssl_context='adhoc')




