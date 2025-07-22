import json
import os
import psycopg2 # type: ignore
import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger(service="DBConnection")
tracer = Tracer(service="DBConnection")

# --- Database Configuration pulled from environment variables ---
DB_HOST        = os.environ.get('DB_HOST')
DB_PORT        = os.environ.get('DB_PORT', '5432')
DB_NAME        = os.environ.get('DB_NAME')
DB_USER        = os.environ.get('DB_USER')
DB_SECRET_NAME = os.environ.get('DB_SECRET_NAME')  # AWS Secrets Manager secret ID

# Clients and caches (module‐level)
secrets_manager_client = boto3.client('secretsmanager')
_db_password_cache     = None
_db_connection_cache   = None

@tracer.capture_method
def get_db_password():
    global _db_password_cache
    if _db_password_cache:
        return _db_password_cache

    if not DB_SECRET_NAME:
        logger.error("DB_SECRET_NAME missing in environment.")
        raise ValueError("DB_SECRET_NAME env var not set for DB password.")

    try:
        logger.debug(f"Retrieving DB password from Secrets Manager: {DB_SECRET_NAME}")
        secret_response = secrets_manager_client.get_secret_value(SecretId=DB_SECRET_NAME)
        secret_string   = secret_response.get('SecretString')
        if not secret_string:
            raise ValueError("Empty SecretString from Secrets Manager.")

        parsed = json.loads(secret_string)
        pwd    = parsed.get('password')
        if not pwd:
            raise ValueError("Key 'password' not found in secret JSON.")
        _db_password_cache = pwd
        return _db_password_cache

    except Exception as e:
        logger.exception("Failed to fetch DB password.")
        raise Exception(f"DatabaseConnectionError: Could not fetch password – {str(e)}")


@tracer.capture_method
def get_aurora_connection():
    """
    Return a cached psycopg2 connection if it’s still healthy;
    otherwise, open a new one and cache it. Raises on failure.
    """
    global _db_connection_cache

    if _db_connection_cache:
        try:
            if _db_connection_cache.closed == 0:
                with _db_connection_cache.cursor() as cur:
                    cur.execute("SELECT 1")
                logger.debug("Reusing existing healthy DB connection.")
                return _db_connection_cache
            else:
                logger.info("Cached DB connection was closed. Re‐establishing.")
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"Cached DB connection is unhealthy ({str(e)}). Re‐establishing.")
            _db_connection_cache = None  # Discard stale connection

    # Ensure all required env vars are present
    if not all([DB_HOST, DB_NAME, DB_USER]):
        logger.error("Missing one or more DB connection parameters.")
        raise ValueError("Database connection parameters (DB_HOST/DB_NAME/DB_USER) missing.")

    password = get_db_password()  # May raise

    logger.info(f"Opening new DB connection to {DB_HOST}:{DB_PORT}/{DB_NAME} as {DB_USER}.")
    try:
        conn = psycopg2.connect(
            host         = DB_HOST,
            port         = DB_PORT,
            dbname       = DB_NAME,
            user         = DB_USER,
            password     = password,
            connect_timeout = 15
        )
        _db_connection_cache = conn
        logger.info("New DB connection established.")
        return conn
    except psycopg2.Error as e:
        logger.exception("Database connection failed.")
        raise Exception(f"DatabaseConnectionError: {str(e)}")
