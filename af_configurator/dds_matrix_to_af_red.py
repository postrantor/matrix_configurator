import argparse
import os
import yaml
from .utils import *
from .openpyxl_patch import *
from .dds_entity_config import *
from .app_creator import AppCreator, SimulinkAppCreator, PerformanceTestAppCreator
from .matrix_parser import MatrixParser


class AfConfigurator:
    def __init__(self, input_file, output_dir, interfaces_name):
        print('parsing: {}, output dir: {}'.format(input_file, output_dir))

        self.input_file = input_file
        self.output_dir = os.path.join(os.getcwd(), output_dir)
        self.interfaces_name = interfaces_name

        self.parser = MatrixParser.create(input_file)
        self.ecus = self.parser.ecu_configs
        self.required_types = self.parser.required_types
        self.required_type_objects = self.parser.required_type_objects
        self.sub_topics_of_397 = self.parser.sub_topics_of_397

    def generate_ros_idl(self):
        print('[Info] generate ros idl')

        package_dir = os.path.join(self.output_dir, self.interfaces_name)
        msg_dir = os.path.join(package_dir, 'msg')

        os.makedirs(package_dir, exist_ok=True)
        os.makedirs(msg_dir, exist_ok=True)

        package_config = {
            'package': {
                'name': self.interfaces_name,
                'description': 'interfaces for {}'.format(self.interfaces_name)
            }
        }

        for file in ('package.xml', 'CMakeLists.txt'):
            expand_interfaces_template_file(file, package_dir, file, package_config)

        for t in self.required_types:
            datatype = self.parser.msg_configs[t]
            # print('[Info] datatype: {}'.format(datatype.ros_typename))
            message_file = os.path.join(msg_dir, '{}.msg'.format(datatype.ros_typename))
            with open(message_file, 'w') as f:
                f.write(datatype.get_ros_define())

    def generate_dds_idl(self):
        idl_dir = os.path.join(self.output_dir, 'idl')
        os.makedirs(idl_dir, exist_ok=True)
        for t in self.required_types:
            datatype = self.parser.msg_configs[t]
            message_file = os.path.join(
                idl_dir, '{}.idl'.format(datatype.typename))
            with open(message_file, 'w') as f:
                f.write(datatype.get_dds_define())

        self.generate_dds_type_category()

    def generate_dds_type_category(self):
        category_file = os.path.join(self.output_dir, 'datatype_category.yaml')
        datatype_category = {
            'typedef': [d.typename for d in self.required_type_objects if isinstance(d, TypedefType)],
            'array': [d.typename for d in self.required_type_objects if isinstance(d, ArrayType)],
            'struct': [d.typename for d in self.required_type_objects if isinstance(d, StructType)],
            'enum': [d.typename for d in self.required_type_objects if isinstance(d, EnumType)]
        }
        with open(category_file, 'w') as f:
            f.write(yaml.dump(datatype_category))

    def generate_af_config(self, someip_matrix=None):
        for ecu in self.ecus:
            if '397' in ecu.name:
                continue
            ecu_dir = os.path.join(self.output_dir, ecu.name)
            os.makedirs(ecu_dir, exist_ok=True)
            for app in ecu.apps.values():
                # generate special code for ADS_AutoDrive
                # need full someip matrix for period information
                if someip_matrix and 'hi_adus' in app.name or 'AutoDrive' in app.name:
                    self.generate_simulink_app_config(
                        ecu_dir, app, someip_matrix)
                else:
                    self.generate_app_config(ecu_dir, app)

    def generate_simulink_app_config(self, ecu_dir, app, someip_matrix):
        app_dir = os.path.join(ecu_dir, app.name)
        config_dir = os.path.join(app_dir, 'orchestration')
        os.makedirs(app_dir, exist_ok=True)
        os.makedirs(config_dir, exist_ok=True)

        tasks = [{'name': dp.name,
                  'block': '/{}/{}'.format(app.name, dp.name),
                  'processor': 0,
                  'priority': 0,
                  'type': 'composite',
                  'input_topics': [{'name': dr.topic.name,
                                    'type': '{}/msg/{}'.format(self.parser.get_interface_of_sub_topic(dr.topic.name), dr.topic.ros_type),
                                    'qos': dr.qos.get_config(),
                                    'domain_id': dp.domain.id}
                                   for sub in dp.subscribers for dr in sub.data_readers]}
                 for dp in app.domain_participants]

        timer_tasks = {}
        period_dic = self.parse_topic_period(someip_matrix)
        for dp in app.domain_participants:
            for pub in dp.publishers:
                for dw in pub.data_writers:
                    if dw.topic.name not in period_dic:
                        raise Exception('error! {} not found in someip matrix'.format(
                            dw.topic.name))
                    period = period_dic[dw.topic.name]
                    if period not in timer_tasks:
                        task_name = 'PeriodTask_{}_ms'.format(str(period))
                        timer_tasks[period] = {
                            'name': task_name,
                            'block': '/{}/{}'.format(app.name, task_name),
                            'processor': 0,
                            'priority': 0,
                            'type': 'periodic',
                            'period': period,
                            'offset': 0,
                            'output_topics': []}
                    timer_tasks[period]['output_topics'].append({
                        'name': dw.topic.name,
                        'type': '{}/msg/{}'.format(self.parser.get_interface_of_pub_topic(dw.topic.name), dw.topic.ros_type),
                        'qos': dw.qos.get_config(),
                        'domain_id': dp.domain.id
                    })
        tasks += timer_tasks.values()

        orchestration_config = {
            'app_name': app.name,
            'processors': [{
                'id': 0,
                'force_realtime': 'false',
                'rt_priority': 97,
                'sched_policy': 'FIFO',
                'cpu_affinity': 0 - 15,
            }],
            'tasks': tasks
        }

        orchestration_file = os.path.join(
            config_dir, 'orchestration.yaml')
        with open(orchestration_file, 'w') as f:
            f.write(yaml.dump(orchestration_config))

        app_creator = SimulinkAppCreator()
        app_creator.create_from_dir(app_dir, self.sub_topics_of_397)

    def parse_topic_period(self, someip_matrix):
        period_dic = {}
        someip_wb = openpyxl.load_workbook(
            someip_matrix, read_only=True, data_only=True)
        service_interfaces_ws = someip_wb['ServiceInterfaces']
        for cur_row in service_interfaces_ws.iter_rows(min_row=2):
            ServiceInterfaceName, ServiceInterfaceID, MajorVersion, MinorVersion, ServiceInterfaceDescription, ElementName, ElementID, ElementType, FieldType, MethodType, Eventgroup, SendingStrategy, Period, ElementDescription, L4Protocol, IN_OUT, ParameterPosition, ParameterName, ParameterDescription, DatatypeReference = [
                cur_row[i].value for i in range(20)]
            if Period is None or Period == '-':
                continue
            # s -> ms
            Period = int(float(Period) * 1000)
            if ElementType == 'Event':
                period_dic['{}_Event_Topic'.format(ElementName)] = Period
            elif ElementType == 'Method':
                if MethodType == 'FF':
                    period_dic['{}_MethodFF_Topic'.format(
                        ElementName)] = Period
                elif MethodType == 'RR':
                    period_dic['{}_MethodRR_Request_Topic'.format(
                        ElementName)] = Period
                    period_dic['{}_MethodRR_Reply_Topic'.format(
                        ElementName)] = Period
        return period_dic

    def generate_app_config(self, ecu_dir, app):
        app_dir = os.path.join(ecu_dir, app.name)
        config_dir = os.path.join(app_dir, 'orchestration')
        os.makedirs(app_dir, exist_ok=True)
        os.makedirs(config_dir, exist_ok=True)

        tasks = []
        for dp in app.domain_participants:
            tasks += [{
                'name': pub.name,
                'block': '/{}/{}'.format(app.name, pub.name),
                'processor': 0,
                'priority': 0,
                'domain_id': dp.domain.id,
                'interval': 500,
                'count': -1,
                'type': 'timer',
                'output_topics': [{
                    'name': dw.topic.name,
                    'type': '{}/msg/{}'.format(self.interfaces_name, dw.topic.ros_type),
                    'qos': dw.qos.get_config(),
                    'domain_id': dp.domain.id
                } for dw in pub.data_writers]
            } for pub in dp.publishers]

            for sub in dp.subscribers:
                for dr in sub.data_readers:
                    block_name = dr.name.split('Topic')[0] + 'Block'
                    cur_task = {
                        'name': block_name.lower(),
                        'block': '/{}/{}'.format(app.name, block_name),
                        'processor': 0,
                        'priority': 0,
                        'type': 'compute',
                        'input_topics': [{
                            'name': dr.topic.name,
                            'type': '{}/msg/{}'.format(self.interfaces_name, dr.topic.ros_type),
                            'qos': dr.qos.get_config(),
                            'domain_id': dp.domain.id
                        }]
                    }
                    tasks.append(cur_task)

        orchestration_config = {
            'app_name': app.name,
            'processors': [
                {'id': 0}
            ],
            'tasks': tasks
        }

        orchestration_file = os.path.join(
            config_dir, 'orchestration.yaml')
        with open(orchestration_file, 'w') as f:
            f.write(yaml.dump(orchestration_config))

        app_creator = AppCreator()
        app_creator.create_from_dir(app_dir)

    def generate_perf_test_app_config(self):
        app_dir = os.path.join(self.output_dir, 'performance_test')
        config_dir = os.path.join(app_dir, 'orchestration')
        os.makedirs(app_dir, exist_ok=True)
        os.makedirs(config_dir, exist_ok=True)

        required_types = sorted(list(self.parser.top_required_types))
        orchestration_config = {
            'app_name': 'message_size_test',
            'processors': [
                {'id': 0}
            ],
            'tasks': [{
                'name': 'test',
                'block': '/test/test',
                'processor': 0,
                'priority': 0,
                'type': 'compute',
                'input_topics': [{
                        'name': type_name_to_ros_type_name(type_name),
                        'type': '{}/msg/{}'.format(self.interfaces_name, type_name_to_ros_type_name(type_name)),
                        'qos': "default_qos",
                        'domain_id': 0
                } for type_name in required_types]
            }]}

        orchestration_file = os.path.join(config_dir, 'orchestration.yaml')
        with open(orchestration_file, 'w') as f:
            f.write(yaml.dump(orchestration_config))

        app_creator = PerformanceTestAppCreator()
        app_creator.create_from_dir(app_dir)

        # TODO, uncomment following lines to print the size of msg type
        # for f in required_types:
        #     print('{} {}'.format(f, self.parser.get_type_size(f)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='input red matrix excel/xml',
                        default='agv-red-dp.xlsx', type=str)
    parser.add_argument('-o', '--output', help='output folder',
                        default='test_output', type=str)
    parser.add_argument('--someip', default=None,
                        help='input someip matrix excel for period information', type=str)
    parser.add_argument('--interfaces', help='interfaces package name',
                        default='agv_interfaces', type=str)
    args = parser.parse_args()

    hpc_25_config = AfConfigurator(args.input, args.output, args.interfaces)

    hpc_25_config.generate_ros_idl()
    hpc_25_config.generate_af_config(someip_matrix=args.someip)
    hpc_25_config.generate_perf_test_app_config()


if __name__ == '__main__':
    main()
