from flask import Flask, request, jsonify
from fraud_model import predict_fraud
from certificate_auth import generate_user_certificate

app = Flask(__name__)

@app.route('/login', methods=['POST'])
def login():
    image = request.files['passport']
    username = request.form.get('username')

    result = predict_fraud(image)

    if result == "REAL":
        cert = generate_user_certificate(username)
        return jsonify({"status": "APPROVED", "cert": cert})
    else:
        return jsonify({"status": "REJECTED"})

if __name__ == "__main__":
    app.run(ssl_context=('pki/server.crt','pki/server.key'))
