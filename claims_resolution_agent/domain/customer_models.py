from pydantic import BaseModel, ConfigDict, Field


class CustomerData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str
    approved_refunds_trailing_90d: int = Field(ge=0)