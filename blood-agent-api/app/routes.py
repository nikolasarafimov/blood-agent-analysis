from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from .agent_connector import run_agent_with_file
from .models import AgentResponse, Token, UserCreate
from .auth import create_access_token, authenticate_user, get_current_user
from .users import create_user, get_user

router = APIRouter()


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/users", response_model=dict)
async def create_new_user(user: UserCreate):
    existing = get_user(user.username)
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    create_user(user.username, user.password, user.full_name)
    return {"username": user.username}


@router.post("/run-agent", response_model=AgentResponse)
async def run_agent_endpoint(
    file: UploadFile = File(...),
    prompt: str = Form("Process this document"),
    current_user=Depends(get_current_user),
):
    file_bytes = await file.read()

    result = await run_agent_with_file(prompt, file_bytes, file.filename, uploaded_by=current_user.username)
    return result
