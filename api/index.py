from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # ← Habilita CORS en todo

@app.route('/')
def home():
    return 'Hello, World!'
    
@app.route("/ranking", methods=["POST"])
def ranking():
    body = request.get_json()
    eventCode = body.get("eventCode")
    return jsonify({"eventCode": eventCode})


