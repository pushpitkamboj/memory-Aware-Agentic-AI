from agents import Agent, run_demo_loop, function_tool
import asyncio

from pydantic import BaseModel, ValidationError
from typing import List, Optional
from enum import Enum

import httpx
    
class TodoIn(BaseModel):
    name: str
    description: str
    
class TodoResponse(TodoIn):
    id: int

@function_tool
async def get_request() -> List[dict]:
    """
    Return list of todo dicts. If failure, return empty list.
    This is JSON-serializable and safe for agents.
    """
    url = "http://localhost:8000/read"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json() #converted the response to python inbuilt data type which is most suitable...

            # If your API already returns the correct shape, just validate lightly:
            parsed = []
            for item in data:
                try:
                    todo = TodoResponse.model_validate(item) # we are validating each object coming from the API
                    parsed.append(todo.model_dump())  # we are adding the responses and creating a list named parsed, which has python inbuilt D.S using model_dump()
                except ValidationError as e:
                    # skip invalid items but keep going
                    print("Skipping invalid todo item:", e)
            return parsed

    #some exception i picked from docs
    except httpx.RequestError as exc:
        print("Network error calling", url, "->", exc)
        return ["network error"]
    except ValueError as exc:
        print("Invalid JSON from", url, "->", exc)
        return ["invalid json"]

@function_tool
async def post_request(todo: TodoIn) -> dict | None:
    """
    Accepts TodoIn (Pydantic). Sends JSON to /post and returns the created todo as a plain dict.
    Returns None on failure.
    """
    url = "http://localhost:8000/post"

    #since todo is an instance of TodoIn we need to serialize it in json format before sending the post request
    payload = todo.model_dump()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=payload) #although its written json parameter, but it expects the python inbuilt data type, 
            # therefore see above we converted pydantic instance to python type 
            resp.raise_for_status()
            # resp.json() can be of any python data type list, dictionary depending on what server has sent
            # we leave the headache of validation on pydantic 
            updated = TodoResponse.model_validate(resp.json()) #resp.json is a method of httpx class...
            return updated.model_dump()
    
    
        except httpx.RequestError as e:
            print("Network error:", e)
        except httpx.HTTPStatusError as e:
            print("HTTP error:", e.response.status_code, e.response.text)
        except Exception as e:
            print("Unexpected error:", e)
    return None



@function_tool
async def put_request(todo: TodoIn, todo_id: int) -> dict | None:
    """
    Update todo at PUT /update/{todo_id}
    - Sends JSON payload (name, description)
    - Returns updated todo as plain dict on success, else None
    """
    url = f"http://localhost:8000/update/{todo_id}"
    payload = todo.model_dump()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.put(url, json=payload)
            resp.raise_for_status()
            updated = TodoResponse.model_validate(resp.json())
            return updated.model_dump()
        
        
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code} -> {e.response.text}")
        except httpx.RequestError as e:
            print(f"Network error: {e}")
        except Exception as e:
            print("Unexpected error:", e)
    return None         

@function_tool
async def delete_request(todo_id: int) -> dict | None:
    """
    Delete todo at DELETE /delete/{todo_id}
    - Calls DELETE endpoint
    - Returns JSON response or None on error
    """
    url = f"http://localhost:8000/delete/{todo_id}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.delete(url)
            resp.raise_for_status()
            data = resp.json()  #we are just checking we the return type is not dict return None, 
            #ideally we should create a pydantic model and then validate the response, but yeah shortcut 
            if not isinstance(data, dict):
                return ["the return type from server was not dictionary"]
            return data
            
            
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code} -> {e.response.text}")
        except httpx.RequestError as e:
            print(f"Network error: {e}")
        except Exception as e:
            print("Unexpected error:", e)
    return None
    
    
read_agent = Agent(
    name = "read agent",
    instructions = "using the function tool return the answer in most polite way and also suggest things based on user's todo response from function tool",
    tools = [get_request],
)

create_agent = Agent(
    name = "create agent",
    instructions = (
        "understand the input and do not modify it, use the tool to send the data, if the name or description is not provided then assume it by itself with minimal interruption in the essence of the user request."
        "make sure to follow the output type , none of the field should be null or empty"
        """the data in the way u have to send is :
            "name": "Going to Delhi",
            "description": "To meet Shivani for my meeting"
        """
        "if the tool responds with None then send sorry message, if the tool replies {`Todo model`} datatype then reply that todo has been created and stored successfully"
    ),
    tools = [post_request],
)

update_agent = Agent(
    name = "update agent",
    instructions = (
        "your task is to call the get_request function and then based on user prompt find the relevant id of the todo based on what is returned from the tool and then send the data to put_request for updating the name or description or both of the said todo"
        "in case get_request return something empty or returns an exception poltiely respond with not possible due to some glitch"
        "now based on response of put_request if its true then return that todo is update successfully else return with sorry polite response"
    ),
    tools = [
        get_request,
        put_request
    ]
)

delete_agent = Agent(
    name = "delete agent",
    instructions = "your task is to interpret the user query for deleting one or more todos, call get request tool, watch all the todos and on the basis of user prompt decide which all todo have to be deleted, after that use delete_request tool to delete the specific todo by passing the id of that todo",
    tools = [
        get_request,
        delete_request
    ]
)
    

orchestrator = Agent(
    name = "main_agent",
    instructions = (
        "You are the main agent of the workflow, strictly follow the tools you have available and if none matches then politely say your request does not fit with my aka toDo agent guidelines"
        "understand the user prompt and guide the tools based on request if it is read, update, delete, create to the said tools respectively"
        "DO NOT modify the name and description of the prompt if the request is to update or add a new todo, u can correct the english but do not change the meaning, sentiment of the name and description also if any on of them is not explicilty said in user prompt, create by understanding the input"
    ),
    tools= [
        read_agent.as_tool(
            tool_name= "read_agent",
            tool_description="respond to the read request to the user accordingly",
        ),
        update_agent.as_tool(
            tool_name = "update_agent",
            tool_description="respond to the update request to the user accordingly",
        ),
        delete_agent.as_tool(
            tool_name = "delete_agent",
            tool_description="respond to the delete request to the user accordingly"
        ),
        create_agent.as_tool(
            tool_name = "create_agent",
            tool_description="respond to the create request to the user accordingly"
        )
    ],
)

        
    # read_agent = Agent(
    #     name = "read agent",
    #     instructions = "using the function tool return the answer in most polite way and also suggest things based on user's todo response from function tool",
    #     tools = [get_request],
    # )
# print(asyncio.run(get_request()))


# if __name__ == "__main__":
#     asyncio.run(main_agent())