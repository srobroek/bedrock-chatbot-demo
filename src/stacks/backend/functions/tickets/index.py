import os
from datetime import datetime, timezone
import uuid
from typing_extensions import Annotated

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.event_handler import BedrockAgentResolver
from aws_lambda_powertools.event_handler.exceptions import NotFoundError, ServiceError
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler.openapi.params import Body, Path
from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute,
    NumberAttribute,
    UnicodeSetAttribute,
    UTCDateTimeAttribute, ListAttribute
)
from enum import Enum



# Configuration
CONFIG = {
    "table_name": os.environ.get("TABLE_NAME", "placeholder"),
    "region": os.environ.get("AWS_REGION", "us-east-1")
}



# Initialize services
logger = Logger(service="ticket-service")
tracer = Tracer()
app = BedrockAgentResolver()


class TicketStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class TicketModel(Model):
    """DynamoDB model for tickets with integrated ticket operations"""
    class Meta:
        table_name = CONFIG["table_name"]
        region = CONFIG["region"]

    user_id = UnicodeAttribute(hash_key=True)
    id = UnicodeAttribute(range_key=True)
    title = UnicodeAttribute()
    description = UnicodeAttribute()
    status = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
    comments = ListAttribute()

    @classmethod
    def get_ticket(cls, ticket_id: str, user_id: str):
        """Get a specific ticket with error handling"""
        logger.debug("Attempting to retrieve ticket", extra={

            "ticket_id": ticket_id
        })
        try:
            ticket = cls.get(range_key=ticket_id, hash_key=user_id)
            logger.info("Successfully retrieved ticket", extra={
                "user_id": user_id,
                "ticket_id": ticket_id,
                "status": ticket.status
            })
            return ticket
        except cls.DoesNotExist:
            logger.warning("Ticket not found", extra={
                "user_id": user_id,
                "ticket_id": ticket_id
            })
            raise NotFoundError(f"Ticket with ID {ticket_id} not found")
        except Exception as e:
            logger.error("Failed to retrieve ticket", extra={
                "user_id": user_id,
                "ticket_id": ticket_id,
                "error": str(e)
            })
            raise ServiceError("Error retrieving ticket")

    @classmethod
    def get_all_tickets(cls) -> dict:
        """Get all ticket IDs"""
        logger.debug("Attempting to fetch all tickets")
        try:
            tickets = cls.scan(
                attributes_to_get=['id'],
                page_size=100
            )
            ticket_list = [dict(ticket.attribute_values) for ticket in tickets]
            logger.info("Successfully retrieved all tickets", extra={
                "ticket_count": len(ticket_list)
            })
            return {"tickets": ticket_list}
        except Exception as e:
            logger.error("Failed to fetch tickets", extra={
                "error": str(e)
            })
            raise ServiceError("Error fetching tickets")
    @classmethod
    def get_ticket_by_user_id(cls,
                              user_id: str,
                              ) -> dict:
        """Get all tickets for a specific user"""
        logger.debug("Attempting to fetch tickets by user ID", extra={
            "user_id": user_id
        })
        try:
            tickets = cls.query(user_id)
            ticket_list = [dict(ticket.attribute_values) for ticket in tickets]
            logger.info("Successfully retrieved tickets by user ID", extra={
                "user_id": user_id,
                "ticket_count": len(ticket_list)
            })
            return {"tickets": ticket_list}
        except Exception as e:
            logger.error("Failed to fetch tickets by user ID", extra={
                "user_id": user_id,
                "error": str(e)
            })
            raise ServiceError("Error fetching tickets by user ID")
    @classmethod
    def create_ticket(cls,
                      user_id: str,
                      title: str,
                      description: str,
                      comment: str | None = None) -> dict:
        """Create a new ticket"""
        logger.debug("Attempting to create ticket", extra={
            "user_id": user_id,
            "title": title
        })
        try:
            comment = comment if comment else "Ticket created"
            current_time = datetime.now(timezone.utc)
            ticket = cls(
                user_id=user_id,
                id=str(uuid.uuid4()),
                title=title,
                description=description,
                status="open",
                created_at=current_time,
                updated_at=current_time,
                comments=[comment]

            )
            ticket.save()
            logger.info("Successfully created ticket", extra={
                "user_id": user_id,
                "ticket_id": ticket.id,
                "status": "open"
            })
            return {"ticket_id": ticket.id}
        except Exception as e:
            logger.error("Failed to create ticket", extra={
                "user_id": user_id,
                "error": str(e)
            })
            raise ServiceError("Error creating ticket")

    @classmethod
    def update_ticket(cls, user_id: str, ticket_id: str,
                      status: TicketStatus | None = None,
                      comment: str | None = None) -> bool:
        """Update a ticket's status and/or comments."""
        if not status and not comment:
            logger.info("No updates provided", extra={"ticket_id": ticket_id})
            return False

        try:
            ticket = cls.get_ticket(ticket_id=ticket_id, user_id=user_id)
            updates = []

            # Status update
            if status and status != ticket.status:
                updates.append(cls.status.set(status))
                logger.debug(f"Status: {ticket.status} → {status}", extra={"ticket_id": ticket_id})

            # Comments update
            if comment:
                current_comments = ticket.comments or []
                current_comments.append(comment)



                updates.append(cls.comments.set(list(current_comments)))
                logger.debug(f"Added a comment", extra={"ticket_id": ticket_id})

            # Apply updates
            if updates:
                updates.append(cls.updated_at.set(datetime.now(timezone.utc)))
                ticket.update(actions=updates)
                logger.info(f"Updated ticket with {len(updates)-1} changes", extra={"ticket_id": ticket_id})
                return True

            return False

        except Exception as e:
            logger.error("Update failed", extra={"ticket_id": ticket_id, "error": str(e)})
            raise ServiceError(f"Failed to update ticket: {str(e)}")





