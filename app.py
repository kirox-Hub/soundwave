from flask import Flask, render_template, request, jsonify, session, redirect
import json, os, hashlib, urllib.request, urllib.parse

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "soundwave_dev_key_2024")

UPLOAD_FOLDER = os.path.join("static", "uploads")
DATA_FILE = "data/users.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("data", exist_ok=True)

def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE) as f:
        return json.load(f)

def save_users(users):
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, indent=2)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

@app.route("/")
def index():
    return render_template("index.html", user=session.get("user"))

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    users = load_users()
    if data["email"] in users:
        return jsonify({"error": "Email déjà utilisé"}), 400
    users[data["email"]] = {
        "name": data["name"], "email": data["email"],
        "password": hash_pw(data["password"]), "plan": "free"
    }
    save_users(users)
    session["user"] = {"name": data["name"], "email": data["email"], "plan": "free"}
    return jsonify({"ok": True, "user": session["user"]})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    users = load_users()
    u = users.get(data["email"])
    if not u or u["password"] != hash_pw(data["password"]):
        return jsonify({"error": "Email ou mot de passe incorrect"}), 401
    session["user"] = {"name": u["name"], "email": u["email"], "plan": u["plan"]}
    return jsonify({"ok": True, "user": session["user"]})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/upgrade", methods=["POST"])
def upgrade():
    if not session.get("user"):
        return jsonify({"error": "Non connecté"}), 401
    users = load_users()
    email = session["user"]["email"]
    users[email]["plan"] = "premium"
    save_users(users)
    session["user"]["plan"] = "premium"
    return jsonify({"ok": True})

@app.route("/upload", methods=["POST"])
def upload():
    if not session.get("user") or session["user"]["plan"] != "premium":
        return jsonify({"error": "Réservé aux membres Premium"}), 403
    f = request.files.get("file")
    if not f or not f.filename.endswith(".mp3"):
        return jsonify({"error": "Fichier MP3 requis"}), 400
    safe = f.filename.replace(" ", "_")
    f.save(os.path.join(UPLOAD_FOLDER, safe))
    return jsonify({"ok": True, "filename": safe, "url": f"/static/uploads/{safe}"})

@app.route("/my-uploads")
def my_uploads():
    files = []
    for fn in os.listdir(UPLOAD_FOLDER):
        if fn.endswith(".mp3"):
            files.append({"name": fn.replace(".mp3","").replace("_"," "), "url": f"/static/uploads/{fn}"})
    return jsonify(files)

@app.route("/search-yt")
def search_yt():
    if not session.get("user"):
        return jsonify({"error": "Connexion requise"}), 401
    plan = session["user"]["plan"]
    q = request.args.get("q", "")
    if not q:
        return jsonify([])
    try:
        encoded = urllib.parse.quote(q)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="ignore")
        import re
        ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        titles = re.findall(r'"title":{"runs":\[{"text":"([^"]+)"', html)
        results = []
        seen = set()
        for vid, title in zip(ids, titles):
            if vid not in seen:
                seen.add(vid)
                results.append({
                    "id": vid, "title": title,
                    "thumbnail": f"https://img.youtube.com/vi/{vid}/mqdefault.jpg",
                    "embed": f"https://www.youtube.com/embed/{vid}?autoplay=1",
                })
            if len(results) >= (10 if plan == "premium" else 3):
                break
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/session-info")
def session_info():
    return jsonify(session.get("user"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
