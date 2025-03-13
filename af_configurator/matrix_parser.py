from .openpyxl_patch import *
from .dds_entity_config import *
from .utils import *
import xml.etree.ElementTree as ET


class MatrixParser:
    """
    This class will parse the input dds matrix and stored the information in
    `self.ecu_configs` and `self.msg_configs`
    """

    def create(input_file):
        if input_file.split('.')[-1] == 'xml':
            return XmlParser(input_file)
        else:
            return ExcelParser(input_file)

    def __init__(self):
        self.ecu_configs = []
        self.msg_configs = {}

        # topic pub/sub by 397
        self.topic_of_397 = {}

        # msg types directly used by pub/sub
        self.top_required_types = None

        # all types
        self.required_types = None

        # type object
        self.required_type_objects = None

        # sub_topics_of_397
        self.sub_topics_of_397 = []

    def post_parse(self):
        self.check_397_topic()
        self.parse_top_required_types()
        self.parse_full_required_types()
        self.generate_iox_roudi_config()

    def check_397_topic(self):
        topic_pub_by_397 = []
        topic_sub_by_397 = []
        for ecu in self.ecu_configs:
            if '397' not in ecu.name:
                continue
            for app in ecu.apps.values():
                topic_pub_by_397 += [
                    dw.topic.name for dp in app.domain_participants for pub in dp.publishers for dw in pub.data_writers]
                topic_sub_by_397 += [
                    dr.topic.name for dp in app.domain_participants for sub in dp.subscribers for dr in sub.data_readers]

        for ecu in self.ecu_configs:
            if '397' in ecu.name:
                continue
            for app in ecu.apps.values():
                for dp in app.domain_participants:
                    for pub in dp.publishers:
                        for dw in pub.data_writers:
                            if dw.topic.name in topic_pub_by_397:
                                raise Exception(
                                    'error! dw duplicated: {}'.format(dw.topic.name))
                    for sub in dp.subscribers:
                        for dr in sub.data_readers:
                            if dr.topic.name in topic_sub_by_397:
                                raise Exception(
                                    'error! dr duplicated: {}'.format(dr.topic.name))
        self.topic_of_397 = {
            'pub': topic_pub_by_397,
            'sub': topic_sub_by_397
        }

    # TODO remove hardcode interfaces name
    def get_interface_of_sub_topic(self, topic):
        return 'agv_interfaces' if topic in self.topic_of_397['pub'] else 'agv_interfaces'

    def get_interface_of_pub_topic(self, topic):
        return 'agv_interfaces' if topic in self.topic_of_397['sub'] else 'agv_interfaces'

    def check_sub_topic_is_with_397(self, topic):
        if topic in self.topic_of_397['pub']:
            return True
        else:
            return False

    def check_pub_topic_is_with_397(self, topic):
        if topic in self.topic_of_397['sub']:
            return True
        else:
            return False

    def parse_top_required_types(self):
        required_types = set()
        for ecu in self.ecu_configs:
            print('[Info] parse_top_required_types::ecu.name: {}'.format(ecu.name))
            if 'TC397' in ecu.name:
                continue
            for app in ecu.apps.values():
                for dp in app.domain_participants:
                    for pub in dp.publishers:
                        for dw in pub.data_writers:
                            # print('[Info] dw.topic.type: {}'.format(dw.topic.type))
                            required_types.add(dw.topic.type)
                    for sub in dp.subscribers:
                        for dr in sub.data_readers:
                            required_types.add(dr.topic.type)
        self.top_required_types = required_types

    def parse_full_required_types(self):
        full_required_types = set()

        temp_types = self.top_required_types
        while len(temp_types) != 0:
            full_required_types |= set(
                [message_type for message_type in temp_types if not is_base_type(message_type)])
            temp_next_level_types = set(
                [datatype
                 for message_type in temp_types if not is_base_type(message_type)
                 for datatype in self.msg_configs[message_type].get_dependent_type()])
            temp_types = temp_next_level_types

        self.required_types = full_required_types
        temp_required_type_objects = set()
        for required_type in self.required_types:
            temp_required_type_objects.add(self.msg_configs[required_type])
        self.required_type_objects = temp_required_type_objects

    def generate_iox_roudi_config(self):
        for ecu in self.ecu_configs:
            if 'TDA4' not in ecu.name:
                continue
            topic_to_pubs = {}
            topic_to_subs = {}
            for app in ecu.apps.values():
                for dp in app.domain_participants:
                    for pub in dp.publishers:
                        for dw in pub.data_writers:
                            if dw.topic.ros_type not in topic_to_pubs:
                                topic_to_pubs[dw.topic.name] = []
                            topic_to_pubs[dw.topic.name].append(dw.name)
                    for sub in dp.subscribers:
                        for dr in sub.data_readers:
                            if dr.topic.name not in topic_to_subs:
                                topic_to_subs[dr.topic.name] = []
                            topic_to_subs[dr.topic.name].append(dr.name)
            for topic in topic_to_pubs:
                if topic in topic_to_subs:
                    pass
                    # print("shared memory: ecu: {}, topic: {}".format(
                    #     ecu.name, topic), topic_to_pubs[topic], topic_to_subs[topic])
                    # print('topic {}, datatype: {}, sizeof: {}'.format(
                    # topic, TopicConfig.dic[topic].type, DataType.dic[TopicConfig.dic[topic].type].get_type_size()))

    def get_type_size(self, typename):
        return self.msg_configs[typename].get_type_size()


