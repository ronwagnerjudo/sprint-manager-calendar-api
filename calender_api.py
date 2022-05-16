from flask import Flask, jsonify, request
from google_apis import create_service


CLIENT_SECRET_FILE = "client_secret.json"
SCOPS = ["https://www.googleapis.com/auth/calendar"]
API_VERSION = "v3"
API_NAME = "calendar"

service = create_service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPS)






# app = Flask(__name__)

# @app.route("/new_task", methods=["POST"])
# def create_new_task():
  #pass

# if __name__ =="__main__":
    # app.run(debug=True)


