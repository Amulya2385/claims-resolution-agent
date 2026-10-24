from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from claims_resolution_agent.application.services.customers import CustomerService
from claims_resolution_agent.domain.models import CustomerData
from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.repositories.customers import (
    CustomerRepository,
)


router = APIRouter(
    prefix="/api/v1/customers",
    tags=["customers"],
)


def get_db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


def get_customer_service(
    session: Session = Depends(get_db),
) -> CustomerService:
    repository = CustomerRepository(session)
    return CustomerService(repository)


@router.get(
    "/{customer_id}",
    response_model=CustomerData,
)
def get_customer(
    customer_id: str,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerData:
    customer = service.get_customer(customer_id)

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail=f"customer not found: {customer_id}",
        )

    return customer


@router.post(
    "",
    response_model=CustomerData,
    status_code=201,
)
def create_customer(
    customer: CustomerData,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerData:
    try:
        return service.create_customer(customer)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
