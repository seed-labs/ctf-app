from app import db
from sqlalchemy.orm import deferred

class Team(db.Model):
    """
    Create a Team table
    """

    __tablename__ = 'teams'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    description = db.Column(db.String(200))
    sessions = db.relationship("Session", back_populates="team")
    flag = deferred(db.Column(db.LargeBinary(length=1024 * 1024)))

    def __repr__(self):
        return '<Team: {}>'.format(self.name)

class Session(db.Model):
    """
    Create a Session table
    """

    __tablename__ = 'sessions'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    team = db.relationship("Team", back_populates="sessions")
    status = db.Column(db.String(100))
    level = db.Column(db.Integer)
    port = db.Column(db.Integer)
    container_id = db.Column(db.String(100), unique=True)
    trials = db.Column(db.Integer)
    successes = db.Column(db.Integer)
    hints = db.Column(db.String(100))
    running = db.Column(db.Boolean)
    error = db.Column(db.Boolean)
    secret = db.Column(db.String(100), unique=True)
    ans = db.Column(db.String(100), unique=True)
    flag_url = db.Column(db.String(100))
    flag_status = db.Column(db.Boolean)

    def __repr__(self):
        return '<Session: {}>'.format(self.level)

# def init_db():
#     db.create_all()
#     db.session.commit()


# if __name__ == '__main__':
#     print('initalizing the dataset')
#     init_db()