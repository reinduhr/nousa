# nousa
Add your favorite 📺 shows and nousa will create an ical feed containing upcoming episodes!

This is a very simple tool. It has no login system, so you cannot create multiple users, yet? 🤷‍♂️
What it does have is an easy to use UI which you can access with your browser. There you can search for tv shows and add them to your list. Your list will be checked for new episodes once a week. All episodes got one day added to their air dates due to worldwide availability.

I'm a beginning programmer. I used to use episodecalendar.com to keep me informed about upcoming episodes. Their limit on free accounts annoyed me, so I asked myself: "Can I make my own service so this limit is not a problem anymore?". Turns out I can! And it wasn't even that hard.
I know the code could be prettier, but it works! Now that it works I kinda don't wanna touch it anymore, and that's why I release it to the public. What's better for a newbie than to get critized by strangers on the internet, am I right?

Container exposes port 5000.
Mount path to data for calendar, database and logs is: /code/data.

docker pull reinduhr/nousa:latest

# this project is using: 
 - show data: api.**tvmaze**.com
 - docker image: **Python** 3.12.3-slim 
 - server: **Uvicorn** (ASGI web server)
 - web framework: **Starlette** (lightweight ASGI framework/toolkit)    
 - database: **SQLite**, **SQLAlchemy**, **Alembic**
 - template: **Jinja**, **Bootstrap**