# API Routes
@app.get(
    "/tickets",
    operation_id="getAllTickets",
    description="Retrieves a list of all tickets in the system",
    response_description="A list of tickets",
    responses={
        200: {"description": "List of tickets successfully retrieved"},
        503: {"description": "Service error occurred while fetching tickets"}
    }
)
@tracer.capture_method
def get_tickets() -> dict:
    logger.debug("GET /tickets request received")
    result = TicketModel.get_all_tickets()
    logger.info("GET /tickets request completed successfully", extra={
        "ticket_count": len(result["tickets"])
    })
    return result

@app.get(
    "/tickets/user/<user_id>",
    operation_id="getTicketsByUserId",
    description="Retrieves a list of all tickets for a specific user identified by `user_id`",
    response_description="A list of tickets for the specified user",
    responses={
        200: {"description": "List of user tickets successfully retrieved"},
        404: {"description": "User not found"},
        503: {"description": "Service error occurred while fetching user tickets"}
    }
)
@tracer.capture_method
def get_tickets_by_user_id(
        user_id: Annotated[str, Path(
            description="The unique identifier of the user whose tickets are to be retrieved",
            example="3e222218-ff31-47d1-a06a-616bbe98a402"
        )]
) -> dict:
    logger.debug("GET /tickets/user/{user_id} request received", extra={
        "user_id": user_id
    })
    result = TicketModel.get_ticket_by_user_id(user_id)
    logger.info("GET /tickets/user/{user_id} request completed successfully", extra={
        "user_id": user_id,
        "ticket_count": len(result["tickets"])
    })
    return result