class ExcelParser(MatrixParser):
    def __init__(self, input_file):
        super().__init__()
        self.wb = openpyxl.load_workbook(
            input_file, read_only=True, data_only=True)
        self.parse()
        self.post_parse()

    def parse(self):
        """
        read every excel sheet and parse dds config
        the result will be stored in `self.ecu_configs` and `self.msg_configs`
        """
        data_type_library_ws = self.wb['DDSDatatypeLibrary']
        locator_config_ws = self.wb['LocatorConfig']
        spdp_config_ws = self.wb['SPDPConfig']
        publisher_config_ws = self.wb['PublisherConfig']
        subscriber_config = self.wb['SubscriberConfig']

        # TODO, hardcode start row index
        self.parse_data_type_library(data_type_library_ws, 2)
        self.parse_locator_config(locator_config_ws, 2)
        # self.parse_spdp_config(spdp_config_ws, 2)
        self.parse_publisher_config(publisher_config_ws, 4)
        self.parse_subscriber_config(subscriber_config, 4)
        self.parse_topic_definition(data_type_library_ws, 2)

    def parse_data_type_library(self, ws, start_row_index):
        base_type = {
            'Boolean': 'bool',
            'BOOLEAN': 'bool',
            'Bool': 'bool',
            'Byte': 'byte',
            'Uint8': 'uint8',
            'UInt8': 'uint8',
            'Uint16': 'uint16',
            'UInt16': 'uint16',
            'Uint32': 'uint32',
            'UInt32': 'uint32',
            'Uint64': 'uint64',
            'UInt64': 'uint64',
            'Int8': 'int8',
            'Int16': 'int16',
            'Int32': 'int32',
            'Int64': 'int64',
            'Float32': 'float32',
            'FLOAT32': 'float32',
            'Float64': 'float64',
            'FLOAT64': 'float64',
            'UTF8': 'char',
            'Char8': 'char',
            'String8': 'string',
            'String16': 'string',
        }

        # state = ['idle', 'structure', 'enumeration']
        cur_state = 'idle'
        cur_datatype = None

        start_row_index = 2
        max_row_index = ws.max_row

        for cur_row_index, cur_row in enumerate(ws.iter_rows(min_row=start_row_index)):
            row_values = [cell.value for cell in cur_row]

            # 确保数据列数刚好是22，若多出数据则忽略
            if len(row_values) > 22:
                row_values = row_values[:22]

            TopicName, TypeName, DatatypeDescription, DataType, Annotation_Default_Value, Bound, EnumBitBound, EnumValue, EnumObjectName, MemberIndex, MemberID, UnionCaseValue, MemberName, MemberDescription, DatatypeReference, UnionDiscriminatorTypeRef, MapKeyType, MustUnderstand, Optional, WhetherKey, ExtensibilityKind, Unit = row_values

            # there are some meaningless blanking rows in dds matrix excel, just skip it
            if TypeName is None and MemberName is None and EnumValue is None:
                print('[Debug] skip blanking row, TypeName: {}'.format(TypeName))
                continue

            print('[Debug] check TypeName: {}'.format(TypeName))

            DatatypeReference = base_type[DatatypeReference] \
                if DatatypeReference in base_type.keys() else DatatypeReference

            if cur_state == 'structure':
                member_name = MemberName
                if member_name is None or TypeName is not None:
                    cur_state = 'idle'
                    self.msg_configs[cur_datatype.typename] = cur_datatype
                    cur_datatype = None
                else:
                    cur_datatype.add_field(DatatypeReference, member_name)

            elif cur_state == 'enumeration':
                enum_name = EnumObjectName
                if enum_name is None or TypeName is not None:
                    cur_state = 'idle'
                    self.msg_configs[cur_datatype.typename] = cur_datatype
                    cur_datatype = None
                else:
                    enum_value = int(EnumValue)
                    cur_datatype.add_field(enum_name, enum_value)

            if cur_state == 'idle':
                if DataType in base_type.keys():
                    self.msg_configs[TypeName] = TypedefType(TypeName, base_type[DataType])
                elif DataType == 'Structure':
                    cur_state = 'structure'
                    cur_datatype = StructType(TypeName)
                elif DataType == 'Sequence':
                    self.msg_configs[TypeName] = SequenceType(TypeName, DatatypeReference, Bound)
                elif DataType == 'Array':
                    self.msg_configs[TypeName] = ArrayType(TypeName, DatatypeReference, Bound)
                elif DataType == 'String8':
                    self.msg_configs[TypeName] = String8Type(TypeName, Bound)
                elif DataType == 'Enumeration':
                    cur_state = 'enumeration'
                    bit_bound = int(EnumBitBound)
                    cur_datatype = EnumType(TypeName, bit_bound)
                else:
                    raise Exception('[Error] DataType: {} not support now!'.format(DataType))

        if cur_datatype is not None:
            self.msg_configs[cur_datatype.typename] = cur_datatype
            cur_datatype = None

        print('[Info] data type library parsing finished...')

    def parse_locator_config(self, ws, start_row_index):
        """
        Parse Locator configuration in Excel table.

        parameter:
            ws: Excel worksheet object.
            start_row_index: Which row to start reading data from (default starts from row 2, skipping the header).
        """
        print("[Info] start parsing the locator configuration and start reading data from line {}.".format(start_row_index))

        for cur_row in ws.iter_rows(min_row=start_row_index):
            ecu, ServiceInterface, Application, GuidPrefix, DomainParticipant, ParticipantId, DomainTag, DomainId, MetaTrafficUnicastPort, MetaTrafficUnicastAddress, MetaTrafficMulticastPort, MetaTrafficMulticastAddress, UserTrafficUnicastPort, UserTrafficUnicastAddress, UserTrafficMulticastPort, UserTrafficMulticastAddress, SourceIP, SourcePort, DeploymentVlan = [cur_row[i].value for i in range(19)]

            # 如果 ecu 为空，则退出
            if not ecu:
                continue

            # 处理 ECU 配置
            if ecu not in EcuConfig.dic:
                cur_ecu = EcuConfig()
                cur_ecu.name = ecu
                EcuConfig.dic[ecu] = cur_ecu
                self.ecu_configs.append(cur_ecu)

            # 处理 Application 配置
            if Application not in EcuConfig.dic[ecu].apps:
                cur_app = AppConfig()
                cur_app.name = Application
                cur_app.ecu = EcuConfig.dic[ecu]
                EcuConfig.dic[ecu].apps[Application] = cur_app

            # 处理 Domain 配置
            if DomainId not in DomainConfig.dic:
                cur_domain = DomainConfig()
                cur_domain.id = DomainId
                cur_domain.tag = DomainTag

                DomainConfig.dic[DomainId] = cur_domain

            # 处理 DomainParticipant 配置
            if DomainParticipant not in DomainParticipantConfig.dic:
                cur_dp = DomainParticipantConfig()
                cur_dp.app = EcuConfig.dic[ecu].apps[Application]
                cur_dp.domain = DomainConfig.dic[DomainId]
                cur_dp.name = DomainParticipant
                cur_dp.guid_prefix = GuidPrefix
                cur_dp.participant_id = ParticipantId

                cur_dp.meta_traffic_unicast_address = MetaTrafficMulticastAddress
                cur_dp.meta_traffic_multicast_address = MetaTrafficMulticastAddress
                cur_dp.user_traffic_unicast_address = UserTrafficUnicastAddress
                cur_dp.user_traffic_multicast_address = UserTrafficMulticastAddress

                cur_dp.source_ip = SourceIP
                cur_dp.source_port = SourcePort
                cur_dp.deployment_vlan = DeploymentVlan

                print('[Info] cur_dp.app: {}'.format(cur_dp.app.name))
                DomainParticipantConfig.dic[DomainParticipant] = cur_dp
                EcuConfig.dic[ecu].apps[Application].domain_participants.append(cur_dp)

    def parse_spdp_config(self, ws, start_row_index):
        """
        解析 SPDP 配置
        """
        for cur_row in ws.iter_rows(min_row=start_row_index):
            DomainParticipant, Spdp_ResendPeriod, Spdp_LeaseDuration, Spdp_ExpectsInlineQoS, USER_DATA, ENTITY_FACTORY, ParticipantId \
                = [cell.value for cell in cur_row]

        print("[Info] parse spdp config: \n\
              DomainParticipant: {}, Spdp_ResendPeriod: {}, Spdp_LeaseDuration: {}, Spdp_ExpectsInlineQoS: {}, USER_DATA: {}, ENTITY_FACTORY: {}, ParticipantId: {}".format(DomainParticipant, Spdp_ResendPeriod, Spdp_LeaseDuration, Spdp_ExpectsInlineQoS, USER_DATA, ENTITY_FACTORY, ParticipantId))

        DomainParticipantConfig.dic[DomainParticipant].spdp_resend_period = Spdp_ResendPeriod
        DomainParticipantConfig.dic[DomainParticipant].spdp_lease_duration = Spdp_LeaseDuration
        DomainParticipantConfig.dic[DomainParticipant].spdp_expects_inline_qos = Spdp_ExpectsInlineQoS
        DomainParticipantConfig.dic[DomainParticipant].user_data = USER_DATA
        DomainParticipantConfig.dic[DomainParticipant].entity_factory = ENTITY_FACTORY

        if DomainParticipantConfig.dic[DomainParticipant].participant_id != ParticipantId:
            raise Exception('error! participant id not equal in Locator Config and Spdp Config: {} {} {}'.formant(
                DomainParticipant, ParticipantId, DomainParticipantConfig.dic[DomainParticipant].participant_id))

    def parse_publisher_config(self, ws, start_row_index):
        for cur_row in ws.iter_rows(min_row=start_row_index):
            Topic, TopicKind, KeyValue, FilterExpression, DomainParticipant, Publisher, DataWriter, GroupId, EntityId, Sedp_HeartbeatPeriod, Sedp_NackResponseDelay, SedpNackSuppressionDuration, PushMode, HeartbeatPeriod, NackResponseDelay, NackSuppressionDuration, StatelessWriterResendPeriod, Autoenable_Created_Entities, GroupDataValue, Access_Scope, Coherent_Access, Ordered_Access, PartitionName, UserDataValue, DurabilityKind, _, _, _, _, _, _, HistoryKind, HistoryDepth, Max_samples, Max_instances, Max_Samples_Per_Instance, Autodispose_Unregistered_Instances, LivelinessKind, Lease_Duration, assert_time_interval, ReliabilityKind, Max_Blocking_Time, DeadlinePeriod, LatencyBudgetDuration, DestinationOrderKind, TransportPriorityValue, LifespanDuration, OwnershipKind, OwnershipStrength = [
                cur_row[i].value for i in range(49)]

            if Topic is None:
                continue

            if Publisher not in PublisherConfig.dic:
                cur_publisher = PublisherConfig()
                cur_publisher.domain_participant = DomainParticipantConfig.dic[DomainParticipant]
                cur_publisher.name = Publisher
                cur_publisher.topic = Topic
                cur_publisher.sedp_heart_beat_period = Sedp_HeartbeatPeriod
                cur_publisher.sedp_nack_response_delay = Sedp_NackResponseDelay
                DomainParticipantConfig.dic[DomainParticipant].publishers.append(cur_publisher)
                PublisherConfig.dic[Publisher] = cur_publisher

            if Topic not in TopicConfig.dic:
                cur_topic = TopicConfig()
                cur_topic.name = Topic
                cur_topic.topic_kind = TopicKind
                cur_topic.key_value = KeyValue
                cur_topic.filter_expression = FilterExpression
                TopicConfig.dic[Topic] = cur_topic

            cur_qos = QosConfig()
            cur_qos.durability_kind = DurabilityKind
            cur_qos.history_kind = HistoryKind
            cur_qos.history_depth = HistoryDepth
            cur_qos.liveliness_kind = LivelinessKind
            cur_qos.liveliness_lease_duration = Lease_Duration
            cur_qos.reliability_kind = ReliabilityKind
            cur_qos.deadline = DeadlinePeriod
            cur_qos.lifespan = LifespanDuration
            cur_qos.ownership = OwnershipKind
            cur_qos.ownership_strength = OwnershipStrength

            cur_dw = DataWriterConfig()
            cur_dw.publisher = PublisherConfig.dic[Publisher]
            cur_dw.name = DataWriter
            cur_dw.topic = TopicConfig.dic[Topic]
            cur_dw.entity_id = EntityId
            cur_dw.qos = cur_qos
            PublisherConfig.dic[Publisher].data_writers.append(cur_dw)
            DataWriterConfig.dic[DataWriter] = cur_dw

    def parse_subscriber_config(self, ws, start_row_index):
        for cur_row in ws.iter_rows(min_row=start_row_index):
            Topic, TopicKind, KeyValue, FilterExpression, DomainParticipant, Subscriber, DataReader, GroupId, EntityId, SedpHeartbeatSuppressionDuration, SedpExpectsInlineQoS, HeartbeatResponseDelay, HeartbeatSuppressionDuration, expectsInlineQos, Autoenable_Created_Entities, GroupDataValue, Access_Scope, Coherent_Access, Ordered_Access, PartitionName, UserDataValue, DurabilityKind, HistoryKind, HistoryDepth, Max_samples, Max_instances, Max_Samples_Per_Instance, Autopurge_Nowriter_Samples_Delay, Autopurge_Disposed_Samples_Delay, LivelinessKind, Lease_Duration, assert_time_interval, ReliabilityKind, Max_Blocking_Time, DeadlinePeriod, LatencyBudgetDuration, DestinationOrderKind, OwnershipKind, TimeBasedFilterMinimum_Separation = [
                cell.value for cell in cur_row]
            if DomainParticipant:
                if '397' in DomainParticipant:
                    self.sub_topics_of_397.append(Topic)
            if Topic is None:
                continue
            if Subscriber not in SubscriberConfig.dic:
                cur_subscriber = SubscriberConfig()
                cur_subscriber.domain_participant = DomainParticipantConfig.dic[DomainParticipant]
                cur_subscriber.name = Subscriber
                cur_subscriber.topic = Topic
                DomainParticipantConfig.dic[DomainParticipant].subscribers.append(cur_subscriber)
                SubscriberConfig.dic[Subscriber] = cur_subscriber

            if Topic not in TopicConfig.dic:
                cur_topic = TopicConfig()
                cur_topic.name = Topic
                cur_topic.topic_kind = TopicKind
                cur_topic.key_value = KeyValue
                cur_topic.filter_expression = FilterExpression
                TopicConfig.dic[Topic] = cur_topic

            cur_qos = QosConfig()
            cur_qos.durability_kind = DurabilityKind
            cur_qos.history_kind = HistoryKind
            cur_qos.history_depth = HistoryDepth
            cur_qos.liveliness_kind = LivelinessKind
            cur_qos.liveliness_lease_duration = Lease_Duration
            cur_qos.reliability_kind = ReliabilityKind
            cur_qos.deadline = DeadlinePeriod
            cur_qos.ownership = OwnershipKind

            cur_dr = DataReaderConfig()
            cur_dr.subscriber = SubscriberConfig.dic[Subscriber]
            cur_dr.name = DataReader
            cur_dr.topic = TopicConfig.dic[Topic]
            cur_dr.entity_id = EntityId
            cur_dr.qos = cur_qos
            SubscriberConfig.dic[Subscriber].data_readers.append(cur_dr)
            DataReaderConfig.dic[DataReader] = cur_dr

    def parse_topic_definition(self, ws, start_row_index):
        for cur_row in ws.iter_rows(min_row=start_row_index):
            TopicNames, TypeName = [cur_row[i].value for i in range(2)]
            if TopicNames is None:
                continue
            topic_names = TopicNames.replace(
                '\r', '').replace('_x000D_', '').split('\n')
            for topic_name in topic_names:
                if topic_name not in TopicConfig.dic:
                    continue
                TopicConfig.dic[topic_name].type = TypeName
                TopicConfig.dic[topic_name].ros_type = type_name_to_ros_type_name(
                    TypeName)
        for topic in TopicConfig.dic.values():
            print('[Warn] topic.type: {}'.format(topic.type))
            if topic.type is None:
                raise Exception('error! {} type is none'.format(topic.name))


