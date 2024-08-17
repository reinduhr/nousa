# nousa
Add your favorite 📺 shows and nousa will create an ical feed containing upcoming episodes!

This is a very simple tool which has an easy to use UI which you can access with your browser. There you can search for tv shows and add them to the list. This list will be checked for new episodes once a week. nousa adds one day to an episode's official air date due to worldwide availability.

Container exposes port 5000\
Mount path to data for calendar, database and logs is: /code/data\
username is nousa (uid:gid = 3333:3333)

docker.io/reinduhr/nousa:latest

# this project is using: 
 - show data: api.**tvmaze**.com
 - docker image: **Python** 3.12.4-slim 
 - server: **Uvicorn** (ASGI web server)
 - web framework: **Starlette** (lightweight ASGI framework/toolkit)    
 - database: **SQLite**, **SQLAlchemy**, **Alembic**
 - template: **Jinja**, **Bootstrap**
