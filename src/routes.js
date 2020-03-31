import React from 'react';
import { Route, Switch } from 'react-router-dom';
import App from './components/App';
import Admin from './components/Admin';
import Monitor from './components/Monitor';
import MonitorSmall from './components/MonitorSmall';
import Log from './components/Log';

const routes = (
  <App>
    <Switch>
      <Route exact path='/' component={Monitor} />
      <Route exact path='/s' component={MonitorSmall} />
      <Route exact path='/admin' component={Admin} />
      <Route path='/t/:team_id/log/:session_id' component={Log} />
    </Switch>
  </App>
)

export { routes };