import os
import eventlet
eventlet.monkey_patch()     # initialize the greenlet threads

from app import create_app

(app, socketio) = create_app()  # fetch the flask app object and socket.io object

# APP_DEBUG = os.environ["APP_DEBUG"]
# print("APP_DEBUG: ", APP_DEBUG)

if __name__ == '__main__':
    socketio.run(app, debug=True, host="0.0.0.0")
