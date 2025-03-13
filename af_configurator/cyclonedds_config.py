import xmlschema
import xmltodict
from .openpyxl_patch import *
from .utils import *


schema = xmlschema.XMLSchema(os.path.join(
    get_resource_path(), 'cyclonedds/cyclonedds.xsd'))


class Domain:
    def __init__(self, id, tag):
        self.id = id
        self.tag = tag

    def get_config(self):
        return {
            '//CycloneDDS/Domain/@Id': self.id,
            '//CycloneDDS/Domain/Discovery/Tag': self.tag}


class SpdpConfig:
    def __init__(self, resend_period, lease_duration, expects_inline_qos):
        self.spdp_resend_period = str(resend_period) + 's'
        self.spdp_lease_duration = str(lease_duration) + 's'
        self.spdp_expects_inline_QoS = expects_inline_qos

    def get_config(self):
        return {
            '//CycloneDDS/Domain/Discovery/SPDPInterval': self.spdp_resend_period,
            '//CycloneDDS/Domain/Discovery/LeaseDuration': self.spdp_lease_duration,
            '//CycloneDDS/Domain/Compatibility/ExplicitlyPublishQosSetToDefault': self.spdp_expects_inline_QoS}


class SedpConfig:
    def __init__(self, heartbeat_period, nack_response_delay):
        self.heartbeat_period = str(heartbeat_period) + 's'
        self.nack_response_delay = str(nack_response_delay) + 's'

    def get_config(self):
        return {
            '//CycloneDDS/Domain/Internal/HeartbeatInterval': self.heartbeat_period,
            '//CycloneDDS/Domain/Internal/NackDelay': self.nack_response_delay}


class ParticipantConfig:
    def __init__(self, name, id, domain, user_traffic_unicast_address):
        self.name = name
        self.id = id
        self.domain = domain
        self.user_traffic_unicast_address = user_traffic_unicast_address
        self.spdp_config = None
        self.sedp_config = None

    def get_config(self):
        config = {'//CycloneDDS/Domain/Discovery/ParticipantIndex': self.id,
                  '//CycloneDDS/Domain/Discovery/Peers/Peer/@Address': self.user_traffic_unicast_address}
        for sub_config in (self.domain, self.spdp_config, self.sedp_config):
            if sub_config:
                config.update(sub_config.get_config())

        return config


class CycloneddsConfig:
    def __init__(self, wb):
        self.ws_locator_config = wb['Unicast&MulticastLocator Config']
        self.ws_spdp_config = wb['SPDP Config']
        self.participant_config_dic = {}
        self.parse()

    def parse(self):
        for row in list(self.ws_locator_config.rows)[2:]:
            participant_name = row[3].value
            if participant_name != None:
                self.participant_config_dic[participant_name] = ParticipantConfig(participant_name,
                                                                                  row[4].value,
                                                                                  Domain(
                                                                                      row[6].value, row[5].value),
                                                                                  row[12].value)
        for row in list(self.ws_spdp_config.rows)[1:]:
            participant_name = row[0].value
            if participant_name not in self.participant_config_dic:
                raise Exception(
                    'error! {} not found in Unicast&MulticastLocator Config sheet'.format(participant_name))
            self.participant_config_dic[participant_name].spdp_config = SpdpConfig(
                row[1].value, row[2].value, row[3].value)

    def write_participant_config(self, name, path):
        for participant_name, participant_config in self.participant_config_dic.items():
            if name == participant_name:
                config = participant_config.get_config()
                config_dic = {}
                for key, value in config.items():
                    keys = key[1:].split('/')[1:]
                    cur_config = config_dic
                    for k in keys[:-1]:
                        if k not in cur_config:
                            cur_config[k] = {}
                        cur_config = cur_config[k]
                    cur_config[keys[-1]] = value

                print(config_dic)
                with open(path, 'w') as f:
                    config_dic['CycloneDDS']['@xmlns'] = "https://cdds.io/config"
                    config_dic['CycloneDDS']['@xmlns:xsi'] = "http://www.w3.org/2001/XMLSchema-instance"
                    config_dic['CycloneDDS']['@xsi:schemaLocation'] = "https://cdds.io/config https://raw.githubusercontent.com/eclipse-cyclonedds/cyclonedds/master/etc/cyclonedds.xsd"
                    cyclonedds_config = xmltodict.unparse(
                        config_dic, pretty=True)
                    if schema.is_valid(cyclonedds_config):
                        f.write(xmltodict.unparse(config_dic, pretty=True))
                    else:
                        print(schema.to_dict(cyclonedds_config))
