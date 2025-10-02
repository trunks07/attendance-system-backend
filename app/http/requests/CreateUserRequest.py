import re
from pydantic import BaseModel, field_validator, model_validator


class CreateUserRequest(BaseModel):
    email: str
    full_name: str
    password: str
    confirm_password: str

    @field_validator("email")
    def validate_email(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v

    @model_validator(mode="after")
    def check_passwords_match(self) -> "CreateUserRequest":
        if self.password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self
