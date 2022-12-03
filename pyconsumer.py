import logging
import os

from dotenv import load_dotenv

from confluent_kafka import DeserializingConsumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import StringDeserializer


import schemas
from models import Person

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

load_dotenv(verbose=True)


def make_consumer() -> DeserializingConsumer:
    # create a SchemaRegistryClient
    schema_reg_client = SchemaRegistryClient({'url': os.environ['SCHEMA_REGISTRY_URL']})

    # create a AvroDeserializer
    avro_deserializer = AvroDeserializer(schema_reg_client,
                                        schemas.person_value_v2,
                                        lambda data, ctx: Person(**data))

    # create and return DeserializingConsumer
    return DeserializingConsumer({'bootstrap.servers': os.environ['BOOTSTRAP_SERVERS'],
                                'key.deserializer': StringDeserializer('utf_8'),
                                'value.deserializer': avro_deserializer,
                                'group.id': os.environ['CONSUMER_GROUP'],
                                'enable.auto.commit': 'false'})

def main():
    logger.info(f"""
        Started Python Avro Consumer
        for topic {os.environ['TOPICS_PEOPLE_AVRO_NAME']}
    """)

    consumer = make_consumer()
    consumer.subscribe([os.environ['TOPICS_PEOPLE_AVRO_NAME']])

    while True:
        msg = consumer.poll(1.0)
        if msg is not None:
            person = msg.value()
            logger.info(f"Consumed person {person}")
            consumer.commit(message=msg)


if __name__ == "__main__":
    main()