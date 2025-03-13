from jinja2 import Environment, FileSystemLoader
import os
import re


def get_resource_path():
    return os.path.join(os.path.dirname(__file__), 'resource')


env = Environment(keep_trailing_newline=True,
                  loader=FileSystemLoader(os.path.join(get_resource_path(), 'template')),
                  lstrip_blocks=True,
                  trim_blocks=True)


def expand_app_template_file(template_file, output_dir, output_file, config):
    expand_template_file('app', template_file, output_dir, output_file, config)


def expand_interfaces_template_file(template_file, output_dir, output_file, config):
    expand_template_file('interfaces', template_file, output_dir, output_file, config)


def expand_template_file(category, template_file, output_dir, output_file, config):
    output_file_name = os.path.join(output_dir, output_file)
    env.get_template(category + '/' + template_file + '.jinja2').stream(config).dump(output_file_name)


def is_base_type(type_name):
    # https://design.ros2.org/articles/mapping_dds_types.html
    base_type = ('bool', 'byte', 'char',
                 'uint8', 'uint16', 'uint32', 'uint64',
                 'int8', 'int16', 'int32', 'int64',
                 'float32', 'float64',
                 'boolean', 'float', 'double',
                 'string')
    return type_name in base_type


def get_base_type_size(type_name):
    base_type_size = {
        'bool': 1,
        'byte': 1,
        'char': 1,
        'uint8': 1,
        'uint16': 2,
        'uint32': 4,
        'uint64': 8,
        'int8': 1,
        'int16': 2,
        'int32': 4,
        'int64': 8,
        'float32': 4,
        'float64': 8,
        'boolean': 1,
        'float': 4,
        'double': 8,
    }
    return base_type_size[type_name]


def get_base_type_alignment(type_name):
    return get_base_type_size(type_name)


def type_name_to_dds_type_name(typename):
    base_type_to_dds_type = {'bool': 'boolean',
                             'float32': 'float',
                             'float64': 'double'}
    if typename in base_type_to_dds_type:
        return base_type_to_dds_type[typename]
    return typename


def type_name_to_ros_type_name(type_name):
    # TODO, find a way to fix this.
    special_type = {
        'LHCRC': 'LHCRCUint64',
        'LH_CRC': 'LHCRCUint32',
        'LHEstimatedWidth': 'LHEstimatedWidthFloat32',
        'LH_Estimated_Width': 'LHEstimatedWidthUint8',
        'LHProtocolVersion': 'LHProtocolVersionUint8',
        'LH_Protocol_Version': 'LHProtocolVersionUint8',
        'LH_ProtocolVersion': 'LHProtocolVersionArray'}

    if is_base_type(type_name):
        return type_name
    if type_name in special_type:
        return special_type[type_name]
    print('[Debug] type_name_to_ros_type_name: {}'.format(type_name))
    return upper_first_letter(''.join(type_name.split('_')))


def upper_first_letter(name):
    return name[:1].upper() + name[1:]


def camel_to_snake(name):
    name = name.strip().replace('\n', '').replace('\r', '').replace('_x000D_', '')
    return '_'.join([_camel_to_snake_helper(sub_name) for sub_name in name.split('_') if sub_name != ''])


def _camel_to_snake_helper(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


# rosidl constant name can not have trailing _:
#   rosidl_adapter: Constant with trailing _ causes parser to infinite loop #693
#   https://github.com/ros2/rosidl/issues/693
def name_to_ros_constant_name(name):
    return camel_to_snake(name).upper()