class XmlParser(MatrixParser):
    def __init__(self, input_file):
        super().__init__()
        self.tree = ET.ElementTree(file=input_file)
        self.parse()
        self.post_parse()

    def parse(self):
        self.ns = {'ns': 'http://www.omg.org/spec/DDS-XML'}
        self.root = self.tree.getroot()

        self.parse_data_type_library()
        self.parse_dds_entity_config()

    def parse_data_type_library(self):
        for enum_node in self.root.findall('.//ns:enum', self.ns):
            type_name = enum_node.attrib['name']
            bit_bound = int(enum_node.attrib['bitBound'])
            cur_datatype = EnumType(type_name, bit_bound)
            for enumerator_node in enum_node.findall('ns:enumerator', self.ns):
                enum_name = enumerator_node.attrib['name']
                enum_value = int(enumerator_node.attrib['value'])
                cur_datatype.add_field(enum_name, enum_value)
            self.msg_configs[type_name] = cur_datatype

        for typedef_node in self.root.findall('.//ns:typedef', self.ns):
            type_name = typedef_node.attrib['name']
            datatype_reference = typedef_node.attrib['type']
            if datatype_reference == 'string':
                bound = typedef_node.attrib['stringMaxLength']
                self.msg_configs[type_name] = ArrayType(
                    type_name, 'char', bound)
            else:
                if 'nonBasicTypeName' in typedef_node.attrib:
                    datatype_reference = typedef_node.attrib['nonBasicTypeName']
                if 'arrayDimensions' in typedef_node.attrib:
                    bound = typedef_node.attrib['arrayDimensions']
                    self.msg_configs[type_name] = ArrayType(
                        type_name, datatype_reference, bound)
                else:
                    self.msg_configs[type_name] = TypedefType(
                        type_name, datatype_reference)

        for struct_node in self.root.findall('.//ns:struct', self.ns):
            type_name = struct_node.attrib['name']
            cur_datatype = StructType(type_name)
            for member_node in struct_node.findall('ns:member', self.ns):
                member_name = member_node.attrib['name']
                if 'nonBasicTypeName' in member_node.attrib:
                    datatype_reference = member_node.attrib['nonBasicTypeName']
                else:
                    datatype_reference = member_node.attrib['type']
                cur_datatype.add_field(datatype_reference, member_name)
            self.msg_configs[type_name] = cur_datatype

    def parse_dds_entity_config(self):
        for app_node in self.root.findall('.//ns:application', self.ns):
            Application = app_node.attrib['name']

            # for name like that: APPNAME_HPCx_TDA4/TC397 -> HPCx_TDA4/TC397
            ecu = '_'.join(Application.split('_')[-2:])

            # for name like that: APPNAME_TBOX1_TBOX1 -> TBOX1
            if ecu.split('_')[0] == ecu.split('_')[1]:
                ecu = ecu.split('_')[0]

            if ecu not in EcuConfig.dic:
                cur_ecu = EcuConfig()
                cur_ecu.name = ecu
                EcuConfig.dic[ecu] = cur_ecu
                self.ecu_configs.append(cur_ecu)

            Application = Application.replace('_' + ecu, '')
            if Application not in EcuConfig.dic[ecu].apps:
                cur_app = AppConfig()
                cur_app.name = Application
                cur_app.ecu = EcuConfig.dic[ecu]
                EcuConfig.dic[ecu].apps[Application] = cur_app

            for dp_node in app_node.findall('ns:domain_participant', self.ns):
                DomainParticipant = dp_node.attrib['name']

                if DomainParticipant not in DomainParticipantConfig.dic:
                    cur_dp = DomainParticipantConfig()
                    cur_dp.app = EcuConfig.dic[ecu].apps[Application]
                    cur_dp.name = DomainParticipant

                    DomainParticipantConfig.dic[DomainParticipant] = cur_dp
                    EcuConfig.dic[ecu].apps[Application].domain_participants.append(
                        cur_dp)

                for pub_node in dp_node.findall('ns:publisher', self.ns):
                    Publisher = pub_node.attrib['name']
                    if Publisher not in PublisherConfig.dic:
                        cur_publisher = PublisherConfig()
                        cur_publisher.domain_participant = DomainParticipantConfig.dic[
                            DomainParticipant]
                        cur_publisher.name = Publisher
                        DomainParticipantConfig.dic[DomainParticipant].publishers.append(
                            cur_publisher)
                        PublisherConfig.dic[Publisher] = cur_publisher

                    for dw_node in pub_node.findall('ns:data_writer', self.ns):
                        DataWriter = dw_node.attrib['name']
                        Topic = dw_node.attrib['topic_ref']

                        if Topic not in TopicConfig.dic:
                            cur_topic = TopicConfig()
                            cur_topic.name = Topic
                            TopicConfig.dic[Topic] = cur_topic

                        cur_dw = DataWriterConfig()
                        cur_dw.publisher = PublisherConfig.dic[Publisher]
                        cur_dw.name = DataWriter
                        cur_dw.topic = TopicConfig.dic[Topic]
                        PublisherConfig.dic[Publisher].data_writers.append(
                            cur_dw)
                        DataWriterConfig.dic[DataWriter] = cur_dw

                for sub_node in dp_node.findall('ns:subscriber', self.ns):
                    Subscriber = sub_node.attrib['name']
                    if Subscriber not in SubscriberConfig.dic:
                        cur_subscriber = SubscriberConfig()
                        cur_subscriber.domain_participant = DomainParticipantConfig.dic[
                            DomainParticipant]
                        cur_subscriber.name = Subscriber
                        DomainParticipantConfig.dic[DomainParticipant].subscribers.append(
                            cur_subscriber)
                        SubscriberConfig.dic[Subscriber] = cur_subscriber

                    for dr_node in sub_node.findall('ns:data_reader', self.ns):
                        DataReader = dr_node.attrib['name']
                        Topic = dr_node.attrib['topic_ref']
                        if Topic not in TopicConfig.dic:
                            cur_topic = TopicConfig()
                            cur_topic.name = Topic
                            TopicConfig.dic[Topic] = cur_topic

                        cur_dr = DataReaderConfig()
                        cur_dr.subscriber = SubscriberConfig.dic[Subscriber]
                        cur_dr.name = DataReader
                        cur_dr.topic = TopicConfig.dic[Topic]
                        SubscriberConfig.dic[Subscriber].data_readers.append(
                            cur_dr)
                        DataReaderConfig.dic[DataReader] = cur_dr

        for register_type_node in self.root.findall('.//ns:register_type', self.ns):
            TypeName = register_type_node.attrib['type_ref']
            topic_name = register_type_node.attrib['name'].replace(
                '_register_type_ref', '')
            if topic_name not in TopicConfig.dic:
                continue
            TopicConfig.dic[topic_name].type = TypeName
            TopicConfig.dic[topic_name].ros_type = type_name_to_ros_type_name(
                TypeName)

        for topic in TopicConfig.dic.values():
            if topic.type is None:
                raise Exception('error! {} type is None'.format(topic.name))
