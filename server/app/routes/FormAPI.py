from flask import current_app, Blueprint, jsonify, request
import os
import docker
from sqlalchemy import exc

form_api = Blueprint('form_api', __name__)

db = None
models = None

@form_api.record
def record(state):
    global db
    global models

    db = state.app.config.get("form_api.db")
    models = state.app.config.get("form_api.models")

    if db is None:
        raise Exception("This blueprint expects you to provide "
                        "database access through form_api.db")

    if models is None:
        raise Exception("This blueprint expects you to provide "
                        "database models access through form_api.models")

@form_api.route('/api/bof_form/get_schema', methods=['GET'])
def getSchema():
    """Fetch the admin form for creating the BOF session
    ---
    get:
        description: Fetch the admin form for creating BOF session
        responses:
            200:
                description: successful
                content:
                    application/json:
                        schema: 'SessionSchema'
    """
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

@form_api.route('/api/team_form/get_schema', methods=['GET'])
def getTeamSchema():
    """Fetch the admin form for creating the team
    ---
    get:
        description: Fetch the admin form for creating the team
        responses:
            200:
                description: successful
                content:
                    application/json:
                        schema: 'SessionSchema'
    """
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