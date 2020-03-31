import React from 'react';
import { Link } from 'react-router-dom';

class SessionCard extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            team: {}
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
    Query the team details
  */
    fetchTeamDetails(team_id) {
        this.api_req('GET', `/api/team/${team_id}`, undefined, (rslt) => {
          var [res, status] = rslt;
          if (status != 200) {
              console.log(`API not-OK when fetchTeamDetails: ${res.error}`)
              return;
          }

          this.setState({team: res});
        });
    }

  /*
    Initialize the sessions list
  */
    componentDidMount() {
        this.fetchTeamDetails(this.props.session.team_id);
    }

    render() {
        var session = this.props.session;
        var flag_el;
        if(!session.flag_status) {
            flag_el = <div className="flag_placeholder">Flag Not Captured Yet</div>;
        } else {
            if(this.state.team.flag != '') {
                flag_el = <img className="flag_img" src={this.state.team.flag}></img>
            } else {
                flag_el = <img className="flag_img" src={`src/assets${session.flag_url}`}></img>
            }
        }

        var flag_wrap = <div className="flag">{flag_el}</div>

        if(this.props.small) {
            return <div className={session.flag_status ? 'card flag-captured': 'card'}>
                        <div className="title-large">
                            <Link to={`/t/${session.team_id}/log/${session.id}`}>{session.name}/{session.id}</Link>
                        </div>
                    </div>;
        } else {
            return <div className={session.expanded ? 'card-expanded': 'card'}>
            <div className="title"><Link to={`/t/${session.team_id}/log/${session.id}`}>{session.name}/{session.id}</Link></div>
                <div className="session-info">
                    <div className="server-info-wrap">
                        <div className="server-info">
                            <div className="panel-wrap row">
                                <div className="col-md-6 col-sm-6">
                                    Port: {session.port}
                                </div>
                                <div className="col-md-6 col-sm-6">
                                    Level: {session.level}
                                </div>
                            </div> 
                        </div>
                    </div>
                    <div className="stats-warp">
                        <div className="stats">
                            <div className="panel-wrap row">
                                <div className="col-md-6 col-sm-6">
                                    Trials: {this.props.trials}
                                </div>
                                <div className="col-md-6 col-sm-6">
                                    Success: {session.successes}
                                </div>
                            </div>
                        </div>
                    </div>
                    {
                        this.props.hints && 
                        <div className="hints-warp">
                            <div className="subtitle">Hints</div> 
                            <div className="hints">
                                <pre>{session.hints == '' ? 'N/A': session.hints}</pre>
                            </div>
                        </div>
                    }
                    {flag_wrap}
                    <div className={session.expanded ? 'console-wrap' : 'hide'}>
                        <pre className="console">{session.console_data ? session.console_data.join('') : 'No console output avaliable at this time.'}</pre>
                    </div>
                </div>
            </div>;
        }
            
    }
};

export default SessionCard;