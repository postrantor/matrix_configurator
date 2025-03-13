from .utils import *
import math


class EcuConfig:
    dic = {}

    def __init__(self):
        self.name = None
        self.apps = {}


class AppConfig:
    def __init__(self):
        self.ecu = None
        self.domain_participants = []


class DomainConfig:
    dic = {}

    def __init__(self):
        self.id = None
        self.tag = None

    def get_config(self):
        return {
            '//CycloneDDS/Domain/@Id': self.id,
            '//CycloneDDS/Domain/Discovery/Tag': self.tag}


class DomainParticipantConfig:
    dic = {}

    def __init__(self):
        self.app = None
        self.domain = None

        self.name = None
        self.publishers = []
        self.subscribers = []
        self.domain_participant_qos = None
        self.guid_prefix = None
        self.participant_id = None

        self.meta_traffic_unicast_address = None
        self.meta_traffic_multicast_address = None
        self.user_traffic_unicast_address = None
        self.user_traffic_multicast_address = None

        self.source_ip = None
        self.source_port = None
        self.deployment_vlan = None

        self.spdp_resend_period = None
        self.spdp_lease_duration = None
        self.spdp_expects_inline_qos = None
        self.user_data = None
        self.entity_factory = None

    def get_config(self):
        config = {'//CycloneDDS/Domain/Discovery/ParticipantIndex': self.participant_id,
                  '//CycloneDDS/Domain/Discovery/Peers/Peer/@Address': self.user_traffic_unicast_address,
                  '//CycloneDDS/Domain/Discovery/SPDPInterval': self.spdp_resend_period,
                  '//CycloneDDS/Domain/Discovery/LeaseDuration': self.spdp_lease_duration,
                  '//CycloneDDS/Domain/Compatibility/ExplicitlyPublishQosSetToDefault': self.spdp_expects_inline_qos}
        return config


class PubSub:
    def __init__(self):
        self.domain_participant = None

        self.name = None
        self.topic = None

        self.sedp_heart_beat_period = None
        self.sedp_nack_response_delay = None


class PublisherConfig(PubSub):
    dic = {}

    def __init__(self):
        self.data_writers = []


class SubscriberConfig(PubSub):
    dic = {}

    def __init__(self):
        self.data_readers = []


class DataReaderWriter:
    def __init__(self):
        self.name = None
        self.topic = None
        self.entity_id = None
        self.qos = None


class DataReaderConfig(DataReaderWriter):
    dic = {}

    def __init__(self):
        self.subscriber = None

    def get_qos_config(self):
        pass


class DataWriterConfig(DataReaderWriter):
    dic = {}

    def __init__(self):
        self.publisher = None


class QosConfig:
    def __init__(self):
        self.durability_kind = None
        self.history_kind = None
        self.history_depth = None
        self.liveliness_kind = None
        self.liveliness_lease_duration = None
        self.reliability_kind = None
        self.deadline = None
        self.lifespan = None
        self.ownership = None
        self.ownership_strength = None

    def get_config(self):
        config = {
            # history: system_default/keep_all/keep_last default: keep_last
            'history': self.history_kind.lower(),

            'depth': int(self.history_depth),

            # reliability: system_default/reliable/best_effort
            'reliability': self.reliability_kind.lower(),

            # durability: system_default/transient_local/volatile
            'durability': self.durability_kind.lower(),

            # liveliness: system_default/automatic/manual_by_topic
            'liveliness': self.liveliness_kind.lower(),

            'ownership': self.ownership.lower()
        }

        if self.deadline and self.deadline != 'infinite':
            config['deadline'] = int(float(self.deadline) * 1000)

        if self.liveliness_lease_duration and self.liveliness_lease_duration != 'infinite':
            config['liveliness_lease_duration'] = int(
                float(self.liveliness_lease_duration) * 1000)

        if self.ownership_strength:
            config['ownership_strength'] = int(self.ownership_strength)

        return config


class TopicConfig:
    dic = {}

    def __init__(self):
        self.name = None
        self.type = None
        self.ros_type = None
        self.topic_kind = None
        self.key_value = None
        self.filter_expression = None


