import hmac
import json
import os
import time
from threading import Thread

from flask import Flask, Response, jsonify, request

import store

app = Flask(__name__)
READ_KEY = os.environ.get('STORE_READ_KEY', '')


def _authorised():
    """Readers must send the read key in the X-Store-Key header. It is never put in the web address."""
    key = request.headers.get('X-Store-Key', '')
    return bool(READ_KEY) and hmac.compare_digest(key, READ_KEY)


@app.route('/')
def index():
    return "Rex Signal Bot is alive!"


@app.route('/signals')
def signals():
    if not _authorised():
        return jsonify({"error": "unauthorised"}), 401
    return jsonify(store.latest())


@app.route('/signals/stream')
def signals_stream():
    if not _authorised():
        return jsonify({"error": "unauthorised"}), 401
    after = request.args.get('after', default=0, type=int)

    def events():
        last = after
        while True:
            rows = store.list_since(last)
            for row in rows:
                last = row['id']
                yield f"id: {row['id']}\ndata: {json.dumps(row)}\n\n"
            if not rows:
                yield ": keep-alive\n\n"  # a comment line keeps the connection open
                time.sleep(2)

    return Response(events(), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache'})


def run():
    port = int(os.environ.get('PORT', 8080))  # Railway sets PORT for the public address
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    t = Thread(target=run)
    t.start()
