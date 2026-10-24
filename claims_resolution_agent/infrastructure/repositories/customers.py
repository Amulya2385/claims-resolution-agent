from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Customer


class CustomerRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, customer_id: str) -> Customer | None:
        statement = select(Customer).where(
            Customer.customer_id == customer_id
        )
        return self.session.scalar(statement)

    def add(self, customer: Customer) -> Customer:
        self.session.add(customer)
        self.session.flush()
        return customer
