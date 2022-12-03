import logging
import os
from typing import List

from dotenv import load_dotenv


from confluent_kafka import SerializingProducer
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka.serialization import StringSerializer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

from commands import CreatePeopleCommand
from models import Person
import schemas
from faker import Faker

from fastapi import FastAPI

load_dotenv(verbose=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()



app = FastAPI()

@app.on_event('startup')
async def startup_event():
    client = AdminClient({'bootstrap.servers': os.environ['BOOTSTRAP_SERVERS']})
    topic = NewTopic(os.environ['TOPICS_PEOPLE_AVRO_NAME'],
                num_partitions=int(os.environ['TOPICS_PEOPLE_AVRO_PARTITIONS']),
                replication_factor=int(os.environ['TOPICS_PEOPLE_AVRO_REPLICAS']))

    try:
        futures = client.create_topics([topic])
        for topic_name, future in futures.items():
            future.result()
            logger.info(f"Create topic {topic_name}")
    except Exception as e:
        logger.warning(e)


def make_producer() -> SerializingProducer:

    schema_reg_client = SchemaRegistryClient({'url': os.environ['SCHEMA_REGISTRY_URL']})

    avro_serializer = AvroSerializer(schema_reg_client,
                                    schemas.person_value_v2,
                                    lambda person, ctx: person.dict())

    return SerializingProducer({'bootstrap.servers': os.environ['BOOTSTRAP_SERVERS'],
                            'linger.ms': 300,
                            'enable.idempotence': 'true',
                            'max.in.flight.requests.per.connection': 1,
                            'acks': 'all',
                            'key.serializer': StringSerializer('utf_8'),
                            'value.serializer': avro_serializer,
                            'partitioner': 'murmur2_random'})

class ProducerCallback:
    def __init__(self, person):
        self.person = person
    def __call__(self, err, msg):
        if err:
            logger.error(f"Failed to produce {self.person}", exc_info=err)
        else:
            logger.info(f"""
                Successfully produced {self.person}
                to partition {msg.partition()}
                at offset {msg.offset()}
            """)



@app.post('/api/people', status_code=201, response_model=List[Person])  
async def create_people(cmd: CreatePeopleCommand):
    people: List[Person] = []
    faker = Faker()
    producer = make_producer()

    for _ in range(cmd.count):
        person = Person(first_name=faker.first_name(),last_name=faker.last_name(), title=faker.job().title())
        people.append(person)
        producer.produce(topic=os.environ['TOPICS_PEOPLE_AVRO_NAME'],
                        key=person.title.lower().replace(r's+', '-'),
                        value=person,
                        on_delivery=ProducerCallback(person))
        
    producer.flush()

    return people