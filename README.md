# nousa
Add your favorite 📺 shows and nousa will create an ical feed containing upcoming episodes!

![nousa ui preview](https://github.com/reinduhr/nousa/blob/main/nousa.gif)

This is a tool with an easy to use UI which you can access with your browser. You can search for tv shows and add them to a list. All lists will be checked for new episodes once a week. nousa adds one day to an episode's official air date due to worldwide availability.

Container exposes port 5000\
Mount path to data for calendar, database and logs is: /code/data\
username:group = nousa:nousa, uid:gid = 3333:3333\
Default timezone is Europe/Amsterdam
RAM usage is around 50MB

docker.io/reinduhr/nousa:latest

# Wanna try it out?
PULL IMAGE
docker pull reinduhr/nousa:latest

BUILD CONTAINER FROM IMAGE
docker build -t nousa .

RUN CONTAINER
docker run --name nousa -p 5000:5000 nousa

# this project is using: 
 - show data: api.**tvmaze**.com
 - docker image: **Python** 3.12.4-slim 
 - server: **Uvicorn** (ASGI web server)
 - web framework: **Starlette** (lightweight ASGI framework/toolkit)    
 - database: **SQLite**, **SQLAlchemy**, **Alembic**
 - template: **Jinja**, **Bootstrap**
