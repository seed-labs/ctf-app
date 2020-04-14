from flask import current_app, Blueprint, jsonify, request
import os
import docker
from sqlalchemy import exc

team_api = Blueprint('team_api', __name__)
docker_client = docker.from_env()   # fetch the docker info

db = None
models = None
teams_schema = None
admin_token = None
team_schema = None

@team_api.record
def record(state):
    global db
    global models
    global team_schema
    global teams_schema
    global admin_token

    db = state.app.config.get("team_api.db")
    models = state.app.config.get("team_api.models")
    teams_schema  = state.app.config.get("team_api.teams_schema")
    team_schema  = state.app.config.get("team_api.team_schema")
    admin_token = os.environ["ADMIN_TOKEN"]     # fetch the admin token

    if db is None:
        raise Exception("This blueprint expects you to provide "
                        "database access through team_api.db")

    if models is None:
        raise Exception("This blueprint expects you to provide "
                        "database models access through team_api.models")

    if teams_schema is None:
        raise Exception("This blueprint expects you to provide "
                        "teams schema access through team_api.teams_schema")

    if admin_token is None:
        raise Exception("This blueprint expects you to provide "
                        "admin token access through env variable")

@team_api.route('/api/team', methods=['POST'])
def createTeam():
    """Team API
    ---
    post:
        description: Create a new Team
        parameters:
            - in: header
              schema: 'TokenParameter'
        responses:
            200:
                description: successful
                content:
                    application/json:
                        schema: 'TeamSchema'
            404:
                description: Invalid token
            400:
                description: Invalid name
            400:
                description: Invalid description
            500:
                description: Team name already used
            500:
                description: SQL error
        security:
            - api_key: []
    """
    req = request.get_json()
    if (not 'token' in req or req['token'] != admin_token):     # check for admin token
        return jsonify({"error": "Invalid token"}), 404

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

    return jsonify(team_schema.dump(team))

@team_api.route('/api/team', methods=['GET'])
def getTeams():
    """Team API
    ---
    get:
        description: Fetch all the teams
        responses:
            200:
                description: successful
                content:
                    application/json:
                        schema: 'TeamSchema'
            404:
                description: Invalid token
        security:
            - api_key: []
    """
    if (not 'token' in request.args or request.args['token'] != admin_token):     # check for admin token
        return jsonify({"error": "Invalid token"}), 404

    teams_output = db.session.query(models.Team)                      # fetch all the teams from db
    return jsonify({'teams': teams_schema.dump(teams_output)})

@team_api.route('/api/team/<team_id>', methods=['PUT', 'DELETE'])
def manageTeam(team_id):
    """Manage team details
    ---
    delete:
        parameters:
            - in: path
              schema: 'TeamParameter'
            - in: header
              schema: 'TokenParameter'
        description: Delete the team
        responses:
            200:
                description: successful
                content:
                    application/json:
                        schema: 'TeamSchema'
            404:
                description: Invalid token
            400:
                description: Invalid team id
            400:
                description: Invalid team
        security:
            - api_key: []
    """
    team_id = int(team_id)
    if not isinstance(team_id, int):                        # check if team id is found and is int
        return jsonify({"error": "Invalid team id"}), 400
    
    if (not 'token' in request.args or request.args['token'] != admin_token):   # check for admin token
        return jsonify({"error": "Invalid token"}), 404

    if request.method == 'PUT':                             # TODO - Add update team mode in future
        return jsonify({'team_id': team_id})
    elif request.method == 'DELETE':                        # Remove a team
        team = models.Team.query.get(team_id)

        if team is None:
            return jsonify({'error': 'Invalid team'}), 400

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
                session.container_id = "null"
                db.session.add(session)

        db.session.delete(team)
        db.session.commit()
        return jsonify({'id': team.id, 'name': team.name, 'description': team.description})

@team_api.route('/api/team/<team_id>', methods=['GET'])
def fetchTeamDetails(team_id):
    """fetch team details
    ---
    get:
        parameters:
            - in: path
              schema: 'TeamParameter'
        description: Fetch the team information
        responses:
            200:
                description: successful
                content:
                    application/json:
                        schema: 'TeamSchema'
            400:
                description: Invalid team id
            400:
                description: Invalid team
    """
    team_id = int(team_id)
    if not isinstance(team_id, int):                        # check if team id is found and is int
        return jsonify({"error": "Invalid team id"}), 400

    team = models.Team.query.get(team_id)

    if team is None:
        return jsonify({'error': 'Invalid team'}), 400

    return jsonify(team_schema.dump(team))