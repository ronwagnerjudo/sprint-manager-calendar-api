from flask import Flask, jsonify, request
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


CLIENT_SECRET_FILE = "client_secret.json"
SCOPS = ["https://www.googleapis.com/auth/calendar"]
API_VERSION = "v3"
API_NAME = "calendar"

cred = Credentials.from_authorized_user_file(CLIENT_SECRET_FILE, SCOPS)

service = build(API_NAME, API_VERSION, cred)

app = Flask(__name__)

@app.route("/new_task", methods=["POST"])
def create_new_task():
    event = {
  'summary': 'task_name',#getting tathe task name froom the database
  'start': {
    'dateTime': '2015-05-28T09:00:00-07:00',
    'timeZone': 'Asia/Jerusalem',
  },
  'end': {
    'dateTime': '2015-05-28T17:00:00-07:00',
    'timeZone': 'Asia/Jerusalem',
  },
}

    event = service.events().insert(calendarId='primary', body=event).execute()




if __name__ =="__main__":
    app.run(debug=True)