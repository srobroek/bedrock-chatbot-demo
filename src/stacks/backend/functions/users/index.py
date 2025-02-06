import os
import uuid
from time import time

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import BedrockAgentResolver
from aws_lambda_powertools.event_handler.exceptions import NotFoundError, ServiceError
from aws_lambda_powertools.event_handler.openapi.params import Path, Body
from aws_lambda_powertools.utilities.typing import LambdaContext
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute
from typing_extensions import Annotated

# Configuration
CONFIG = {
    "table_name": os.environ.get("TABLE_NAME", "placeholder"),
    "region": os.environ.get("AWS_REGION", "us-east-1")
}

# Initialize services
logger = Logger(service="user-service")
tracer = Tracer()
app = BedrockAgentResolver()

class UserModel(Model):
    """DynamoDB model for users with integrated user operations"""
    class Meta:
        table_name = CONFIG["table_name"]
        region = CONFIG["region"]

    id = UnicodeAttribute(hash_key=True)
    first_name = UnicodeAttribute()
    last_name = UnicodeAttribute()
    email = UnicodeAttribute()

    @classmethod
    def get_user(cls, user_id: str):
        """Get a specific user with error handling"""
        logger.debug("Attempting to retrieve user", extra={
            "user_id": user_id
        })
        try:
            user = cls.get(hash_key=user_id)
            logger.info("Successfully retrieved user", extra={
                "user_id": user_id,
                "email": user.email
            })
            return user
        except cls.DoesNotExist:
            logger.warning("User not found", extra={
                "user_id": user_id
            })
            raise NotFoundError(f"User with ID {user_id} not found")
        except Exception as e:
            logger.error("Error retrieving user", extra={
                "user_id": user_id,
                "error": str(e)
            })
            raise ServiceError("Error retrieving user")

    @classmethod
    def get_all_users(cls) -> dict:
        """Get all user IDs"""
        logger.debug("Attempting to fetch all users")
        try:
            users = cls.scan(
                attributes_to_get=['id'],
                page_size=100  # Optimize DynamoDB read capacity
            )
            user_list = [dict(user.attribute_values) for user in users]
            logger.info("Successfully retrieved all users", extra={
                "user_count": len(user_list)
            })
            return {"users": user_list}
        except Exception as e:
            logger.error("Error fetching users", extra={
                "error": str(e)
            })
            raise ServiceError("Error fetching users")

    @classmethod
    def create_user(cls, first_name: str, last_name: str, email: str) -> dict:
        """Create a new user"""
        logger.debug("Attempting to create user", extra={
            "email": email,
            "first_name": first_name,
            "last_name": last_name
        })
        try:
            user_id = str(uuid.uuid4())
            user = cls(
                id=user_id,
                first_name=first_name,
                last_name=last_name,
                email=email
            )
            user.save()
            logger.info("Successfully created user", extra={
                "user_id": user_id,
                "email": email
            })
            return {"user_id": user.id}
        except Exception as e:
            logger.error("Error creating user", extra={
                "email": email,
                "error": str(e)
            })
            raise ServiceError("Error creating user")

@app.get(
    "/users",
    operation_id="getAllUsers",
    description="Retrieves a list of all users in the system",
    response_description="A list of user IDs",
    responses={
        200: {"description": "List of users successfully retrieved"},
        503: {"description": "Service error occurred while fetching users"}
    }
)
@tracer.capture_method
def get_users() -> dict:
    logger.debug("GET /users request received")
    result = UserModel.get_all_users()
    logger.info("GET /users request completed successfully", extra={
        "user_count": len(result["users"])
    })
    return result


@app.get(
    "/users/<user_id>",
    operation_id="getUserById",
    description="Retrieves detailed information about a specific user identified by `user_id`",
    response_description="Detailed user information including first name, last name, and email",
    responses={
        200: {"description": "User details successfully retrieved"},
        404: {"description": "User not found"},
        503: {"description": "Service error occurred while fetching user"}
    }
)
@tracer.capture_method
def get_user(
        user_id: Annotated[str, Path(
            description="The unique identifier of the user to retrieve",
            example="3e222218-ff31-47d1-a06a-616bbe98a402'"
        )]
) -> dict:
    logger.debug("GET /users/{user_id} request received", extra={
        "user_id": user_id
    })
    result = UserModel.get_user(user_id)
    logger.info("GET /users/{user_id} request completed successfully", extra={
        "user_id": user_id
    })
    return result.to_simple_dict()

@app.post(
    "/users",
    operation_id="createUser",
    description="Creates a new user in the system",
    response_description="The ID of the newly created user",
    responses={
        200: {"description": "User successfully created"},
        400: {"description": "Invalid input parameters"},
        503: {"description": "Service error occurred while creating user"}
    }
)
@tracer.capture_method
def create_user(
        first_name: Annotated[str, Body(
            description="The user's first name",
            example="John"
        )],
        last_name: Annotated[str, Body(
            description="The user's last name",
            example="Doe"
        )],
        email: Annotated[str, Body(
            description="The user's email address",
            example="john.doe@example.com"
        )]
) -> dict:
    logger.debug("POST /users request received", extra={
        "email": email,
        "first_name": first_name,
        "last_name": last_name
    })
    result = UserModel.create_user(
        first_name=first_name,
        last_name=last_name,
        email=email
    )
    logger.info("POST /users request completed successfully", extra={
        "user_id": result.get("user_id"),
        "email": email
    })
    return result

@app.get("/current_time", description="Gets the current time in seconds")


@tracer.capture_method
def current_time() -> int:
    return int(time())

@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)

# Generate openAPI schema if called interactively
if __name__ == "__main__":
    print(app.get_openapi_json_schema())
