import argparse
import os
import yaml
from .utils import *


def expand_block_template_file(block_config, package_config, include_dir, src_dir, special_implementation=''):
    block_type = block_config['type']
    header_file = block_config['file_name_prefix'] + '.hpp'
    source_file = block_config['file_name_prefix'] + '.cpp'
    config = {'block': block_config, 'package': package_config['package']}
    expand_app_template_file(block_type + '_block.hpp', include_dir, header_file, config)
    expand_app_template_file(special_implementation + block_type + '_block.cpp', src_dir, source_file, config)


def expand_model_template_file(model_config, include_dir, src_dir):
    header_file = 'model_wrapper.hpp'
    source_file = 'model_wrapper.cpp'
    config = {'model': model_config}
    expand_app_template_file(header_file, include_dir, header_file, config)
    expand_app_template_file(source_file, src_dir, source_file, config)


class AppCreator:
    def __init__(self):
        self.package_dir = None
        self.src_dir = None
        self.include_dir = None
        self.config_dir = None
        self.af_project_dir = None
        self.special_implementation = ''
        self.sub_topics_of_397 = []

    def create_from_dir(self, app_dir):
        self.prepare_dir(app_dir)
        self.create_app()

    def create_app(self):
        if os.path.exists(self.orchestration_filename):
            self.create_from_orchestration()
        elif os.path.exists(self.manifest_filename):
            self.create_from_manifest()

    def prepare_dir(self, package_dir):
        self.package_dir = package_dir
        self.config_dir = os.path.join(package_dir, 'orchestration')
        self.src_dir = os.path.join(package_dir, 'src/block')
        self.include_dir = os.path.join(package_dir, 'include/block')
        self.af_project_dir = os.path.join(package_dir, 'af_project')
        for dir in (self.src_dir, self.include_dir, self.config_dir, self.af_project_dir):
            os.makedirs(dir, exist_ok=True)

        self.manifest_filename = os.path.join(self.config_dir, 'manifest.yaml')
        self.orchestration_filename = os.path.join(
            self.config_dir, 'orchestration.yaml')

    def create_from_orchestration(self):
        self.create_manifest_from_orchestration()
        self.generate_config_from_orchestration()

        self.create_blocks()

    def generate_config_from_orchestration(self):
        with open(self.orchestration_filename, 'rb') as f:
            orchestration = yaml.safe_load(f)

        package_config = {
            'package': {
                'name': orchestration['app_name'],
                'description': 'af red app for {}'.format(orchestration['app_name']),
                'depends': set(),
                'library': orchestration['app_name']
            }}

        block_configs = []
        for task in orchestration['tasks']:
            # block: /xxx/class_name -> class_name
            class_name = task['block'].split('/')[2]
            file_name_prefix = camel_to_snake(class_name)
            block_config = {'name': class_name,
                            'file_name_prefix': file_name_prefix}

            # using list rather than set to keep interfaces order
            interfaces = []
            if 'input_topics' in task:
                block_config['inputs'] = self.generate_topic_config([topic for topic in task['input_topics']])
                for topic in task['input_topics']:
                    print("[Debug] --- input_topics: {}".format(topic))
                for topic in task['input_topics']:
                    if topic['type'] not in interfaces:
                        interfaces.append(topic['type'])
            if 'output_topics' in task:
                block_config['outputs'] = self.generate_topic_config([topic for topic in task['output_topics']])
                for topic in block_config['outputs']:
                    print("[Debug] --- output_topics: {}".format(topic))
                for topic in task['output_topics']:
                    print('[Debug] output_topics: {}'.format(topic['name']))
                    if topic['type'] not in interfaces:
                        interfaces.append(topic['type'])

            for interface in interfaces:
                # interface: <package_name>/<msg/srv/act>/<message_type>
                interface_package = interface.split('/')[0]
                package_config['package']['depends'].add(interface_package)

            block_config['interfaces'] = self.generate_interface_config(interfaces)
            block_config['type'] = task['type'] if 'type' in task else 'compute'
            if 'output_topics' in task:
                block_config['output_domains'] = set()
                block_config['out_to_397'] = False
                for output in block_config['outputs']:
                    print('[Debug] block_config::outputs: {}'.format(output['name']))
                    block_config['output_domains'].add(output['domain_id'])
                    if output['is_sub_topics_of_397']:
                        block_config['out_to_397'] = True
            block_configs.append(block_config)

        self.package_config = package_config
        self.block_configs = block_configs

    def create_blocks(self):
        self.create_project(self.package_config)

        for block_config in self.block_configs:
            print('[Debug] block_config: {}'.format(block_config['name']))
            expand_block_template_file(
                block_config,
                self.package_config,
                self.include_dir,
                self.src_dir,
                self.special_implementation)

    def create_project(self, package_config):
        for file in ('package.xml', 'CMakeLists.txt'):
            expand_app_template_file(
                file, self.package_dir, file, package_config)

        for file in ('af_project.cpp', 'CMakeCPack.cmake', 'manifest.xml', 'project.cmake'):
            expand_app_template_file(
                file, self.af_project_dir, file, package_config)

    def create_manifest_from_orchestration(self):
        with open(self.orchestration_filename, 'rb') as f:
            orchestration_config = yaml.safe_load(f)

        tasks = orchestration_config['tasks']
        modules = {}
        for task in tasks:
            # block: /module_name/class_name -> class_name
            module_name, class_name = task['block'].split('/')[1:]
            if module_name not in modules:
                modules[module_name] = {
                    'name': module_name,
                    'library': 'lib{}.so'.format(module_name),
                    'blocks': []
                }
            cur_block = {
                'name': class_name,
                'class_name': class_name,
                'type': task['type'] if 'type' in task else 'compute'
            }
            if 'input_topics' in task:
                cur_block['inputs'] = [topic['type']
                                       for topic in task['input_topics']]
            if 'output_topics' in task:
                cur_block['outputs'] = [topic['type']
                                        for topic in task['output_topics']]
            modules[module_name]['blocks'].append(cur_block)

        manifest_config = {'modules': [module for module in modules.values()]}

        with open(self.manifest_filename, 'w') as f:
            f.write(yaml.dump(manifest_config))

    def create_from_manifest(self):
        self.generate_config_from_manifest()
        self.create_blocks()

    def generate_config_from_manifest(self):
        with open(self.manifest_filename, 'rb') as f:
            manifest = yaml.safe_load(f)

        modules = manifest['modules']
        if len(modules) != 1:
            raise Exception('num of modules != 0, not support now')
        module = modules[0]

        # libxxx.so -> xxx
        library = module['library'].split('.')[0][3:]
        blocks = module['blocks']
        package_name = module['name']

        package_config = {'package': {
            'name': package_name,
            'description': 'af red app for {}'.format(package_name),
            'depends': set(),
            'library': library
        }}

        block_configs = []
        for block in blocks:
            class_name = block['class_name']
            file_name_prefix = camel_to_snake(class_name)
            block_config = {'name': class_name,
                            'file_name_prefix': file_name_prefix}

            # using list rather than set to keep interfaces order
            interfaces = []
            for ports in ('inputs', 'outputs'):
                if ports in block:
                    block_config[ports] = self.generate_interface_config(
                        block[ports])
                    for port in block[ports]:
                        if port not in interfaces:
                            interfaces.append(port)

            for interface in interfaces:
                # interface: <package_name>/<msg/srv/act>/<message_type>
                interface_package = interface.split('/')[0]
                package_config['package']['depends'].add(interface_package)

            block_config['interfaces'] = self.generate_interface_config(
                interfaces)
            block_config['type'] = block['type']
            block_configs.append(block_config)

        self.package_config = package_config
        self.block_configs = block_configs

    def generate_interface_config(self, interfaces):
        return [{'package': interface.split('/')[0],
                 'category': interface.split('/')[1],
                 'type': interface.split('/')[2],
                 'header': camel_to_snake(interface.split('/')[2])}
                for interface in interfaces]

    def generate_topic_config(self, topics):
        topic_configs = []
        for topic in topics:
            print('[Debug] generate_topic_config::topic_name: {}'.format(topic['name']))
            config = {
                'package': topic['type'].split('/')[0],
                'category': topic['type'].split('/')[1],
                'type': topic['type'].split('/')[2],
                'header': camel_to_snake(topic['type'].split('/')[2]),
                'name': topic['name'],
                'domain_id': topic['domain_id'],
                'qos': topic['qos']
            }
            # Check if the topic is a sub-topic of 397
            if self.sub_topics_of_397:
                config['is_sub_topics_of_397'] = topic['name'] in self.sub_topics_of_397
            else:
                config['is_sub_topics_of_397'] = False  # Default value if sub_topics_of_397 is not set
            # Append the config to topic_configs
            topic_configs.append(config)
        return topic_configs


