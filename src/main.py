from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# startup functions
from src.log_config import setup_logging, delete_files_not_in_use
from src.db import engine, db_migrations
from src.scheduler import start_scheduler

# web routes
from src.routes.web_routes import homepage, search, list_page, lists_page, download_redirect, jellyrec

# logic routes
from src.cal_logic.input import add_to_series, add_to_archive
from src.cal_logic.update import del_series
from src.cal_logic.list_ops import create_list, rename_list
from src.cal_logic.output import download_calendar

routes = [
    Route("/", endpoint=homepage, methods=["GET"]),
    Mount("/nousa", app=StaticFiles(directory="static"), name="static"),
    Route("/search", endpoint=search, methods=["GET", "POST"]),
    Route("/add_show", endpoint=add_to_series, methods=["GET", "POST"]),
    Route("/archive_show", endpoint=add_to_archive, methods=["GET", "POST"]),
    Route("/delete_show", endpoint=del_series, methods=["GET", "POST"]),
    Route("/subscribe", endpoint=download_redirect, methods=["GET"]),
    Route("/create_list", endpoint=create_list, methods=["GET", "POST"]),
    Route("/rename_list", endpoint=rename_list, methods=["GET", "POST"]),
    Route("/lists", endpoint=lists_page, methods=["GET", "POST"]),
    Route("/list/{list_id}", endpoint=list_page, methods=["GET", "POST"]),
    Route("/subscribe/{list_id}", endpoint=download_calendar, methods=["GET"]),
    Route("/recommendations", endpoint=jellyrec, methods=["GET"])
]

@asynccontextmanager
async def lifespan(app: Starlette):
    # --- Startup Logic ---
    # This runs before the app starts taking requests
    setup_logging()
    db_migrations()
    delete_files_not_in_use()
    start_scheduler()
    
    yield  # The app runs while execution is "paused" here
    
    # --- Shutdown Logic ---
    # This runs when the app is shutting down
    engine.dispose()
    print("Shutting down...")

app = Starlette(
    debug=False, 
    routes=routes, 
    lifespan=lifespan
)
