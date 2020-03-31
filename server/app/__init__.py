from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc
from flask_migrate import Migrate
from flask import request
from flask_socketio import SocketIO, emit
import docker
import random
import time
import eventlet
from eventlet.semaphore import Semaphore
import os
import random
import string
import socket

admin_token = os.environ["ADMIN_TOKEN"]     # fetch the admin token
print("Debug: admin_token: ", admin_token)

HOST_IP = os.environ["HOST_IP"]     # fetch the host ip
print("Debug: HOST_IP: ", HOST_IP)

DATABASE_URL = os.environ["DATABASE_URL"]
print("Debug: DATABASE_URL: ", DATABASE_URL)

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

    # app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    socketio = SocketIO(app, cors_allowed_origins="*")      # enable cross origin websocket requests
    db.init_app(app)                                        # initialize the database

    from app import models                                  # load the database models

    with app.app_context():
        # db.drop_all()
        db.create_all()                                     # create all tables for the models
    ##
    # API routes
    ##
    @app.route('/api/team', methods=['GET', 'POST'])
    def createTeam():
        '''Create a new team'''
        if request.method == 'POST':
            req = request.get_json()
            if (not 'token' in req or req['token'] != admin_token):     # check for admin token
                return jsonify({"error": "Invalid token"}), 400

            if (not 'name' in req or req['name'] == None):     # check for admin token
                return jsonify({"error": "Invalid name"}), 400

            if (not 'description' in req or req['description'] == None):     # check for admin token
                return jsonify({"error": "Invalid description"}), 400

            if (not 'file' in req or req['file'] == ''):                # check if the file is attached to request
                team = models.Team(name=req['name'], description=req['description'])
            else:
                team = models.Team(name=req['name'], description=req['description'], flag=req['file'].encode())

            try:
                db.session.add(team)                                        # create a new team
                db.session.commit()
            except exc.IntegrityError as e:
                print(e)
                return jsonify({"error": "Team name already used"}), 500
            except exc.SQLAlchemyError as e:
                print(e)
                if e.args[0].find('Data too long for column \'flag\' ') != -1:
                    return jsonify({"error": "Flag file is bigger than 10MB"}), 500    
                return jsonify({"error": "SQL error"}), 500

            return jsonify({'id': team.id, 'name': team.name, 'description': team.description})
        else:
            if (not 'token' in request.args or request.args['token'] != admin_token):     # check for admin token
                return jsonify({"error": "Invalid token"}), 400

            output = db.session.query(models.Team)                      # fetch all the teams from db
            teamsOutput = []
            for t in output:
                if t.flag:
                    teamsOutput.append({
                        'id': t.id,
                        'name': t.name,
                        'description': t.description,
                        'flag': t.flag.decode(),
                    })
                else:
                    teamsOutput.append({
                        'id': t.id,
                        'name': t.name,
                        'description': t.description,
                        'flag': '',
                    })
            return jsonify({'teams': teamsOutput})

    @app.route('/api/team/<team_id>', methods=['PUT', 'DELETE'])
    def team(team_id):
        '''Manage team details'''
        team_id = int(team_id)
        if not isinstance(team_id, int):                        # check if team id is found and is int
            return jsonify({"error": "Invalid team id"}), 400
        
        if (not 'token' in request.args or request.args['token'] != admin_token):   # check for admin token
            return jsonify({"error": "Invalid token"}), 400

        if request.method == 'PUT':                             # TODO - Add update team mode in future
            return jsonify({'team_id': team_id})
        elif request.method == 'DELETE':                        # Remove a team
            team = models.Team.query.get(team_id)
            team_sessions = models.Session.query.filter_by(team_id=team_id)  # Query all the session for this team
            for session in team_sessions:
                if session.container_id:
                    try:
                        ct = docker_client.containers.get(session.container_id)  # stop the docker container for the sessions found
                        ct.stop()
                    except docker.errors.APIError:
                        print("Error - Container not found")

                if session.running == True:                             # update status to not running
                    session.running = False
                    db.session.add(session)

            db.session.delete(team)
            db.session.commit()
            return jsonify({'id': team.id, 'name': team.name, 'description': team.description})

    @app.route('/api/team/<team_id>', methods=['GET'])
    def fetchTeamDetails(team_id):
        '''fetch team details'''
        team_id = int(team_id)
        if not isinstance(team_id, int):                        # check if team id is found and is int
            return jsonify({"error": "Invalid team id"}), 400

        team = models.Team.query.get(team_id)
        if team.flag:
            return jsonify({
                'id': team.id,
                'name': team.name,
                'description': team.description,
                'flag': team.flag.decode(),
            })
        else:
            return jsonify({
                'id': team.id,
                'name': team.name,
                'description': team.description,
                'flag': '',
            })
            
    @app.route('/api/get_sessions_public', methods=['GET'])
    def getSessionsListPublic():
        '''Fetch currently running sessions - public api'''
        output = db.session.query(models.Session).join(models.Team).filter(models.Session.running == True)
        sessions  = []
        for row in output:
            sessions.append({
                'id': row.id,
                'team_id': row.team_id,
                'status': row.status,
                'level': row.level,
                'port': row.port,
                'trials': row.trials,
                'successes': row.successes,
                'hints': row.hints,
                'running': row.running,
                'name': row.team.name,
                'description': row.team.description,
                'flag_url': row.flag_url,
                'flag_status': row.flag_status,
                'dropped': False
            })
        return jsonify({'sessions': sessions})

    @app.route('/api/get_sessions', methods=['GET'])
    def getSessionsList():
        '''Fetch currently running sessions - admin api'''
        if (not 'token' in request.args or request.args['token'] != admin_token):   # check for admin token
            return jsonify({"error": "Invalid token"}), 400

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
                    print("Docker container not running: ", row.id)
                    db.session.add(row)
            except docker.errors.NotFound:                                          # capture the exception when the docker container is missing from the system
                row.error = True
                row.status = "Docker container not found"
                print("Docker container not found: ", row.id)
                db.session.add(row)

            sessions.append({
                'id': row.id,
                'team_id': row.team_id,
                'status': row.status,
                'level': row.level,
                'port': row.port,
                'container_id': row.container_id,
                'trials': row.trials,
                'successes': row.successes,
                'hints': row.hints,
                'running': row.running,
                'error': row.error,
                'name': row.team.name,
                'description': row.team.description,
                'flag_url': row.flag_url,
                'flag_status': row.flag_status, 
                'dropped': False
            })
        db.session.commit()
        return jsonify({'sessions': sessions})

    @app.route('/api/bof_form/get_schema', methods=['GET'])
    def getSchema():
        '''Fetch the admin form for creating the BOF session'''
        formFields = {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "$id": "http://json-schema.org/draft-04/schema#",
            "title": "Buffer Overflow Session Configuration",
            "type": "object",
            "properties": {
                "level": {
                "type": "integer",
                "enum": [
                    1,
                    2,
                    3,
                    4
                ],
                "description": "Difficulty level for the session.",
                "default": 1
                },
                "team": {
                    "type": "integer",
                    "enum": [],
                    "description": "Select a Team"
                },
                "buffer_size": {
                "type": "integer",
                "description": "The size of buffer."
                },
            },
            "required": [
                "level",
                "host",
                "buffer_size",
                "team"
            ],
            "dependencies": {
                "level": {
                "oneOf": [
                    {
                    "properties": {
                        "level": {
                        "enum": [
                            1,
                            4
                        ]
                        }
                    }
                    },
                    {
                    "properties": {
                        "level": {
                        "enum": [
                            2
                        ]
                        },
                        "buffer_high": {
                        "type": "integer",
                        "description": "The value to be added to the buffer size: the upper bound of the range."
                        },
                        "buffer_low": {
                        "type": "integer",
                        "description": "The value to be deducted from the buffer size: the lower bound of the range"
                        }
                    },
                    "required": [
                        "buffer_high",
                        "buffer_low"
                    ]
                    },
                    {
                    "properties": {
                        "level": {
                        "enum": [
                            3
                        ]
                        },
                        "buffer_high": {
                        "type": "integer",
                        "description": "The value to be added to the buffer size: the upper bound of the range."
                        },
                        "buffer_low": {
                        "type": "integer",
                        "description": "The value to be deducted from the buffer size: the lower bound of the range"
                        },
                        "address_mask": {
                        "type": "string",
                        "description": "The address mask."
                        }
                    },
                    "required": [
                        "buffer_high",
                        "buffer_low",
                        "address_mask"
                    ]
                    }
                ]
                }
            }
            }

        # add the list of teams to the form as dropdown
        teams = db.session.query(models.Team)
        for team in teams:
            formFields['properties']['team']['enum'].append(team.name)

        return jsonify(formFields)

    @app.route('/api/team_form/get_schema', methods=['GET'])
    def getTeamSchema():
        '''Fetch the admin form for creating the team'''
        return jsonify({
            "$schema": "http://json-schema.org/draft-04/schema#",
            "$id": "http://json-schema.org/draft-04/schema#",
            "title": "Team Settings",
            "type": "object",
            "properties": {
                "name": {
                "type": "string",
                "description": "The name of the team"
                },
                "description": {
                "type": "string",
                "description": "Team description"
                },
                "file": {
                "type": "string",
                "format": "data-url",
                "title": "flag"
                },
            },
            "required": [
                "name",
                "description",
            ],
            })

    @app.route('/api/team/<team_id>/session', methods=['POST'])
    def startTeamSession(team_id):
        '''Create a new session for the team'''
        req = request.get_json()

        if (not 'token' in req or req['token'] != admin_token):   # check for admin token
            return jsonify({"error": "Invalid token"}), 400

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
            print(err)
            print("Error- Build Image")
            return jsonify({"error": "error starting bof server - code: 1"}), 500
        except docker.errors.APIError as err:       # unable to connect to docker api
            print(err)
            print("Error- API Error")
            return jsonify({"error": "error starting bof server - API Error - code: 2"}), 500
        except docker.errors.ImageNotFound as err:  # unable to find the BOF docker image
            print(err)
            print("Error- Image Not Found")
            return jsonify({"error": "error starting bof server - code: 3"}), 500
        except docker.errors.ContainerError as err:  # unable to start the container
            print(err)
            print("Error- Container error")
            return jsonify({"error": "error starting bof server - code: 4"}), 500
            
        team_session.running = True
        team_session.container_id = ct.id
        team_session.port = port_assigned
        db.session.add(team_session)
        db.session.commit()

        eventlet.greenthread.spawn(watchStdErrLogs, { 'container_id': team_session.id }, models)
        eventlet.greenthread.spawn(watchLogs, { 'container_id': team_session.id }, models)
        eventlet.greenthread.spawn(watchSocketStatus, { 'container_id': team_session.id }, models)
        
        response = jsonify({'team_id': team_session.team_id, 'flag_url': team_session.flag_url, 'flag_status': team_session.flag_status, 'level': team_session.level, "port": team_session.port, "id": team_session.id, "container_id": team_session.container_id})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response
    
    @app.route('/api/team/session/<session_id>', methods=['DELETE'])
    def teamSessionDelete(session_id):
        '''Delete the session'''
        if (not 'token' in request.args or request.args['token'] != admin_token):   # check for admin token
            return jsonify({"error": "Invalid token"}), 400

        if request.method == 'DELETE':
            team_session = models.Session.query.get(session_id)
            team = models.Team.query.get(team_session.team_id)

            try:
                # stop the docker container
                ct = docker_client.containers.get(team_session.container_id)
                ct.stop()
            except docker.errors.APIError:
                print("Error - Container not found")

            if team_session.running == True:
                team_session.running = False
                db.session.add(team_session)
                db.session.commit()
            return jsonify({'team_id': team_session.team_id, 'level': team_session.level, "port": team_session.port, "id": team_session.id, "container_id": team_session.container_id, "running": team_session.running})

    @app.route('/api/team/session/<session_id>/docker', methods=['GET'])
    def restartDocker(session_id):
        '''Restart the docker container for the current session'''
        if (not 'token' in request.args or request.args['token'] != admin_token):   # check for admin token
            return jsonify({"error": "Invalid token"}), 400

        if request.method == 'GET':
            team_session = models.Session.query.get(session_id)
            team = models.Team.query.get(team_session.team_id)

            try:
                ct = docker_client.containers.get(team_session.container_id)
                ct.restart()                                                        # restart the docker container
            except docker.errors.APIError:
                print("Error - Container not found")

            ct.reload()             # required to get auto-assigned ports, not needed if it was an already running container
            port_assigned = ct.ports['9090/tcp'][0]['HostPort']                     # fetch the newly assigned port number

            team_session.running = True
            team_session.error = False
            team_session.status = ""
            team_session.port = port_assigned
            db.session.add(team_session)
            db.session.commit()
            return jsonify({'team_id': team_session.team_id, 'level': team_session.level, "port": team_session.port, "id": team_session.id, "container_id": team_session.container_id, "running": team_session.running})

    @app.route('/api/team/session/<session_id>/flag', methods=['DELETE'])
    def teamSessionClearFlag(session_id):
        '''Clear the session flag details'''
        if request.method == 'DELETE':
            team_session = models.Session.query.get(session_id)     # fetch the session from db
            team_session.flag_status = False                        # reset the flag status
            db.session.add(team_session)
            db.session.commit()
            return jsonify({'team_id': team_session.team_id, 'level': team_session.level, "port": team_session.port, "id": team_session.id, "container_id": team_session.container_id, "running": team_session.running})
            
    @app.route('/api/team/session/<session_id>', methods=['GET'])
    def teamSessionFetch(session_id):
        '''Fetch the session details'''
        team_session = models.Session.query.get(session_id)     # fetch the session from db
        team = models.Team.query.get(team_session.team_id)      # fetch the team details from db
        if team is not None and team.name is not None:
            return jsonify({'team_id': team_session.team_id, 'name': team.name, 'description': team.description, 'flag_url': team_session.flag_url, 'flag_status': team_session.flag_status, 'level': team_session.level, "port": team_session.port, "id": team_session.id, "container_id": team_session.container_id, "running": team_session.running, "trials": team_session.trials, "successes": team_session.successes, "hints": team_session.hints })
        else:
            return jsonify({"error": "Invalid session id"}), 400

    @app.route('/api/team/session/<session_id>/answer', methods=['GET'])
    def getSessionAnswer(session_id):
        '''Fetch the session answer'''
        if (not 'token' in request.args or request.args['token'] != admin_token):   # check for admin token
            return jsonify({"error": "Invalid token"}), 400

        team_session = models.Session.query.get(session_id)     # fetch the session from db
        team = models.Team.query.get(team_session.team_id)      # fetch the team details from db
        if team_session.ans is None and team_session.trials > 0:    # fetch the answer value
            print('ans is null')
            try:
                ct = docker_client.containers.get(team_session.container_id)
                log_data = ct.logs(stdout=False, stderr=True)       # fetch the docker container log
                for server_line in log_data.decode('unicode_escape').splitlines():      # parse the control log
                    if '#' not in server_line: 
                        print('Session: {}: unexpected respond from CTF server: {}'.format(session_id, server_line))
                    [msg_type, msg] = server_line.split('#')                            # fetch the type of message and message value

                    if msg_type == 'err':
                        print('Session {}: Server error: {}'.format(session_id, msg))
                        break

                    if msg_type == 'hints':
                        team_session.hints = msg
                        print('Session {}: Hints updated'.format(session_id))

                    if msg_type == 'ans':
                        team_session.ans = msg
                        print('Session {}: Answer updated'.format(session_id))
                db.session.add(team_session)
                db.session.commit()
            except docker.errors.APIError:
                print("Error - docker api not working")

        return jsonify({'ans': team_session.ans, 'team_id': team_session.team_id, 'name': team.name, 'description': team.description, 'level': team_session.level, "port": team_session.port, "id": team_session.id, "container_id": team_session.container_id, "running": team_session.running, "trials": team_session.trials, "successes": team_session.successes, "hints": team_session.hints })

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
        # print('message : {} - {}'.format(message, eventlet.corolocal.get_ident()))
        sem.acquire()   # acquire the lock on the semaphore
        if message is not None and message['container_id'] is not None and isinstance(message['container_id'], int) and message['container_id'] not in StdOutLogIterator:
            with app.app_context():
                ts = models.Session.query.get(message['container_id'])
                if ts is not None and ts.container_id != "null":
                    # print('starting emit-listner: {}'.format(message['container_id']))
                    ct = docker_client.containers.get(ts.container_id)
                    StdOutLogIterator[message['container_id']] = ct.attach(stream=True, stdout=True, stderr=False)   # listen to the container log
                    sem.release()   # release the lock on the semaphore

                    eventName = 'emit_log_' + str(message['container_id'])
                    for line in StdOutLogIterator[message['container_id']]:         # iterate over the lines in the log
                        # print('emit_log_t_{} -'.format(message['container_id']))
                        if(line.decode('unicode_escape').find(ts.secret) != -1):    # check the secret value with the log
                            # print('found secret')
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
        # print('message : {} - {}'.format(message, eventlet.corolocal.get_ident()))
        sem.acquire()   # acquire the lock on the semaphore
        if message is not None and message['container_id'] is not None and isinstance(message['container_id'], int) and message['container_id'] not in StdErrLogIterator:
            with app.app_context():
                ts = models.Session.query.get(message['container_id'])
                if ts is not None and ts.container_id != "null":
                    # print('starting emit-listner-err-log: {}'.format(message['container_id']))
                    ct1 = docker_client.containers.get(ts.container_id)
                    StdErrLogIterator[message['container_id']] = ct1.attach(stream=True, stdout=False, stderr=True)   # listen to the container log
                    sem.release()   # release the lock on the semaphore

                    eventName = 'emit_log_' + str(message['container_id'])
                    for line in StdErrLogIterator[message['container_id']]:         # iterate over the lines in the log
                        # print('emit_log_err_{}: {}'.format(message['container_id'], line.decode('unicode_escape')))
                        for server_line in line.decode('unicode_escape').splitlines():     # parse the control log
                            session_id = message['container_id']
                            if '#' not in server_line: 
                                print('Session: {}: unexpected respond from CTF server: {}'.format(session_id, server_line))
                            [msg_type, msg] = server_line.split('#')                # fetch the type of message and message value

                            if msg_type == 'err':
                                print('Session {}: Server error: {}'.format(session_id, msg))
                                break

                            if msg_type == 'trial':
                                eventName = 'emit_trial_count_' + str(message['container_id'])
                                ts.trials = models.Session.trials + 1
                                db.session.add(ts)
                                db.session.commit()
                                socketio.emit(eventName, {'count': (ts.trials), 'timestamp': time.time()})  # send the count information
                                # print('Session {}: Trial received from {}'.format(session_id, msg))

                            if msg_type == 'hints':
                                # print('test hints: ', msg)
                                ts.hints = msg      # update the hints
                                db.session.add(ts)
                                db.session.commit()
                                eventName = 'emit_refresh_' + str(message['container_id'])
                                socketio.emit(eventName, {'refresh_data': True, 'timestamp': time.time()})
                                print('Session {}: Hints updated'.format(session_id))

                            if msg_type == 'ans':
                                # print('test ans: ', msg)
                                ts.ans = msg        # update the answer
                                db.session.add(ts)
                                db.session.commit()
                                eventName = 'emit_refresh_' + str(message['container_id'])
                                socketio.emit(eventName, {'refresh_data': True, 'timestamp': time.time()})
                                print('Session {}: Answer updated'.format(session_id))
                else:
                    sem.release()   # release the lock on the semaphore
        else:
            sem.release()   # release the lock on the semaphore

    def watchSocketStatus(message, models):
        # print('socket-status - message : {} - {}'.format(message, eventlet.corolocal.get_ident()))
        sem.acquire()   # acquire the lock on the semaphore
        if message is not None and message['container_id'] is not None and isinstance(message['container_id'], int) and message['container_id'] not in SocketStatusIterator:
            SocketStatusIterator[message['container_id']] = True
            sem.release()   # release the lock on the semaphore

            with app.app_context():
                while 1:
                    ts = models.Session.query.get(message['container_id'])
                    if ts is not None and ts.container_id != "null" and ts.running == True:         # check if the session is running
                        # print('socket-status - starting: {} - Port: {}'.format(message['container_id'], ts.port))
                        container_instance = docker_client.containers.get(ts.container_id)

                        # send socket data to the container
                        try:
                            clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            clientsocket.connect((HOST_IP, ts.port))
                            clientsocket.send(b'test\n')
                        except socket.error as e:
                            ts.error = True
                            ts.status = "Docker container not responding"
                            db.session.add(ts)
                            db.session.commit()
                            if(e.errno == 60):
                                print("Error socket timeout: ", e)
                            else:
                                print("Issue: ", e)
                    else:
                        print('socket-status - skipping: {} - Port: {}'.format(message['container_id'], ts.port))
                    eventlet.sleep(seconds=60)
        else:
            sem.release()   # release the lock on the semaphore

    @socketio.on('connect')
    def test_connect():
        emit('status', {'data': 'Connected'})

    @socketio.on('disconnect')
    def test_disconnect():
        print('Client disconnected')


    return (app, socketio)