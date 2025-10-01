from pydantic import BaseModel, Field, model_validator


class ChangeUserPasswordRequest(BaseModel):
    password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)

    @model_validator(mode="after")
    def check_passwords_match(self) -> "ChangeUserPasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self
