from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc
from flask_migrate import Migrate
from flask import request
from flask_socketio import SocketIO, emit

import os
import random
import string
import socket
import random
import time
import docker
import json
import yaml

import eventlet
from eventlet.semaphore import Semaphore

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin
from pprint import pprint
from marshmallow import Schema, fields

from .routes.TeamAPI import team_api, createTeam, getTeams, manageTeam, fetchTeamDetails
from .routes.SessionAPI import session_api, teamSessionFetch, teamSessionDelete, teamSessionClearFlag, getSessionAnswer
from .routes.FormAPI import form_api, getSchema, getTeamSchema

from .schemas import TeamParameter, SessionParameter, TokenParameter, TeamSchema, SessionSchema, SessionPublicSchema

OPENAPI_SPEC = """
openapi: 3.0.2
servers:
- url: http://localhost:{port}/
  description: The development API server
  variables:
    port:
      enum:
      - '5000'
      - '80'
      - '443'
      default: '5000'
"""

settings = yaml.safe_load(OPENAPI_SPEC)

# Create an APISpec
spec = APISpec(
    title="CTF System",
    version="1.0.0",
    openapi_version="3.0.2",
    info=dict(description="Capture the flag system"),
    plugins=[FlaskPlugin(), MarshmallowPlugin()],
    **settings
)

# validate_spec(spec)
api_key_scheme = {"type": "apiKey", "in": "header", "name": "token"}
spec.components.security_scheme("token", api_key_scheme)

# Initialize the schema objects
team_schema = TeamSchema()
teams_schema = TeamSchema(many=True)

session_schema = SessionSchema()
session_many_schema = SessionSchema(many=True)

session_public_schema = SessionPublicSchema()
session_many_public_schema = SessionPublicSchema(many=True)

# Add to the spec list
spec.components.schema("Team", schema=TeamSchema)
spec.components.schema("Session", schema=SessionSchema)
spec.components.schema("SessionPublic", schema=SessionPublicSchema)

admin_token = os.environ["ADMIN_TOKEN"]     # fetch the admin token
HOST_IP = os.environ["HOST_IP"]     # fetch the host ip
DATABASE_URL = os.environ["DATABASE_URL"]

db = SQLAlchemy()   # initialize the db client

docker_client = docker.from_env()   # fetch the docker info

dummy_sizes = [0, random.randint(0, 1000), random.randint(0, 1000), random.randint(0, 1000), random.randint(0, 1000)]

# store the stream object
StdOutLogIterator = {}
StdErrLogIterator = {}
SocketStatusIterator = {}

sem = Semaphore(1)                  # semaphore object for synchronizing the iterator objects

