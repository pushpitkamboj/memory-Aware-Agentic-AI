from fastapi import FastAPI, Depends
from sqlmodel import SQLModel, Field, Session, create_engine, select  # ← select imported
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

# FastAPI app
app = FastAPI()

engine = create_engine("sqlite:///todos.db")

# Todo Model
class Todo(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True) #auto incrememented the id by DB
    name: str
    description: str
    
class TodoIn(BaseModel):
    name: str
    description: str
    
class TodoUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

SQLModel.metadata.create_all(engine)

# Session dependency
def get_session():
    with Session(engine) as session:
        yield session


# === ROUTES ===
@app.get("/read")
def get_todos(session: Session = Depends(get_session)):
    todos = session.exec(select(Todo)).all()
    
    return todos

@app.post("/post")
def create_todo(todo: TodoIn, session: Session = Depends(get_session)):
    user_data = Todo.model_validate(todo)
    
    session.add(user_data) #no need for validation, so put in session directly
    session.commit()
    session.refresh(user_data) #brought back to send back 
    
    return user_data

@app.put("/update/{todo_id}")
def update_todo(todo_id: int, todo: TodoUpdate, session: Session = Depends(get_session)):
    db_todo = session.get(Todo, todo_id)
    if not db_todo:
        raise HTTPException(status_code=404, detail="todo not found in the DB")
    
    db_todo.sqlmodel_update(todo)
    session.add(db_todo)
    session.commit()

    return {"message": "the todo is updated successfully"}

@app.delete("/delete/{todo_id}")
def delete_todo(todo_id: int, session: Session = Depends(get_session)):
    db_todo = session.get(Todo, todo_id)
    if not db_todo:
        raise HTTPException(status_code=404, detail= "the todo was not there")
    
    session.delete(db_todo)
    session.commit
    
    return{"message": "the todo has been deleted successfully"}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)