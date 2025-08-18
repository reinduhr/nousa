# nousa
Add your favorite 📺 shows and nousa will create an ical feed keeping you informed on upcoming episodes!

![nousa ui preview](https://github.com/reinduhr/nousa/blob/main/static/nousa.gif)

This is a tool with an easy to use UI which is accessible by a browser. You can search for tv shows and add them to a list. Episode data is updated once a week. nousa adds one day to an episode's official air date due to worldwide availability.\
There's also the option to have this application send out an email to notify you of any changes anyone makes regarding list/calendar entries.\
nousa can also scan your Jellyfin media server so you can easily add those scanned shows to your list.

See .env.example for environment variables\
Container exposes port 5000\
Mount path to data for calendar, database and logs is: /code/data\
username:group = nousa:nousa, uid:gid = 3333:3333\

docker.io/reinduhr/nousa:latest

# wanna try it out?
PULL IMAGE\
docker pull reinduhr/nousa:latest

RUN CONTAINER\
docker run --name nousa -p 5000:5000 nousa

# this project is using: 
 - show data: api.**tvmaze**.com
 - docker image: **Python** 3.12.4-slim 
 - server: **Uvicorn** (ASGI web server)
 - web framework: **Starlette** (lightweight ASGI framework/toolkit)    
 - database: **SQLite**, **SQLAlchemy**, **Alembic**
 - template: **Jinja**, **Bootstrap**