def create_app():
    '''Main wrapper for app creation'''
    app = Flask(__name__, static_folder='../../build')      # static folder where the frontend application is hosted from
    CORS(app)                                               # enable cross origin HTTP requests

    app.logger.info("admin_token: ", admin_token)
    app.logger.info("HOST_IP: ", HOST_IP)
    app.logger.info("DATABASE_URL: ", DATABASE_URL)

    # app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    socketio = SocketIO(app, cors_allowed_origins="*")      # enable cross origin websocket requests
    db.init_app(app)                                        # initialize the database

    from app import models                                  # load the database models

    with app.app_context():
        # db.drop_all()
        db.create_all()                                     # create all tables for the models

    app.config["team_api.db"] = db
    app.config["team_api.models"] = models
    app.config["team_api.teams_schema"] = teams_schema
    app.config["team_api.team_schema"] = team_schema

    app.config["session_api.db"] = db
    app.config["session_api.models"] = models
    app.config["session_api.session_schema"] = session_schema
    app.config["session_api.session_public_schema"] = session_public_schema

    app.config["form_api.db"] = db
    app.config["form_api.models"] = models
    
    ##
    # API routes
    ##
    app.register_blueprint(team_api)
    app.register_blueprint(session_api)
    app.register_blueprint(form_api)

    @app.route('/api/get_sessions_public', methods=['GET'])
    def getSessionsListPublic():
        """Fetch currently running sessions - public api
        ---
        get:
            description: Fetch all the sessions
            responses:
                200:
                    description: successful
                    content:
                        application/json:
                            schema: 'SessionSchema'
        """
        output = db.session.query(models.Session).join(models.Team).filter(models.Session.running == True)
        return jsonify({'sessions': session_many_public_schema.dump(output)})

    @app.route('/api/get_sessions', methods=['GET'])
    def getSessionsList():
        """Fetch currently running sessions - admin api
        ---
        get:
            parameters:
                - in: header
                  schema: 'TokenParameter'
            description: Fetch all the sessions
            responses:
                200:
                    description: successful
                    content:
                        application/json:
                            schema: 'SessionSchema'
                404:
                    description: Invalid token
            security:
                - api_key: []
        """
        if (not 'token' in request.args or request.args['token'] != admin_token):   # check for admin token
            return jsonify({"error": "Invalid token"}), 404

        output = db.session.query(models.Session).join(models.Team).filter(models.Session.running == True) # query all the sessions that are running
        sessions  = []
        for row in output:
            try:
                ct = docker_client.containers.get(row.container_id)                 # fetch the docker container status
                if ct.status == "running":
                    eventlet.greenthread.spawn(watchStdErrLogs, { 'container_id': row.id }, models)     # create a new greenlet thread to watch the control logs
                    eventlet.greenthread.spawn(watchLogs, { 'container_id': row.id }, models)    # create a new greenlet thread to watch the output logs
                    eventlet.greenthread.spawn(watchSocketStatus, { 'container_id': row.id }, models)    # create a new greenlet thread to watch the container running status
                else:                                                               # update the session with the container not running stats
                    row.error = True
                    row.status = "Docker container not running"
                    app.logger.info("Docker container not running: ", row.id)
                    db.session.add(row)
            except docker.errors.NotFound:                                          # capture the exception when the docker container is missing from the system
                row.error = True
                row.status = "Docker container not found"
                app.logger.info("Docker container not found: ", row.id)
                db.session.add(row)

            sessions.append(row)
        db.session.commit()
        return jsonify({'sessions': session_many_schema.dump(sessions)})

    @app.route('/api/team/<team_id>/session', methods=['POST'])
    def startTeamSession(team_id):
        """Create a new session for the team
        ---
        post:
            parameters:
                - in: header
                  schema: 'TokenParameter'
                - in: path
                  schema: 'TeamParameter'
            description: Create a session
            responses:
                200:
                    description: successful
                    content:
                        application/json:
                            schema: 'SessionSchema'
                404:
                    description: Invalid token
                400:
                    description: Invalid team id
                400:
                    description: Missing level or buffer size
                400:
                    description: Missing buffer_high or buffer_low
                400:
                    description: Missing buffer_high or buffer_low or address_mask
                500:
                    description: error starting bof server - code 1 - Build Image
                500:
                    description: error starting bof server - code 2 - API Error
                500:
                    description: error starting bof server - code 3 - Image Not Found
                500:
                    description: error starting bof server - code 4 - Container error
            security:
                - api_key: []
        """
        req = request.get_json()

        if (not 'token' in req or req['token'] != admin_token):   # check for admin token
            return jsonify({"error": "Invalid token"}), 404

        team_id = int(team_id)
        if team_id == 'undefined' or not isinstance(team_id, int):  # check the team id 
            return jsonify({"error": "Invalid team id"}), 400

        if (not 'level' in req or not 'buffer_size' in req):        # check if level and buffer_size is provided
            return jsonify({'error': 'Missing level or buffer size'}), 400
        
        # generate the command string based on the level of the session
        if req['level'] == 1 or req['level'] == 4:
            cmd = [
                '/bof_vulnerable_server',
                '-l', str(req['level']),
                '-p', '9090',
                '-b', '0.0.0.0'
            ]

        if req['level'] == 2:
            if (not 'buffer_high' in req or not 'buffer_low' in req):   #check if buffer_high and buffer_low is provided
                return jsonify({'error': 'Missing buffer_high or buffer_low'}), 400

            cmd = [
                '/bof_vulnerable_server',
                '-l', str(req['level']),
                '-p', '9090',
                '-b', '0.0.0.0',
                '-S', str(req['buffer_high']),
                '-s', str(req['buffer_low'])
            ]

        if req['level'] == 3:
            if (not 'buffer_high' in req or not 'buffer_low' in req or not 'address_mask' in req):   #check if buffer_high, buffer_low and address_mask is provided
                return jsonify({'error': 'Missing buffer_high or buffer_low or address_mask'}), 400

            cmd = [
                '/bof_vulnerable_server',
                '-l', str(req['level']),
                '-p', '9090',
                '-b', '0.0.0.0',
                '-S', str(req['buffer_high']),
                '-s', str(req['buffer_low']),
                '-m', req['address_mask']
            ]
        letters = string.ascii_lowercase
        bof_secret = ''.join(random.choice(letters) for i in range(10))     #generate a random secret string of 10 characters
        team = models.Team.query.get(team_id)

        if team.flag:
            team_session = models.Session(team_id=team_id, level=req['level'], port=-1, running=False, status="building", successes=0, trials=0, hints="", flag_url="", flag_status=False, secret=bof_secret)
        else:
            team_session = models.Session(team_id=team_id, level=req['level'], port=-1, running=False, status="building", successes=0, trials=0, hints="", flag_url="/team_test.jpg", flag_status=False, secret=bof_secret)

        db.session.add(team_session)
        db.session.commit()

        try:
            # build a new image from the dockerfile with the secret generated for this session
            docker_client.images.build(path="docker", tag="bof:" + str(team_session.id), buildargs={"bof_secret": bof_secret, "ddummy_size":str(dummy_sizes[req['level']]), "dbuf_size": str(req['buffer_size'])})
            team_session.status = "image built"        
            core_limit = docker.types.Ulimit(name='core', soft=0, hard=0)   # disable code dump in the container

            # run the docker image with the command generated based on the level chosen 
            ct = docker_client.containers.run(image="bof:" + str(team_session.id), command=cmd, ulimits=[core_limit], nano_cpus=100000000, restart_policy= {"Name": "always"}, detach=True, auto_remove=False, publish_all_ports=True)

            ct.reload()  # required to get auto-assigned ports, not needed if it was an already running container

            port_assigned = ct.ports['9090/tcp'][0]['HostPort']     # fetch the port number of the exposed port in the container
        except docker.errors.BuildError as err:     # build error during the image build process
            app.logger.info(err)
            app.logger.info("Error- Build Image")
            return jsonify({"error": "error starting bof server - code: 1"}), 500
        except docker.errors.APIError as err:       # unable to connect to docker api
            app.logger.info(err)
            app.logger.info("Error- API Error")
            return jsonify({"error": "error starting bof server - API Error - code: 2"}), 500
        except docker.errors.ImageNotFound as err:  # unable to find the BOF docker image
            app.logger.info(err)
            app.logger.info("Error- Image Not Found")
            return jsonify({"error": "error starting bof server - code: 3"}), 500
        except docker.errors.ContainerError as err:  # unable to start the container
            app.logger.info(err)
            app.logger.info("Error- Container error")
            return jsonify({"error": "error starting bof server - code: 4"}), 500
            
        team_session.running = True
        team_session.container_id = ct.id
        team_session.port = port_assigned
        db.session.add(team_session)
        db.session.commit()

        eventlet.greenthread.spawn(watchStdErrLogs, { 'container_id': team_session.id }, models)
        eventlet.greenthread.spawn(watchLogs, { 'container_id': team_session.id }, models)
        eventlet.greenthread.spawn(watchSocketStatus, { 'container_id': team_session.id }, models)
        
        return jsonify(session_schema.dump(team_session))

    @app.route('/api/team/session/<session_id>/docker', methods=['GET'])
    def teamSessionRestartDocker(session_id):
        """Restart the docker container for the current session
        ---
        get:
            parameters:
                - in: header
                  schema: 'TokenParameter'
                - in: path
                  schema: 'SessionParameter'
            description: Restart docker container for the current session
            responses:
                200:
                    description: successful
                    content:
                        application/json:
                            schema: 'SessionSchema'
                404:
                    description: Invalid token
                400:
                    description: Invalid session
            security:
                - api_key: []
        """
        if (not 'token' in request.args or request.args['token'] != admin_token):   # check for admin token
            return jsonify({"error": "Invalid token"}), 404

        if request.method == 'GET':
            team_session = models.Session.query.get(session_id)

            if team_session is None:
                return jsonify({'error': 'Invalid session'}), 400

            try:
                ct = docker_client.containers.get(team_session.container_id)
                ct.restart()                                                        # restart the docker container
            except docker.errors.APIError:
                app.logger.info("Error - Container not found")

            ct.reload()             # required to get auto-assigned ports, not needed if it was an already running container
            port_assigned = ct.ports['9090/tcp'][0]['HostPort']                     # fetch the newly assigned port number

            team_session.running = True
            team_session.error = False
            team_session.status = ""
            team_session.port = int(port_assigned)

            # restart the docker sesssion 
            sem.acquire()
            if team_session.id in StdErrLogIterator:
                del StdErrLogIterator[team_session.id] 

            if team_session.id in StdOutLogIterator:
                del StdOutLogIterator[team_session.id] 
            sem.release()

            eventlet.greenthread.spawn(watchStdErrLogs, { 'container_id': team_session.id }, models)
            eventlet.greenthread.spawn(watchLogs, { 'container_id': team_session.id }, models)

            db.session.add(team_session)
            db.session.commit()
            return jsonify(session_schema.dump(team_session))
    ##
    # View route
    ##
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def index(path):
        '''Return index.html for all non-api routes'''
        #pylint: disable=unused-argument
        if (path.find('.js') != -1) or (path.find('.css') != -1) or (path.find('.jpg') != -1) or (path.find('.png') != -1):
            return send_from_directory(app.static_folder, path)
        else:
            path = 'index.html'
            return send_from_directory(app.static_folder, path)

    def watchLogs(message, models):
        '''Eventlet function to watch the stdout logs from the container '''
        # app.logger.debug('message : {} - {}'.format(message, eventlet.corolocal.get_ident()))
        sem.acquire()   # acquire the lock on the semaphore
        if message is not None and message['container_id'] is not None and isinstance(message['container_id'], int) and message['container_id'] not in StdOutLogIterator:
            with app.app_context():
                ts = models.Session.query.get(message['container_id'])
                if ts is not None and ts.container_id != "null":
                    app.logger.debug('starting emit-listner: {}'.format(message['container_id']))
                    ct = docker_client.containers.get(ts.container_id)
                    StdOutLogIterator[message['container_id']] = ct.attach(stream=True, stdout=True, stderr=False)   # listen to the container log
                    sem.release()   # release the lock on the semaphore

                    eventName = 'emit_log_' + str(message['container_id'])
                    for line in StdOutLogIterator[message['container_id']]:         # iterate over the lines in the log
                        # app.logger.debug('emit_log_t_{} -'.format(message['container_id']))
                        if(line.decode('unicode_escape').find(ts.secret) != -1):    # check the secret value with the log
                            # app.logger.debug('found secret')
                            ts.successes = models.Session.successes + 1
                            ts.flag_status = True
                            db.session.add(ts)
                            db.session.commit()
                            eventName = 'emit_refresh_' + str(message['container_id'])
                            socketio.emit(eventName, {'refresh_data': True, 'timestamp': time.time()})  # send the success event information to the induvidual session
                            socketio.emit('emit_success', {'refresh_data': True, 'timestamp': time.time()})  # send the success event information to the monitor page
                        eventName = 'emit_log_' + str(message['container_id'])
                        socketio.emit(eventName, {'log': str(line.decode('unicode_escape')), 'timestamp': time.time()}) # send the log data to clients
                else:
                    sem.release()   # release the lock on the semaphore
        else:
            sem.release()   # release the lock on the semaphore

    def watchStdErrLogs(message, models):
        '''Eventlet function to watch the stderr logs from the container '''
        # app.logger.debug('message : {} - {}'.format(message, eventlet.corolocal.get_ident()))
        sem.acquire()   # acquire the lock on the semaphore
        if message is not None and message['container_id'] is not None and isinstance(message['container_id'], int) and message['container_id'] not in StdErrLogIterator:
            with app.app_context():
                ts = models.Session.query.get(message['container_id'])
                if ts is not None and ts.container_id != "null":
                    app.logger.debug('starting emit-listner-err-log: {}'.format(message['container_id']))
                    ct1 = docker_client.containers.get(ts.container_id)
                    StdErrLogIterator[message['container_id']] = ct1.attach(stream=True, stdout=False, stderr=True)   # listen to the container log
                    sem.release()   # release the lock on the semaphore

                    eventName = 'emit_log_' + str(message['container_id'])
                    for line in StdErrLogIterator[message['container_id']]:         # iterate over the lines in the log
                        # app.logger.debug('emit_log_err_{}: {}'.format(message['container_id'], line.decode('unicode_escape')))
                        for server_line in line.decode('unicode_escape').splitlines():     # parse the control log
                            session_id = message['container_id']
                            if '#' not in server_line: 
                                app.logger.debug('Session: {}: unexpected respond from CTF server: {}'.format(session_id, server_line))
                            [msg_type, msg] = server_line.split('#')                # fetch the type of message and message value

                            if msg_type == 'err':
                                app.logger.debug('Session {}: Server error: {}'.format(session_id, msg))
                                break

                            if msg_type == 'trial':
                                eventName = 'emit_trial_count_' + str(message['container_id'])
                                ts.trials = models.Session.trials + 1
                                db.session.add(ts)
                                db.session.commit()
                                socketio.emit(eventName, {'count': (ts.trials), 'timestamp': time.time()})  # send the count information
                                # app.logger.debug('Session {}: Trial received from {}'.format(session_id, msg))

                            if msg_type == 'hints':
                                # app.logger.debug('test hints: ', msg)
                                ts.hints = msg      # update the hints
                                db.session.add(ts)
                                db.session.commit()
                                eventName = 'emit_refresh_' + str(message['container_id'])
                                socketio.emit(eventName, {'refresh_data': True, 'timestamp': time.time()})
                                app.logger.info('Session {}: Hints updated'.format(session_id))

                            if msg_type == 'ans':
                                # app.logger.debug('test ans: ', msg)
                                ts.ans = msg        # update the answer
                                db.session.add(ts)
                                db.session.commit()
                                eventName = 'emit_refresh_' + str(message['container_id'])
                                socketio.emit(eventName, {'refresh_data': True, 'timestamp': time.time()})
                                app.logger.info('Session {}: Answer updated'.format(session_id))
                else:
                    sem.release()   # release the lock on the semaphore
        else:
            sem.release()   # release the lock on the semaphore

    def watchSocketStatus(message, models):
        # app.logger.debug('socket-status - message : {} - {}'.format(message, eventlet.corolocal.get_ident()))
        sem.acquire()   # acquire the lock on the semaphore
        if message is not None and message['container_id'] is not None and isinstance(message['container_id'], int) and message['container_id'] not in SocketStatusIterator:
            SocketStatusIterator[message['container_id']] = True
            sem.release()   # release the lock on the semaphore

            with app.app_context():
                while 1:
                    ts = models.Session.query.get(message['container_id'])
                    if ts is not None and ts.container_id != "null":
                        if ts.running == True:         # check if the session is running
                            app.logger.debug('socket-status - starting: {} - Port: {}'.format(message['container_id'], ts.port))
                            try:
                                container_instance = docker_client.containers.get(ts.container_id)                 # fetch the docker container status
                                port_assigned = container_instance.ports['9090/tcp'][0]['HostPort']                 # fetch port number

                                # check the port number with db port mapped
                                if int(port_assigned) != ts.port:
                                    app.logger.info('socket-status - port not matching: {} - Port: {}'.format(message['container_id'], ts.port))
                                    ts.port = int(port_assigned)
                                    db.session.add(ts)
                                    db.session.commit()
                            except docker.errors.NotFound:                                          # capture the exception when the docker container is missing from the system
                                break
                            
                            currentStatusFlag = False   # check the status of connection

                            # send socket data to the container
                            try:
                                clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                clientsocket.connect((HOST_IP, ts.port))
                                clientsocket.send(b'ping\n')
                            except socket.error as e:
                                currentStatusFlag = True    # connection failed
                                if(e.errno == 60):
                                    app.logger.info("Error socket timeout: ", e)
                                else:
                                    app.logger.info("Issue: ", e)
                            
                            # change in status
                            if currentStatusFlag == True and ts.error == False:
                                ts.error = True
                                ts.status = "Docker container not responding"
                                db.session.add(ts)
                                db.session.commit()
                            elif currentStatusFlag == False and ts.error == True:
                                ts.error = False
                                ts.status = ""
                                db.session.add(ts)
                                db.session.commit()
                            app.logger.debug('socket-status - completed loop: {} - Port: {}'.format(message['container_id'], ts.port))
                        else:
                            app.logger.info('socket-status - skipping: {} - Port: {}'.format(message['container_id'], ts.port))
                    else:
                        app.logger.info('socket-status - stopping: {} - Port: {}'.format(message['container_id'], ts.port))
                        break
                    eventlet.sleep(seconds=60)
        else:
            sem.release()   # release the lock on the semaphore

    @socketio.on('connect')
    def test_connect():
        emit('status', {'data': 'Connected'})

    @socketio.on('disconnect')
    def test_disconnect():
        app.logger.info('Client disconnected')

    with app.test_request_context():
        spec.path(view=createTeam)
        spec.path(view=getTeams)
        spec.path(view=manageTeam)
        spec.path(view=fetchTeamDetails)
        spec.path(view=getSessionsListPublic)
        spec.path(view=getSessionsList)
        spec.path(view=getSchema)
        spec.path(view=getTeamSchema)
        spec.path(view=startTeamSession)
        spec.path(view=teamSessionDelete)
        spec.path(view=teamSessionRestartDocker)
        spec.path(view=teamSessionClearFlag)
        spec.path(view=teamSessionFetch)
        spec.path(view=getSessionAnswer)

    with open('swagger.json', 'w') as f:
        json.dump(spec.to_dict(), f)


    return (app, socketio)