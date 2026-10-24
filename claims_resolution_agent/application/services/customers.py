from claims_resolution_agent.domain.models import CustomerData
from claims_resolution_agent.infrastructure.models import Customer
from claims_resolution_agent.infrastructure.repositories.customers import (
    CustomerRepository,
)


class CustomerService:
    def __init__(self, repository: CustomerRepository):
        self.repository = repository

    def get_customer(self, customer_id: str) -> CustomerData | None:
        customer = self.repository.get_by_id(customer_id)

        if customer is None:
            return None

        return CustomerData(
            customer_id=customer.customer_id,
            approved_refunds_trailing_90d=customer.approved_refunds_trailing_90d,
        )

    def create_customer(self, data: CustomerData) -> CustomerData:
        existing = self.repository.get_by_id(data.customer_id)

        if existing is not None:
            raise ValueError(
                f"customer already exists: {data.customer_id}"
            )

        customer = Customer(
            customer_id=data.customer_id,
            approved_refunds_trailing_90d=data.approved_refunds_trailing_90d,
        )

        self.repository.add(customer)
        self.repository.session.commit()

        return data
