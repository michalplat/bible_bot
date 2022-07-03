from typing import Any, Dict, List, Optional
import pydantic


class Verses(pydantic.BaseModel):
    user_input: Optional[List[str]] = ["1", "1"]
    from_verse: Optional[str]
    to_verse: Optional[str]
    repr_verses: Optional[str]

    @pydantic.validator("user_input", pre=True)
    def validate_user_input(cls, v: str) -> List[str]:
        if v.isdigit():
            return [v, v]
        elif "-" in v and v.count("-") == 1:
            v = v.split("-")
            if v[0].isdigit() and v[1].isdigit() and int(v[0]) < int(v[1]):
                return v
        raise ValueError("user_input doesn't follow verse format")

    @pydantic.validator("repr_verses", always=True)
    def validate_representation(cls, v: None, values: Dict[str, Any]) -> str:
        if values["from_verse"] == values["to_verse"]:
            return values["from_verse"]
        else:
            return "-".join(values["user_input"])

    @pydantic.validator("from_verse", always=True)
    def validate_from_verses(cls, v: None, values: Dict[str, Any]) -> str:
        return values["user_input"][0] if "user_input" in values else v

    @pydantic.validator("to_verse", always=True)
    def validate_to_verses(cls, v: None, values: Dict[str, Any]) -> str:
        return values["user_input"][1]if "user_input" in values else v



