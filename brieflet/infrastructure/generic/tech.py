"""Known infrastructure: Docker image names and client libraries → (tech, kind, diagram shape). Data only."""
from __future__ import annotations

import re

# tech → (kind, shape); kind decides the Infrastructure subgraph and the default arrow label
INFRA = {
    "Redis": ("cache", "db"), "Valkey": ("cache", "db"), "Memcached": ("cache", "db"),
    "PostgreSQL": ("database", "db"), "MySQL": ("database", "db"), "MariaDB": ("database", "db"),
    "SQL Server": ("database", "db"), "MongoDB": ("database", "db"), "Elasticsearch": ("database", "db"),
    "OpenSearch": ("database", "db"), "ClickHouse": ("database", "db"), "Cassandra": ("database", "db"),
    "SQLite": ("database", "db"), "Qdrant": ("database", "db"),
    "RabbitMQ": ("queue", "queue"), "Kafka": ("queue", "queue"), "NATS": ("queue", "queue"),
    "Azure Service Bus": ("queue", "queue"), "AWS SQS": ("queue", "queue"),
    "Nginx": ("proxy", "hex"), "Traefik": ("proxy", "hex"), "Envoy": ("proxy", "hex"), "Caddy": ("proxy", "hex"),
    "Keycloak": ("auth", "box"), "MinIO": ("container", "box"),
}

# Docker image (last path part, no tag) → tech
IMAGES = {
    "redis": "Redis", "valkey": "Valkey", "memcached": "Memcached", "postgres": "PostgreSQL", "postgis": "PostgreSQL",
    "mysql": "MySQL", "mariadb": "MariaDB", "mssql-server": "SQL Server", "azure-sql-edge": "SQL Server", "mongo": "MongoDB", "mongodb": "MongoDB",
    "elasticsearch": "Elasticsearch", "opensearch": "OpenSearch", "clickhouse-server": "ClickHouse",
    "cassandra": "Cassandra", "qdrant": "Qdrant", "rabbitmq": "RabbitMQ", "kafka": "Kafka", "cp-kafka": "Kafka",
    "redpanda": "Kafka", "nats": "NATS", "nginx": "Nginx", "traefik": "Traefik", "envoy": "Envoy", "caddy": "Caddy",
    "keycloak": "Keycloak", "minio": "MinIO",
}

# client library (npm / PyPI / Go / Cargo / Maven / NuGet name, lower case) → tech
CLIENTS = {
    "redis": "Redis", "ioredis": "Redis", "aioredis": "Redis", "go-redis": "Redis", "stackexchange.redis": "Redis",
    "spring-boot-starter-data-redis": "Redis", "bullmq": "Redis", "bull": "Redis",
    "pg": "PostgreSQL", "postgres": "PostgreSQL", "psycopg": "PostgreSQL", "psycopg2": "PostgreSQL",
    "psycopg2-binary": "PostgreSQL", "asyncpg": "PostgreSQL", "pgx": "PostgreSQL", "npgsql": "PostgreSQL",
    "tokio-postgres": "PostgreSQL", "postgresql": "PostgreSQL", "npgsql.entityframeworkcore.postgresql": "PostgreSQL",
    "microsoft.entityframeworkcore.sqlserver": "SQL Server", "microsoft.data.sqlclient": "SQL Server",
    "mssql": "SQL Server", "pyodbc": "SQL Server", "pomelo.entityframeworkcore.mysql": "MySQL",
    "mysql": "MySQL", "mysql2": "MySQL", "pymysql": "MySQL", "mysqlclient": "MySQL", "mysql-connector-j": "MySQL",
    "mongodb": "MongoDB", "mongoose": "MongoDB", "pymongo": "MongoDB", "motor": "MongoDB", "mongo-driver": "MongoDB",
    "@elastic/elasticsearch": "Elasticsearch", "elasticsearch": "Elasticsearch",
    "better-sqlite3": "SQLite", "sqlite3": "SQLite", "rusqlite": "SQLite", "qdrant-client": "Qdrant",
    "amqplib": "RabbitMQ", "amqp-connection-manager": "RabbitMQ", "pika": "RabbitMQ", "aio-pika": "RabbitMQ",
    "spring-boot-starter-amqp": "RabbitMQ", "rabbitmq.client": "RabbitMQ", "lapin": "RabbitMQ",
    "kafkajs": "Kafka", "confluent-kafka": "Kafka", "aiokafka": "Kafka", "kafka-python": "Kafka", "sarama": "Kafka",
    "kafka-go": "Kafka", "rdkafka": "Kafka", "spring-kafka": "Kafka", "confluent.kafka": "Kafka",
    "nats": "NATS", "nats-py": "NATS", "nats.go": "NATS", "async-nats": "NATS",
    "@azure/service-bus": "Azure Service Bus", "azure-servicebus": "Azure Service Bus",
    "@aws-sdk/client-sqs": "AWS SQS",
}


def image_tech(image: str) -> str | None:
    """'docker.io/library/postgres:16-alpine' → 'PostgreSQL'."""
    name = image.split("@")[0].rsplit("/", 1)[-1].split(":")[0].lower()
    return IMAGES.get(name) or next((t for k, t in IMAGES.items() if re.fullmatch(rf"{k}(-\w+)?", name)), None)


def client_tech(dep: str) -> str | None:
    d = dep.lower()
    if d.startswith(("github.com/", "go.", "gopkg.in/")):   # Go module path: github.com/redis/go-redis/v9
        parts = [x for x in d.split("/") if not re.fullmatch(r"v\d+", x)]
        d = parts[-1]
    return CLIENTS.get(d)
