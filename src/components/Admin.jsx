import React from 'react';
import { Link } from 'react-router-dom';
import Form from 'react-jsonschema-form';

class Admin extends React.Component {
  constructor(props) {
    super(props);
    this.token = 'changeme';
    this.form_data = {};

    this.state = {
      sessions: [],
      busy: 0,
      schema: {},
      schema_team: {},
      sessions: [],
      teams: [],
    };
  }

  /*
    API request - query the backend service
  */
  api_req(method, url, payload, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, `${process.env.API_URL}${url}`);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onreadystatechange = () => {
        if (xhr.readyState != 4) return;

        var res_content_type = xhr.getResponseHeader('Content-Type');
        if (res_content_type.toLowerCase() != 'application/json') {
            callback([{ok: false}, xhr.status]);
            console.log(`Bad Content-Type: ${res_content_type}`);
            return;
        }

        var obj = JSON.parse(xhr.responseText);
        callback([obj, xhr.status]);
    };
    xhr.send(payload);
  }

  /*
    Get the list of sessions that are currently running
  */
  fetchSessions() {
    this.api_req('GET', `/api/get_sessions?token=${this.token}`, undefined, (rslt) => {
      var [res, status] = rslt;
      if (status != 200) {
          alert(`Failed to get schema: ${res.error}`);
          console.log(`API not-OK when get_schema: ${res.error}`)
          return;
      }

      this.setState({sessions: res.sessions});
    });
  }

  /*
    Initialize the forms 
  */
  componentDidMount() {
    console.log('Loading CTF configuration...');
    this.token = prompt('Instructor Token');

    // fetch the sechema data for session form
    this.getSchmeaData();

    // fetch the sechema data for team form
    this.api_req('GET', '/api/team_form/get_schema', undefined, (rslt) => {
        var [res, status] = rslt;
        if (status != 200) {
            alert(`Failed to get schema: ${res.error}`);
            console.log(`API not-OK when get_schema: ${res.error}`)
            return;
        }

        this.setState({schema_team: res});
    });

    this.fetchSessions();
    this.fetchTeams();
    this.fetcher = window.setInterval(this.fetchSessions.bind(this), 30000);    // set a refresh interval for fetching the sessions
  }

  /*
    Clean up the component
  */
  componentWillUnmount() {
      window.clearInterval(this.fetcher);   // clear the interval - handle memory leaks
  }

  /*
    Function to fetch the session form
  */
  getSchmeaData() {
    this.api_req('GET', '/api/bof_form/get_schema', undefined, (rslt) => {
        var [res, status] = rslt;
        if (status != 200) {
            alert(`Failed to get schema: ${res.error}`);
            console.log(`API not-OK when get_schema: ${res.error}`)
            return;
        }

        this.setState({schema: res});
    });
  }

  /*
    Create a new bof session for a team
  */
  addSession(configuration) {
      configuration.token = this.token;

      if(configuration.team == null) {
          alert('Failed to add session: Select a team');
          return false;
      }

      // match the team string with team id
      let teamID;
      for(let i=0; i < this.state.teams.length; i++) {
          if(configuration.team == this.state.teams[i].name) {
            teamID = this.state.teams[i].id;
          }
      }

      // if team id is null then the team name is not present in current team list
      if(teamID == null) {
        alert('Failed to add session: Select a team');
        this.fetchTeams();  // refresh the team list
        return false;
      }

      this.setState({busy: this.state.busy + 1});
      this.api_req('POST', '/api/team/'+ teamID +'/session', JSON.stringify(configuration), (rslt) => {
          this.setState({busy: this.state.busy - 1});
          var [res, status] = rslt;
          if (status != 200) {
              alert(`Failed to add session: ${res.error}`);
              console.log(`API not-OK when add_session: ${res.error}`);
              return;
          }

          console.log(`Session added. New ID: ${res.id}.`);
          this.fetchSessions(); // refresh the session list
      });
  }

  /*
    Add a new team
  */
  addTeam(data) {
    this.setState({busy: this.state.busy + 1});
    data.token = this.token;
    this.api_req('POST', '/api/team', JSON.stringify(data), (rslt) => {
        this.setState({busy: this.state.busy - 1});
        var [res, status] = rslt;
        if (status != 200) {
            alert(`Failed to add session: ${res.error}`);
            console.log(`API not-OK when add_session: ${res.error}`);
            return;
        }

        console.log(`Team added. New ID: ${res.id}.`);
        this.fetchTeams();  // refresh the team list
        this.getSchmeaData(); // refresh the session form
    });
  }

  /*
    Query the list of teams
  */
  fetchTeams() {
    this.api_req('GET', `/api/team?token=${this.token}`, undefined, (rslt) => {
        var [res, status] = rslt;
        if (status != 200) {
            alert(`Failed to get schema: ${res.error}`);
            console.log(`API not-OK when get_schema: ${res.error}`)
            return;
        }
  
        this.setState({teams: res.teams});
      });
  }

  /*
    Remove a team
  */
  dropTeam(team_id) {
      this.setState({busy: this.state.busy + 1});
      this.api_req('DELETE', `/api/team/${team_id}?token=${this.token}`, undefined, (rslt) => {
          this.setState({busy: this.state.busy - 1});
          var [res, status] = rslt;
          if (status != 200) {
              alert(`Failed to drop session: ${res.error}`);
              console.log(`API not-OK when drop_session: ${res.error}`);
              return;
          }
          this.fetchTeams();  // refresh the team list
          this.getSchmeaData(); // refresh the session form
          console.log(`Team dropped.`);
      });
  }

  /*
    Stop the session
  */
  dropSession(session_id) {
      this.setState({busy: this.state.busy + 1});
      this.api_req('DELETE', `/api/team/session/${session_id}?token=${this.token}`, undefined, (rslt) => {
          this.setState({busy: this.state.busy - 1});
          var [res, status] = rslt;
          if (status != 200) {
              alert(`Failed to drop session: ${res.error}`);
              console.log(`API not-OK when drop_session: ${res.error}`);
              return;
          }

          for(var i=0; i<this.state.sessions.length; i++) {
            if(this.state.sessions[i].id == res.id) {
              this.state.sessions[i].dropped = true
            }
          }

          this.setState({'sessions': this.state.sessions });
          console.log(`Session dropped.`);
      });
  }

  /*
    Restart the docker container
  */
  restartContainer(session_id) {
    this.setState({busy: this.state.busy + 1});
    this.api_req('GET', `/api/team/session/${session_id}/docker?token=${this.token}`, undefined, (rslt) => {
        this.setState({busy: this.state.busy - 1});
        var [res, status] = rslt;
        if (status != 200) {
            alert(`Failed to restart container: ${res.error}`);
            console.log(`API not-OK when restartContainer: ${res.error}`);
            return;
        }

        this.fetchSessions();  // refresh the session list
        console.log(`Docker container restarted`);
    });
  }

  /*
    Fetch the answer value for the session
  */
  getAnswer(session_id) {
      this.setState({busy: this.state.busy + 1});
      this.api_req('GET', `/api/team/session/${session_id}/answer?token=${this.token}`, undefined, (rslt) => {
          this.setState({busy: this.state.busy - 1});
          var [res, status] = rslt;
          if (status != 200) {
              alert(`Failed to get answer: ${res.error}`);
              console.log(`API not-OK when get_answer: ${res.error}`);
              return;
          }
          prompt("Answer", res.ans);    // display the answer
      });
  }

  /*
    Display the error for the session
  */
  showError(details) {
      if(details.error) {
        prompt("Error Details", details.status);    // display the error
      }
  }

  render() {
    return (
    <div className='home'>
      <div className="panel-wrap row">
              <div className="col-md-8 col-sm-12 panel-add-session">
                  <legend>Current sessions</legend>
                  <div className="session-list-wrap">
                      <table className="session-list table table-bordered">
                          <tbody className="session-list-body">
                              <tr className="session-list-header">
                                  <th>Team Name</th>
                                  <th>Container ID</th>
                                  <th>Level</th>
                                  <th>Port</th>
                                  <th>#trials</th>
                                  <th>#cap</th>
                                  <th>Action</th>
                              </tr>
                              {this.state.sessions.filter(session => !session.dropped).map(session => {
                                var this_class = session.error ? 'error-table' : '';
                                return (<tr key={session.id} className="session-list-item">
                                  <td className={this_class} onClick={() => this.showError(session)}><Link to={`/t/${session.team_id}/log/${session.id}`}>{session.name}</Link></td>
                                  <td><code>{session.container_id}</code></td>
                                  <td>{session.level}</td>
                                  <td>{session.port}</td>
                                  <td>{session.trials}</td>
                                  <td>{session.successes}</td>
                                  <td>
                                      <button 
                                          className="action-btn btn btn-sm btn-success" 
                                          disabled={this.state.busy > 0}
                                          onClick={() => this.getAnswer(session.id)}
                                      >Get Answer</button>
                                      <button 
                                          className="action-btn btn btn-sm btn-danger" 
                                          disabled={this.state.busy > 0}
                                          onClick={() => this.restartContainer(session.id)}
                                      >Restart</button>
                                      <button 
                                          className="action-btn btn btn-sm btn-danger" 
                                          disabled={this.state.busy > 0}
                                          onClick={() => this.dropSession(session.id)}
                                      >Drop</button>
                                  </td>
                                </tr>)}
                              )}
                          </tbody>
                      </table>
                  </div>
              </div>
              <div className="col-md-4 col-sm-12 session-panel">
                  <div>
                    <legend>Add session</legend>
                    <Form 
                        ref={(f) => this.form = f}
                        formData={this.form_data}
                        schema={this.state.schema}
                        onSubmit={({formData}) => {
                            this.addSession(formData);
                        }}
                        noValidate={true}
                        disabled={this.state.busy > 0}
                        onChange={({formData}) => this.form_data = formData}
                        onError={errors => console.error("Form error:", this.form_data, errors)}
                    ></Form>
                    <button className="action-btn btn btn-info" onClick={() => {
                        this.form.submit();
                    }} >Submit</button>
                    <button className="action-btn btn btn-danger" onClick={() => {
                        this.form_data = {};
                        this.forceUpdate();
                    }} >Reset</button>
                  </div>
              </div>
          </div>
          <div className="panel-wrap row">
              <div className="col-md-8 col-sm-12 panel-add-session">
                  <legend>Teams</legend>
                  <div className="session-list-wrap">
                      <table className="session-list table table-bordered">
                          <tbody className="session-list-body">
                              <tr className="session-list-header">
                                    <th>Team ID</th>
                                    <th>Team Name</th>
                                    <th>Description</th>
                                    <th>Flag</th>
                                    <th>Action</th>
                              </tr>
                              {this.state.teams.map(team => <tr key={team.id} className="team-list-item">
                                  <td>{team.id}</td>
                                  <td>{team.name}</td>
                                  <td>{team.description}</td>
                                  <td><img className="team-flag" src={team.flag}></img></td>
                                  <td>
                                      <button 
                                          className="action-btn btn btn-sm btn-danger" 
                                          disabled={this.state.busy > 0}
                                          onClick={() => this.dropTeam(team.id)}
                                      >Drop Team</button>
                                  </td>
                              </tr>)}
                          </tbody>
                      </table>
                  </div>
              </div>
              <div className="col-md-4 col-sm-12 session-panel">
                  <div>
                    <legend>Add Team</legend>
                    <Form 
                        ref={(f) => this.team_form = f}
                        formData={this.team_form_data}
                        schema={this.state.schema_team}
                        onSubmit={({formData}) => {
                            this.addTeam(formData);
                        }}
                        noValidate={true}
                        disabled={this.state.busy > 0}
                        onChange={({formData}) => this.team_form_data = formData}
                        onError={errors => console.error("Form error:", this.team_form_data, errors)}
                    ></Form>
                    <button className="action-btn btn btn-info" onClick={() => {
                        this.team_form.submit();
                    }} >Submit</button>
                    <button className="action-btn btn btn-danger" onClick={() => {
                        this.team_form_data = {};
                        this.forceUpdate();
                    }} >Reset</button>
                  </div>
              </div>
          </div>
    </div>
    )
  }
}

export default Admin;