'''
reference: https://cyclonedds.io/docs/cyclonedds/latest/config/config_file_reference.html
'''


class StructTypeField:
    def __init__(self, typename, member_name):
        self.typename = type_name_to_dds_type_name(typename)
        self.ros_typename = type_name_to_ros_type_name(typename)
        self.member_name = member_name.strip()
        self.ros_member_name = camel_to_snake(self.member_name)

    def get_type_size(self):
        if is_base_type(self.typename):
            return get_base_type_size(self.typename)
        else:
            return DataType.dic[self.typename].get_type_size()

    def get_type_alignment(self):
        if is_base_type(self.typename):
            return get_base_type_alignment(self.typename)
        else:
            return DataType.dic[self.typename].get_type_alignment()


class EnumTypeField:
    def __init__(self, member_name, value):
        self.member_name = member_name.strip()
        self.ros_member_name = name_to_ros_constant_name(self.member_name)
        self.value = value


class DataType:
    dic = {}

    def __init__(self, typename):
        self.typename = typename
        self.ros_typename = type_name_to_ros_type_name(typename)

        DataType.dic[typename] = self

    def get_dependent_type(self):
        return []


class StructType(DataType):
    def __init__(self, typename):
        super().__init__(typename)
        self.fields = []

    def add_field(self, typename, member_name):
        self.fields.append(StructTypeField(typename, member_name))

    def get_ros_define(self):
        return '\n'.join(['{} {}'.format(f.ros_typename, f.ros_member_name) for f in self.fields] + [''])

    def get_dependent_type(self):
        res = set(
            [f.typename for f in self.fields if not is_base_type(f.typename)])
        return sorted(res)

    def get_dds_define(self):
        return '\n'.join(
            ["#ifndef {}_IDL".format(self.typename.upper()),
             "#define {}_IDL".format(self.typename.upper()),
             '']
            + ['#include "{}.idl"'.format(f)
               for f in self.get_dependent_type()]
            + ['',
               'struct {} {{'.format(self.typename)]
            + ['  {} {};'.format(f.typename, f.member_name)
               for f in self.fields]
            + ['};',
               '',
               '#endif',
               ''])

    def get_type_size(self):
        size = 0
        cur_alignment = 0
        for f in self.fields:
            member_type_size = f.get_type_size()
            member_type_alignment = f.get_type_alignment()

            size = math.ceil(size / member_type_alignment) * \
                member_type_alignment
            size += member_type_size

            cur_alignment = max(cur_alignment, member_type_alignment)

        size = math.ceil(size / cur_alignment) * cur_alignment
        return size

    def get_type_alignment(self):
        alignment = 0
        for f in self.fields:
            alignment = max(alignment, f.get_type_alignment())

        # for arm64
        alignment = min(alignment, 8)
        return alignment


class TypedefType(DataType):
    def __init__(self, typename, original_type):
        super().__init__(typename)
        self.original_type = original_type
        self.dds_base_type = type_name_to_dds_type_name(original_type)

    def get_ros_define(self):
        return '{} {}\n'.format(self.original_type, 'data')

    def get_dds_define(self):
        return '\n'.join(
            ["#ifndef {}_IDL".format(self.typename.upper()),
             "#define {}_IDL".format(self.typename.upper()),
             '',
             'typedef {} {};'.format(self.dds_base_type, self.typename),
             '',
             '#endif',
             ''])

    def get_dependent_type(self):
        if is_base_type(self.original_type):
            return []
        else:
            return DataType.dic[self.original_type].get_dependent_type()

    def get_type_size(self):
        if is_base_type(self.original_type):
            return get_base_type_size(self.original_type)
        else:
            return DataType.dic[self.original_type].get_type_size()

    def get_type_alignment(self):
        if is_base_type(self.original_type):
            return get_base_type_alignment(self.original_type)
        else:
            return DataType.dic[self.original_type].get_type_alignment()


