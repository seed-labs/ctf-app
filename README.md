# CTF-App

### Requirements

We use docker containers to build and run the CTF application. We need the below applications setup on host machine

- Docker - v19.03+

- Docker Compose - v1.25+


## Development

To start the application we need to run

```
docker-compose -f docker-compose.dev.yml up
```

This will build the application and bring up the services. There are 4 different services that currently run in development mode
* Frontend - This is a web application built using ReactJS, Redux and Socket.io
* Backend - This is the backend API service used to start the sessions and store team details, its built using Flask and Socket.io server module. 
* SwaggerUI - The Flask API generates a OpenAPI spec for documentation which can be accessed by going to `http://localhost`
* MySQL - Service used to store persistant data like team and session details

Once the application is up we can access the frontend by using the url `http://localhost:5000`. The admin page has a default auth with token value `secret`. 

The teams form is used to create a new team which can be assigned with a CTF session. Currently we have one CTF lab called Buffer Overflow. 

## Production

To start the application we need to run

```
docker-compose up
```
