import React from 'react';
import { Link } from 'react-router-dom';

export default class AppWrapper extends React.Component {
  constructor() {
    super();
  }

  render() {
    return (
      <div className='app-container'>
        <nav className="navbar navbar-dark bg-light">
          <Link  className="navbar-brand" to={'/'}>Home</Link>
          <Link  className="navbar-brand" to={'/s'}>Teams</Link>
          <Link  className="navbar-brand" to={'/admin'}>Admin</Link>
        </nav>
        <div className='body-content'>
          {this.props.children}
        </div>
      </div>
    )
  }
}