import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Final

import uvicorn
from bson import ObjectId
from fastapi import FastAPI, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from dal import ListSummary, ToDoDAL, ToDoList

COLLECTION_NAME: Final[str] = "todo_lists"
MONGODB_URI: Final[str] = os.environ["MONGODB_URI"]
DEBUG = os.environ.get("DEBUG", "").strip().lower() in {"1", "true", "on", "yes"}


class ToDoApp(FastAPI):
    todo_dal: ToDoDAL

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.add_event_handler("startup", lifespan)
        # self.add_event_handler("shutdown", lifespan)


@asynccontextmanager
async def lifespan(app: ToDoApp):
    # Startup
    client = AsyncIOMotorClient(MONGODB_URI)
    database = client.get_default_database()

    # Ensure that the database is available before proceeding
    pong = await database.command("ping")
    if int(pong["ok"]) != 1:
        raise RuntimeError("Database is not available")

    todo_lists = database.get_collection(COLLECTION_NAME)
    app.todo_dal = ToDoDAL(todo_lists)  # type: ignore

    # Yield control back to the FastAPI application
    yield

    # Shutdown
    client.close()


app = ToDoApp(lifespan=lifespan, debug=DEBUG)


@app.get("/api/lists")
async def get_all_lists() -> list[ListSummary]:
    return [list_summary async for list_summary in app.todo_dal.list_todo_lists()]


class NewList(BaseModel):
    name: str


class NewListResponse(BaseModel):
    id: str
    name: str


@app.post("/api/lists", status_code=status.HTTP_201_CREATED)
async def create_todo_list(new_list: NewList) -> NewListResponse:
    return NewListResponse(
        id=await app.todo_dal.create_todo_list(new_list.name), name=new_list.name
    )


@app.get("/api/lists/{list_id}")
async def get_list(list_id: str) -> ToDoList:
    """Get a single to-do list by its ID."""
    return await app.todo_dal.get_todo_list(list_id)


@app.delete("/api/lists/{list_id}")
async def delete_list(list_id: str) -> dict[str, bool]:
    """Delete a single to-do list by its ID."""
    return {"success": await app.todo_dal.delete_todo_list(list_id)}


class NewItem(BaseModel):
    label: str


class NewItemResponse(BaseModel):
    id: str
    label: str


@app.post("/api/lists/{list_id}/items", status_code=status.HTTP_201_CREATED)
async def create_todo_item(list_id: str, new_item: NewItem) -> ToDoList:
    item = await app.todo_dal.create_item(list_id, new_item.label)
    if item is None:
        raise HTTPException(status_code=404, detail="List not found")
    return item


@app.delete("/api/lists/{list_id}/items/{item_id}")
async def delete_item(list_id: str, item_id: str) -> ToDoList:
    """Delete a single to-do item by its ID."""
    todo_list = await app.todo_dal.delete_item(list_id, item_id)
    if todo_list is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return todo_list


class ToDoItemUpdate(BaseModel):
    item_id: str
    checked_state: bool


@app.patch("/api/lists/{list_id}/checked_state")
async def set_checked_state(list_id: str, item_update: ToDoItemUpdate) -> ToDoList:
    """Set the checked state of a single to-do item."""
    todo_list = await app.todo_dal.set_checked_state(
        list_id, item_update.item_id, item_update.checked_state
    )
    if todo_list is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return todo_list


class DummyResponse(BaseModel):
    id: str
    when: datetime


@app.get("/api/dummy")
async def get_dummy() -> DummyResponse:
    return DummyResponse(id=str(ObjectId()), when=datetime.now())


def main(argv=sys.argv[1:]):
    try:
        uvicorn.run("server:app", host="0.0.0.0", port=3001, reload=DEBUG)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
