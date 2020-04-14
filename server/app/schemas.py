from marshmallow import Schema, fields

# Schema
class TeamParameter(Schema):
    team_id = fields.Int()

class SessionParameter(Schema):
    session_id = fields.Int()

class TokenParameter(Schema):
    token = fields.Str(required=True)

class TeamSchema(Schema):
    description = fields.Str()
    flag = fields.Str()
    id = fields.Int(dump_only=True)
    name = fields.Str()

class SessionSchema(Schema):
    id = fields.Int(dump_only=True)
    team_id = fields.Int(dump_only=True)
    team = fields.Nested(TeamSchema, only=("id", "name")) 
    status = fields.Str()
    level = fields.Int()
    port = fields.Int()
    container_id = fields.Str()
    trials = fields.Int()
    successes = fields.Int()
    hints = fields.Str()
    running = fields.Boolean()
    error = fields.Boolean()
    secret = fields.Str()
    ans = fields.Str()
    flag_url = fields.Str()
    flag_status = fields.Boolean()

class SessionPublicSchema(Schema):
    id = fields.Int(dump_only=True)
    team_id = fields.Int(dump_only=True)
    team = fields.Nested(TeamSchema, only=("id", "name")) 
    status = fields.Str()
    level = fields.Int()
    port = fields.Int()
    container_id = fields.Str()
    trials = fields.Int()
    successes = fields.Int()
    hints = fields.Str()
    running = fields.Boolean()
    error = fields.Boolean()
    flag_url = fields.Str()
    flag_status = fields.Boolean()