class SimulinkAppCreator(AppCreator):
    def __init__(self):
        self.special_implementation = 'simulink_'
        self.sub_topics_of_397 = []

    def create_from_dir(self, app_dir, topics_397, model_name='HAV3G_TDA4MultiThreads', model_class='EU260_MultiThreadsModelClass'):
        self.sub_topics_of_397 = topics_397
        super().create_from_dir(app_dir)
        self.create_model(model_name, model_class)

    def create_model(self, model_name, model_class):
        model_config = {'inputs': [],
                        'outputs': [],
                        'interfaces': [],
                        'name': model_name,
                        'type': model_class,
                        'depends': self.package_config['package']['depends']}

        for block_config in self.block_configs:
            if 'inputs' in block_config:
                model_config['inputs'] += block_config['inputs']
            if 'outputs' in block_config:
                model_config['outputs'] += block_config['outputs']
            if 'interfaces' in block_config:
                model_config['interfaces'] += block_config['interfaces']

        expand_model_template_file(
            model_config, self.include_dir, self.src_dir)


class PerformanceTestAppCreator(AppCreator):
    def __init__(self):
        self.special_implementation = 'performance_test_'
        self.sub_topics_of_397 = []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='input package dir', type=str)
    args = parser.parse_args()

    package_dir = args.input
    app_creator = AppCreator()
    app_creator.create_from_dir(package_dir)


if __name__ == '__main__':
    main()
