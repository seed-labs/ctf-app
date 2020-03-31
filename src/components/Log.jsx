import React from 'react';
import SessionCard from './SessionCard';
import socketIOClient from "socket.io-client";
import { connect } from 'react-redux';

let intVal;

class Log extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      log: 'Listening to log....\n',
      session: {},
      trials: 0,
    };
    this.socket;
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
    Initialize the socket connection
  */
  componentDidMount() {
    const { endpoint } = this.state;
    const { session_id } = this.props.match.params;
    this.socket = socketIOClient(process.env.API_URL);

    this.socket.on("emit_log_" + session_id, data => {
      console.log("log data: ", data);
      this.setState({ log: this.state.log + data.log });
    });

    this.socket.on("emit_trial_count_" + session_id, data => {
      console.log("trial count data: ", data);
      this.setState({ trials: data.count });
    });

    this.socket.on("emit_refresh_" + session_id, data => {
      console.log("emit_refresh: ", data);
      this.fetchSession();
    });

    let startFetchingLogs = () => this.socket.emit('fetch-logs', { container_id: parseInt(session_id) })
    this.socket.on('connect', function() {
      console.log("Connected from socket");
      startFetchingLogs();
      intVal = setInterval(startFetchingLogs, 50000);
    });

    this.socket.on('disconnect', function() {
      console.log("Disconnected from socket");
      clearInterval(intVal);
    });

    this.fetchSession(); // query the session
    this.fetcher = window.setInterval(this.fetchSession.bind(this), 60000);
  }

  /*
    Query the session details
  */
  fetchSession() {
    const { session_id } = this.props.match.params;
    this.api_req('GET', `/api/team/session/${session_id}`, undefined, (rslt) => {
      var [res, status] = rslt;
      if (status != 200) {
          alert(`Failed to get schema: ${res.error}`);
          console.log(`API not-OK when get_schema: ${res.error}`)
          return;
      }

      // parse the hints 
      if(res && res.hints) {
        res.hints = res.hints.replace(/:\|/g, ':').replace(/\|/g,'  |  ')
      }
      
      // update the session state
      if(res && res.running) {
        this.setState({session: res, trials: res.trials});
      }
      
      this.ready = true;
    });
  }

  /*
    Clean up the component
  */
  componentWillUnmount() {
    clearInterval(intVal);
    this.socket.off();
    window.clearInterval(this.fetcher);
  }

  render() {
    return (
      <div className='log row'>
        {
          this.state.session && this.state.session.id &&
            <div className='card-wrap col-12 col-sm-6 col-lg-4 col-xl-3'>
              <SessionCard 
                  session={this.state.session} key={'card_' + this.state.session.id} 
                  expanded={false}
                  hints={true}
                  trials={this.state.trials}
              />
            </div>
        }
        <div className='card-wrap col-12 col-sm-6 col-lg-8 col-xl-9'>
          <pre className="card log-output">
            {this.state.log}
          </pre>
        </div>
      </div>
    )
  }
}

// const mapStateToProps = state => {
//   return {
//     items: state.items
//   }
// }

// const mapDispatchToProps = dispatch => {
//   return {
//     fetchItems: (session_id) => {
//       dispatch(fetchItems(config.endpoint + 'team/session/' + session_id))
//     }
//   }
// }

const LogComponent = connect(
  null,
  null
)(Log);

export default LogComponent;