@app.get(
    "/tickets/<ticket_id>",
    operation_id="getTicketById",
    description="Retrieves detailed information about a specific ticket identified by `ticket_id`",
    response_description="Detailed ticket information including title, description, status, and comments",
    responses={
        200: {"description": "Ticket details successfully retrieved"},
        404: {"description": "Ticket not found"},
        503: {"description": "Service error occurred while fetching ticket"}
    }
)
@tracer.capture_method
def get_ticket(
        ticket_id: Annotated[str, Path(
            description="The unique identifier of the ticket to retrieve",
            example="3e222218-ff31-47d1-a06a-616bbe98a402"
        )],

        user_id: Annotated[str, Body(
            description="ID of the user requesting the ticket",
            example="3e222218-ff31-47d1-a06a-616bbe98a402"
        )]
) -> dict:
    logger.debug("GET /tickets/{ticket_id} request received", extra={
        "ticket_id": ticket_id
    })
    result = TicketModel.get_ticket(user_id=user_id, ticket_id=ticket_id)
    logger.info("GET /tickets/{ticket_id} request completed successfully", extra={
        "ticket_id": ticket_id
    })
    return result.to_simple_dict()


@app.post(
    "/tickets",
    operation_id="createTicket",
    description="Creates a new support ticket in the system",
    response_description="The details of the newly created ticket including its ID",
    responses={
        200: {"description": "Ticket successfully created"},
        400: {"description": "Invalid input parameters"},
        503: {"description": "Service error occurred while creating ticket"}
    }
)
@tracer.capture_method
def create_ticket(
        title: Annotated[str, Body(
            description="The title of the ticket",
            example="Login Issue"
        )],
        description: Annotated[str, Body(
            description="Detailed description of the ticket",
            example="Unable to login to the application after password reset"
        )],
        user_id: Annotated[str, Body(
            description="ID of the user creating the ticket",
            example="3e222218-ff31-47d1-a06a-616bbe98a402"
        )],
        comment: Annotated[str | None, Body(
            description="Initial comments on the ticket",
            example="First attempt to login failed"
        )] = None
) -> dict:
    logger.debug("POST /tickets request received", extra={
        "user_id": user_id,
        "title": title,
        "has_comments": comment is not None
    })
    result = TicketModel.create_ticket(
        user_id=user_id,
        title=title,
        description=description,
        comment=comment
    )
    logger.info("POST /tickets request completed successfully", extra={
        "user_id": user_id,
        "ticket_id": result.get("id")
    })
    return result

@app.put(
    "/tickets/<ticket_id>",
    operation_id="updateTicket",
    description="Updates an existing ticket's status and/or adds new comments identified by `ticket_id`",
    response_description="Boolean indicating whether the update was successful",
    responses={
        200: {"description": "Ticket successfully updated"},
        404: {"description": "Ticket not found"},
        400: {"description": "Invalid input parameters"},
        503: {"description": "Service error occurred while updating ticket"}
    }
)
@tracer.capture_method
def update_ticket(
        ticket_id: Annotated[str, Path(
            description="The unique identifier of the ticket to update",
            example="3e222218-ff31-47d1-a06a-616bbe98a402"
        )],
        user_id: Annotated[str, Body(
            description="ID of the user updating the ticket",
            example="3e222218-ff31-47d1-a06a-616bbe98a402"
        )],
        status: Annotated[TicketStatus | None, Body(
            description="New status for the ticket",
            example=TicketStatus.IN_PROGRESS,
        )] = None,
        comment: Annotated[str | None, Body(
            description="New comment to add to the ticket",
            example="Investigating the login issue",
        )] = None
) -> bool:
    logger.debug("PUT /tickets/{ticket_id} request received", extra={
        "ticket_id": ticket_id,
        "user_id": user_id,
        "status": status,
        "has_comments": comment is not None
    })
    result = TicketModel.update_ticket(
        user_id=user_id,
        ticket_id=ticket_id,
        status=status,
        comment=comment
    )
    logger.info("PUT /tickets/{ticket_id} request completed successfully", extra={
        "ticket_id": ticket_id,
        "user_id": user_id,
        "success": result
    })
    return result


@logger.inject_lambda_context()
@tracer.capture_lambda_handler
def handler(event: dict, context: LambdaContext) -> dict:
    logger.debug("Lambda handler invoked", extra={"event": event})
    response = app.resolve(event, context)
    logger.debug("Lambda handler completed", extra={"response": response})
    return response

if __name__ == "__main__":
    print(app.get_openapi_json_schema())
