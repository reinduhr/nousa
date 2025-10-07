# 📆 nousa 📺
add your favorite shows and nousa will create an ical feed keeping you informed on upcoming episodes!

![nousa ui preview](https://github.com/reinduhr/nousa/blob/main/static/nousa.gif)

this is a tool with an easy to use UI which is accessible by a browser. you can search for tv shows and add them to a list. episode data is updated once a week. nousa adds one day to an episode's official air date due to worldwide availability.\

## optional features
can be enabled by environment variables.
### email notifications
send out an email (basic auth) to notify you of any changes anyone makes regarding list/calendar entries.\
### jellyfin integration
scan your Jellyfin media server and present those shows on the recommendations page where you can easily add them to your list.
### sonarr integration
sync shows (that are not archived) to sonarr.\
you can optionally pass a comma separated list of nousa list ids (e.g. "1,2") to the allowed list environment variable. all lists will be synced if you don't use this env var.

see .env.example for more information on environment variables\
container exposes port 5000\
mount path to data for database and logs is: /code/data\
username:group = nousa:nousa, uid:gid = 3333:3333\

docker.io/reinduhr/nousa:latest

## this project is using: 
 - show data: api.**tvmaze**.com
 - docker image: **python** 3.x-slim
 - server: **uvicorn** (ASGI web server)
 - web framework: **starlette** (lightweight asgi framework/toolkit)    
 - database: **sqlite**, **sqlalchemy**, **alembic**
 - template: **jinja**, **bootstrap**
