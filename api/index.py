from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return 'Hello, World!'
    
@app.route("/ranking", methods=["POST"])
def ranking():
    body = request.get_json()
    eventCode = body.get("eventCode")
    return jsonify({"eventCode": eventCode})


