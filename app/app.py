
from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os

app = Flask(__name__)
app.secret_key = "supersecret"
DB = "app.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT)")
    conn.commit(); conn.close()

@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")
    return render_template("dashboard.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method=="POST":
        email=request.form["email"]
        password=generate_password_hash(request.form["password"])
        conn=sqlite3.connect(DB); c=conn.cursor()
        try:
            c.execute("INSERT INTO users(email,password) VALUES (?,?)",(email,password))
            conn.commit()
        except:
            return "User exists"
        conn.close()
        return redirect("/login")
    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form["email"]; password=request.form["password"]
        conn=sqlite3.connect(DB); c=conn.cursor()
        c.execute("SELECT password FROM users WHERE email=?",(email,))
        row=c.fetchone(); conn.close()
        if row and check_password_hash(row[0], password):
            session["user"]=email
            return redirect("/")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

@app.route("/forgot", methods=["GET","POST"])
def forgot():
    return render_template("forgot.html")

@app.route("/api/health")
def health():
    return jsonify({"status":"ok"})

if __name__=="__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
