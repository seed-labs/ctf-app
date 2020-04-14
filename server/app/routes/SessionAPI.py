from flask import current_app, Blueprint, jsonify, request
import os
import docker
from sqlalchemy import exc

session_api = Blueprint('session_api', __name__)
docker_client = docker.from_env()   # fetch the docker info

db = None
models = None
admin_token = None
session_public_schema = None
session_schema = None

@session_api.record
def record(state):
    global db
    global models
    global session_schema
    global session_public_schema
    global admin_token

    db = state.app.config.get("session_api.db")
    models = state.app.config.get("session_api.models")
    session_schema  = state.app.config.get("session_api.session_schema")
    session_public_schema  = state.app.config.get("session_api.session_public_schema")
    admin_token = os.environ["ADMIN_TOKEN"]     # fetch the admin token

    if db is None:
        raise Exception("This blueprint expects you to provide "
                        "database access through session_api.db")

    if models is None:
        raise Exception("This blueprint expects you to provide "
                        "database models access through session_api.models")

    if session_schema is None:
        raise Exception("This blueprint expects you to provide "
                        "teams schema access through session_api.session_schema")

    if session_public_schema is None:
        raise Exception("This blueprint expects you to provide "
                        "teams schema access through session_api.session_public_schema")

    if admin_token is None:
        raise Exception("This blueprint expects you to provide "
                        "admin token access through env variable")

@session_api.route('/api/team/session/<session_id>', methods=['GET'])
def teamSessionFetch(session_id):
    """Fetch the session details
    ---
    get:
        parameters:
            - in: path
              schema: 'SessionParameter'
        description: Fetch the session
        responses:
            200:
                description: successful
                content:
                    application/json:
                        schema: 'SessionPublicSchema'
            400:
                description: Invalid session
    """
    team_session = models.Session.query.get(session_id)     # fetch the session from db
    if team_session is not None and team_session.team is not None and team_session.team.name is not None:
        return jsonify(session_public_schema.dump(team_session))
    else:
        return jsonify({"error": "Invalid session"}), 400

@session_api.route('/api/team/session/<session_id>', methods=['DELETE'])
def teamSessionDelete(session_id):
    """Delete the session
    ---
    delete:
        parameters:
            - in: header
              schema: 'TokenParameter'
            - in: path
              schema: 'SessionParameter'
        description: Delete the session
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

    if request.method == 'DELETE':
        team_session = models.Session.query.get(session_id)

        if team_session is None:
            return jsonify({'error': 'Invalid session'}), 400

        try:
            # stop the docker container
            ct = docker_client.containers.get(team_session.container_id)
            ct.stop()
        except docker.errors.APIError:
            print("Error - Container not found")

        if team_session.running == True:
            team_session.running = False
            team_session.container_id = "null"
            db.session.add(team_session)
            db.session.commit()
        return jsonify(session_schema.dump(team_session))

@session_api.route('/api/team/session/<session_id>/flag', methods=['DELETE'])
def teamSessionClearFlag(session_id):
    """Clear the session flag details
    ---
    delete:
        parameters:
            - in: path
              schema: 'SessionParameter'
        description: Clear the session flag
        responses:
            200:
                description: successful
                content:
                    application/json:
                        schema: 'SessionPublicSchema'
            400:
                description: Invalid session
    """
    if request.method == 'DELETE':
        team_session = models.Session.query.get(session_id)     # fetch the session from db

        if team_session is None:
            return jsonify({'error': 'Invalid session'}), 400

        team_session.flag_status = False                        # reset the flag status
        db.session.add(team_session)
        db.session.commit()
        return jsonify(session_public_schema.dump(team_session))

@session_api.route('/api/team/session/<session_id>/answer', methods=['GET'])
def getSessionAnswer(session_id):
    """Fetch the session answer
    ---
    get:
        parameters:
            - in: header
              schema: 'TokenParameter'
            - in: path
              schema: 'SessionParameter'
        description: Fetch the session answer
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
    team_session = models.Session.query.get(session_id)     # fetch the session from db
    
    if team_session is None:
        return jsonify({'error': 'Invalid session'}), 400

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

    return jsonify(session_schema.dump(team_session))