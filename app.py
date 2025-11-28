from flask import Flask, render_template, jsonify, send_file
import threading
import asyncio
from scraper import scrape_all, PROGRESS

app = Flask(__name__)

SCRAPER_RUNNING = False  # prevents duplicate runs

def background_scraper():
    global SCRAPER_RUNNING
    SCRAPER_RUNNING = True
    try:
        asyncio.run(scrape_all())
    finally:
        SCRAPER_RUNNING = False


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/start")
def start():
    global SCRAPER_RUNNING

    if SCRAPER_RUNNING:
        return jsonify({"status": "already_running"})

    # Start background thread
    thread = threading.Thread(target=background_scraper, daemon=True)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/progress")
def progress():
    return jsonify(PROGRESS)


@app.route("/download")
def download():
    return send_file("gem_full_fixed.csv", as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
