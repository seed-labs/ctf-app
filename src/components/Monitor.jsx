import React from 'react';
import SessionCard from './SessionCard';
import socketIOClient from "socket.io-client";

class Monitor extends React.Component {
  constructor(props) {
    super(props);
    this.socket;

    this.state = {
      sessions: [],
    };
    this.victory_audio = new Audio(location.origin + '/src/assets/victory.wav');
    this.victory = function() {
        this.victory_audio.play().catch(e => console.log('Error playing victory audio: ', e));
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
    this.api_req('GET', `/api/get_sessions_public`, undefined, (rslt) => {
      var [res, status] = rslt;
      if (status != 200) {
          console.log(`API not-OK when fetchSessions: ${res.error}`)
          return;
      }

      this.setState({sessions: res.sessions});
    });
  }

  /*
    Reset the flag displayed
  */
  clearFlag(session_id) {
    this.api_req('DELETE', `/api/team/session/${session_id}/flag`, undefined, (rslt) => {
        var [res, status] = rslt;
        if (status != 200) {
            console.log(`API not-OK when clear flag: ${res.error}`);
            return;
        }

        this.fetchSessions();
    });
  }

  /*
    Initialize the socket connection
  */
  componentDidMount() {
      this.fetchSessions();
      this.socket = socketIOClient(process.env.API_URL);
      this.fetcher = window.setInterval(this.fetchSessions.bind(this), 5000);

      this.socket.on("emit_success", data => {
        console.log("emit_success: ", data);
        this.fetchSessions();
        this.victory();
      });
  }

  /*
    Clean up the component
  */
  componentWillUnmount() {
      window.clearInterval(this.fetcher);
      this.socket.off();
  }

  render() {
    var running_sessions = this.state.sessions.filter(session => session.running);
    var some_expanded = running_sessions.some(session => session.expanded);

    if (running_sessions.length > 0) return <div className="box container">
        <div className="row">
            <div>Server URL: {location.hostname}</div>
            {running_sessions.map(session => {
                var this_hide = some_expanded && !session.expanded;
                var this_class = this_hide ? 'hide' : (
                    session.expanded ? 'card-wrap-expanded' : 'card-wrap col-12 col-sm-6 col-lg-4 col-xl-3'
                );
                return <div key={session.id} className={this_class}>
                    <SessionCard 
                        session={session} key={'card_' + session.id} 
                        expanded={session.expanded}
                        hints={false}
                        trials={session.trials}
                    />
                    <div className="card-ctrl-btn-wrap">
                        <button key={'btn_reset_' + session.id} onClick={() => this.clearFlag(session.id)}>Clear Flag</button>
                    </div>
                </div>;
            })}
        </div>
    </div>;
    else return <div className="info-no-sessions">
        No sessions are currently running. 
    </div>
  }
}

export default Monitor;