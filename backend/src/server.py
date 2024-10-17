import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Final

import uvicorn
from bson import ObjectId
from fastapi import FastAPI, status
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from dal import ListSummary, ToDoDAL, ToDoList

COLLECTION_NAME: Final[str] = "todo_lists"
MONGODB_URI: Final[str] = os.environ["MONGODB_URI"]
DEBUG = os.environ.get("DEBUG", "").strip().lower() in {"1", "true", "on", "yes"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    client = AsyncIOMotorClient(MONGODB_URI)
    database = client.get_default_database()

    # Ensure that the database is available before proceeding
    pong = await database.command("ping")
    if int(pong["ok"]) != 1:
        raise RuntimeError("Database is not available")
    
    todo_lists = database.get_collection(COLLECTION_NAME)
    app.todo_dal = ToDoDAL(todo_lists) # type: ignore

    # Yield control back to the FastAPI application
    yield

    # Shutdown
    client.close()

app = FastAPI(lifespan=lifespan, debug=DEBUG)