class ArrayType(DataType):
    def __init__(self, typename, member_typename, bound):
        super().__init__(typename)
        self.member_typename = type_name_to_dds_type_name(member_typename)
        self.ros_member_typename = type_name_to_ros_type_name(member_typename)
        self.bound = bound

    def get_ros_define(self):
        return '{}[{}] {}\n'.format(self.ros_member_typename, self.bound, 'data')

    def get_dependent_type(self):
        if is_base_type(self.member_typename):
            return []
        return [self.member_typename]

    def get_dds_define(self):
        return '\n'.join(
            ["#ifndef {}_IDL".format(self.typename.upper()),
             "#define {}_IDL".format(self.typename.upper()),
             '']
            + ['#include "{}.idl"'.format(f)
               for f in self.get_dependent_type()]
            + ['']
            + ['typedef {} {}[{}];'.format(self.member_typename, self.typename, self.bound)]
            + ['',
               '#endif',
               ''])

    def get_type_size(self):
        type_size = get_base_type_size(self.member_typename) if is_base_type(
            self.member_typename) else DataType.dic[self.member_typename].get_type_size()
        return type_size * self.bound

    def get_type_alignment(self):
        if is_base_type(self.member_typename):
            return get_base_type_alignment(self.member_typename)
        else:
            return DataType.dic[self.member_typename].get_type_alignment()


class EnumType(DataType):
    def __init__(self, typename, bit_bound):
        super().__init__(typename)
        self.member_type = None
        if bit_bound <= 8:
            self.member_type = 'uint8'
        elif bit_bound <= 16:
            self.member_type = 'uint16'
        elif bit_bound <= 32:
            self.member_type = 'uint32'
        else:
            raise Exception('{} enum bitbound > 32!'.format(self.typename))
        self.fields = []
        self.bit_bound = bit_bound

    def add_field(self, member_name, value):
        if value >= pow(2, self.bit_bound):
            raise Exception('error! enum value {}: {} > 2^{}'.format(
                self.typename, value, self.bit_bound))
        self.fields.append(EnumTypeField(member_name, value))

    def get_ros_define(self):
        return '\n'.join(['{} {}'.format(self.member_type, 'data')]
                         + ['']
                         + ['{} {}={}'.format(self.member_type, f.ros_member_name, f.value) for f in self.fields]
                         + [''])

    def get_dds_define(self):
        return '\n'.join(
            ["#ifndef {}_IDL".format(self.typename.upper()),
             "#define {}_IDL".format(self.typename.upper()),
             '']
            + ['@bit_bound({})'.format(self.bit_bound)]
            + ['enum {} {{'.format(self.typename)]
            # TODO: name conflict, temp solution: add self.typename to avoid it
            + [',\n\n'.join(['  @value({})\n  {}_{}'.format(f.value,
                                                            self.typename, f.member_name) for f in self.fields])]
            + ['};',
               '',
               '#endif',
               ''])

    def get_type_size(self):
        return get_base_type_size(self.member_type)

    def get_type_alignment(self):
        return get_base_type_alignment(self.member_type)


# TODO, unfinish, currently not use
class SequenceType(DataType):
    def __init__(self, typename, member_typename, bound=None):
        super().__init__(typename)
        self.member_typename = type_name_to_dds_type_name(member_typename)
        self.ros_member_typename = type_name_to_ros_type_name(member_typename)
        self.bound = bound

    def get_ros_define(self):
        if self.bound:
            return '{}[<{}] {}\n'.format(self.ros_member_typename, self.bound, 'data')
        else:
            return '{}[] {}\n'.format(self.ros_member_typename, 'data')

    def get_dependent_type(self):
        if is_base_type(self.member_typename):
            return []
        return [self.member_typename]


# TODO, unfinish, currently not use
class String8Type(DataType):
    def __init__(self, typename, bound=None):
        super().__init__(typename)
        self.bound = bound

    def get_ros_define(self):
        if self.bound:
            return 'string<={} data\n'.format(self.bound)
        else:
            return 'string data\n'

    def get_dds_define(self):
        return '\n'.join(
            ["#ifndef {}_IDL".format(self.typename.upper()),
             "#define {}_IDL".format(self.typename.upper()),
             '']
            + ['#include "{}.idl"'.format(f)
               for f in self.get_dependent_type()]
            + ['']
            + ['typedef {} {}[{}];'.format("char", self.typename, 8)]
            + ['',
               '#endif',
               ''])
