from pydantic import BaseModel


class FiscalRecord(BaseModel):
    tax_id: str
    business_name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    activity: str | None = None
    status: str = "ACTIVE"
