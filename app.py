from flask import Flask, jsonify
from time import sleep
import requests
import threading
import os
from looper import Looper

app = Flask(__name__)

# instantiate looper object and start background processing
# add this crazy hack, otherwise it will be called twice:
#if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
lp = Looper()
thread = threading.Thread(target=lp.start)
thread.start()

@app.route('/api/motion-state', methods=['GET'])
def getCurState():
    return jsonify({"msg": "Current state: {}".format(lp.curState())})

@app.route('/api/motion-state/<int:state>', methods=['PUT', 'GET'])
def toggleMotionDetect(state):

    # stop background process
    if state == 0:
        lp.stop()
        return jsonify({"msg": "Process stopped"})

    # background process already started
    if state == 1 and lp.curState() == 1:
        return jsonify({"msg": "Process already running"})

    # kick off background process
    thread = threading.Thread(target=lp.start)
    thread.start()

    return jsonify({"msg": "Process started"})

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
