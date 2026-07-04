from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class StatusResponse(BaseModel):
    session_exists: bool
    ollama_available: bool
    blackboard_login_url: str
    blackboard_courses_url: str
