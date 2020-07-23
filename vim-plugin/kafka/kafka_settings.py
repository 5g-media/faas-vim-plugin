import os

KAFKA_SERVER = "{}:{}".format(os.environ.get("KAFKA_HOST", "192.158.1.175"),
                              os.environ.get("KAFKA_PORT", "9092"))
KAFKA_CONFIGURATION_TOPIC = 'ns.instances.conf'
KAFKA_CLIENT_ID = 'faas_vim_conf'
KAFKA_API_VERSION = (1, 1, 0)
KAFKA_GROUP_ID = 'FAAS_CONFIGURATION_CG'
